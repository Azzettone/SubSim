"""
HornBlock — blocco "tromba acustica" del Block Assembler.

Genera la geometria costruttiva (pannelli) di una tromba a sezione
rettangolare o trapezoidale, con espansione exponential / tractrix /
hypex / conical, fold 0/1/2 e ThroatAdapter opzionale per ridurre
l'area emissiva del driver alla gola della tromba.

Riusa i calcoli acustici verificati di `core.horn_calculator` (formule
Webster 1919, Klipsch 1941, Salmon 1946, Olson 1957).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.constants import (
    SPEED_OF_SOUND,
    EXPANSION_EXPONENTIAL, EXPANSION_CONICAL,
    EXPANSION_TRACTRIX, EXPANSION_HYPEX,
    EXPANSION_TYPES,
)
from ..core.driver_model import DriverModel
from ..core.horn_calculator import (
    calculate_flare_rate,
    calculate_horn_length,
    area_at_position,
)
from .base_block import (
    Block,
    Panel,
    ConnectionPort,
    ValidationWarning,
    Severity,
    DEFAULT_PANEL_THICKNESS,
    DEFAULT_PANEL_MATERIAL,
)


# ─── Default a livello di classe (modificabili a runtime) ────────────────────

DEFAULT_N_SECTIONS = 50         # discretizzazione profilo tromba
DEFAULT_ASPECT_RATIO = 1.5      # mouth width / mouth height
MAX_AREA_RATIO_ADJACENT = 4.0   # Olson (1957): vincolo riflessioni interne


# ─── Strutture di supporto ───────────────────────────────────────────────────

@dataclass
class HornSectionGeometry:
    """
    Sezione trasversale della tromba in posizione x lungo l'asse (post-fold).

    Attributi:
        x_axial: distanza lungo l'asse della tromba dalla gola, in metri
                 (lunghezza "srotolata", non profondità fisica)
        area: area sezione [m²]
        width: larghezza sezione [m]
        height: altezza sezione [m]
        center: posizione centro sezione nello spazio globale [m] (3,)
        normal: versore direzione di propagazione locale [m] (3,)
        vertices: angoli sezione nello spazio globale [m] (4, 3)
    """
    x_axial: float
    area: float
    width: float
    height: float
    center: np.ndarray
    normal: np.ndarray
    vertices: np.ndarray  # (4, 3)


@dataclass
class ThroatAdapter:
    """
    Pannello adattatore tra l'area emissiva del driver (Sd, circolare)
    e la gola della tromba (rettangolare).

    Modi:
        "match"  : throat_area = Sd (nessun adattatore reale, no panel)
        "reduce" : throat_area < Sd (compression) — più comune in trombe
                   di mid/CD; nei sub aumenta l'efficienza ma riduce xmax utile
        "expand" : throat_area > Sd (raro, decompression)

    Si specifica throat_area diretta OPPURE compression_ratio (Sd/throat).
    Se entrambi None → throat_area = Sd (modalità match implicita).

    Attributi:
        mode: "match" | "reduce" | "expand"
        throat_area: area finale gola [m²]; se None usa compression_ratio
        compression_ratio: Sd / throat_area
        adapter_length: lunghezza transizione [m]
        adapter_profile: "conical" | "exponential"
    """
    mode: str = "match"
    throat_area: Optional[float] = None
    compression_ratio: Optional[float] = None
    adapter_length: float = 0.05
    adapter_profile: str = "conical"

    VALID_MODES = ("match", "reduce", "expand")
    VALID_PROFILES = ("conical", "exponential")

    def __post_init__(self) -> None:
        if self.mode not in self.VALID_MODES:
            raise ValueError(
                f"ThroatAdapter.mode deve essere in {self.VALID_MODES}, "
                f"ricevuto: {self.mode!r}"
            )
        if self.adapter_profile not in self.VALID_PROFILES:
            raise ValueError(
                f"ThroatAdapter.adapter_profile deve essere in "
                f"{self.VALID_PROFILES}, ricevuto: {self.adapter_profile!r}"
            )
        if self.adapter_length <= 0.0:
            raise ValueError("ThroatAdapter.adapter_length deve essere > 0")

    def resolve_throat_area(self, driver_sd: float) -> float:
        """Calcola l'area gola finale dato Sd del driver."""
        if self.mode == "match":
            return driver_sd
        if self.throat_area is not None and self.compression_ratio is not None:
            raise ValueError(
                "ThroatAdapter: specifica solo throat_area O compression_ratio, "
                "non entrambi."
            )
        if self.throat_area is not None:
            return float(self.throat_area)
        if self.compression_ratio is not None:
            if self.compression_ratio <= 0.0:
                raise ValueError("compression_ratio deve essere > 0")
            return driver_sd / self.compression_ratio
        # nessuno specificato → match
        return driver_sd

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "throat_area": self.throat_area,
            "compression_ratio": self.compression_ratio,
            "adapter_length": self.adapter_length,
            "adapter_profile": self.adapter_profile,
        }


# ─── HornBlock ───────────────────────────────────────────────────────────────

class HornBlock(Block):
    """
    Blocco tromba acustica.

    Costruttori:
        HornBlock.from_acoustics(...) — partendo da parametri acustici
        HornBlock.from_constraints(...) — partendo da vincoli dimensionali

    NOTA: la versione corrente genera la geometria dei pannelli per fold=0
    (tromba dritta). Fold 1 e 2 sono supportati come parametri (lunghezza
    asse e bounding box ricalcolati) ma la generazione precisa dei pannelli
    interni di piegatura sarà completata in step successivi del Layer 3.
    Lo stato di supporto fold è esposto da `geometry_implementation_status`.
    """

    block_type = "horn"

    DEFAULT_N_SECTIONS = DEFAULT_N_SECTIONS
    DEFAULT_PANEL_THICKNESS = DEFAULT_PANEL_THICKNESS

    # ── Costruttore privato ──────────────────────────────────────────────────

    def __init__(
        self,
        *,
        driver: DriverModel,
        cutoff_frequency: float,
        expansion: str,
        hypex_T: float,
        throat_area: float,
        mouth_width: float,
        mouth_height: float,
        fold: int,
        section_shape: str,
        n_sections: int,
        throat_adapter: Optional[ThroatAdapter],
        panel_thickness: float,
        panel_material: str,
        c: float = SPEED_OF_SOUND,
        origin: Optional[np.ndarray] = None,
    ) -> None:
        # Validazione parametri scalari
        if expansion not in EXPANSION_TYPES:
            raise ValueError(
                f"expansion deve essere in {EXPANSION_TYPES}, "
                f"ricevuto: {expansion!r}"
            )
        if section_shape not in ("rectangular", "trapezoidal"):
            raise ValueError(
                f"section_shape deve essere 'rectangular' o 'trapezoidal', "
                f"ricevuto: {section_shape!r}"
            )
        if fold not in (0, 1, 2):
            raise ValueError(f"fold deve essere 0, 1 o 2 (ricevuto: {fold})")
        if n_sections < 4:
            raise ValueError("n_sections deve essere >= 4")
        if cutoff_frequency <= 0.0:
            raise ValueError("cutoff_frequency deve essere > 0")
        if throat_area <= 0.0 or mouth_width <= 0.0 or mouth_height <= 0.0:
            raise ValueError("throat_area, mouth_width, mouth_height devono essere > 0")
        if expansion == EXPANSION_HYPEX and not (0.0 <= hypex_T < 1.0):
            raise ValueError(f"hypex_T deve essere in [0, 1), ricevuto: {hypex_T}")

        self.driver: DriverModel = driver
        self.cutoff_frequency: float = float(cutoff_frequency)
        self.expansion: str = expansion
        self.hypex_T: float = float(hypex_T)
        self.throat_area: float = float(throat_area)
        self.mouth_width: float = float(mouth_width)
        self.mouth_height: float = float(mouth_height)
        self.fold: int = int(fold)
        self.section_shape: str = section_shape
        self.n_sections: int = int(n_sections)
        self.throat_adapter: Optional[ThroatAdapter] = throat_adapter
        self.panel_thickness: float = float(panel_thickness)
        self.panel_material: str = panel_material
        self.c: float = float(c)
        self.origin: np.ndarray = (
            np.asarray(origin, dtype=float).reshape(3)
            if origin is not None else np.zeros(3)
        )

        # ── Calcoli derivati ──
        self.flare_rate: float = calculate_flare_rate(
            self.cutoff_frequency, c=self.c,
            expansion_type=self.expansion, hypex_T=self.hypex_T,
        )
        self.mouth_area: float = self.mouth_width * self.mouth_height
        self.length: float = calculate_horn_length(
            throat_area_m2=self.throat_area,
            mouth_area_m2=self.mouth_area,
            flare_rate_m=self.flare_rate,
            expansion_type=self.expansion,
            hypex_T=self.hypex_T,
        )

        # ── Generazione geometria ──
        self._sections: List[HornSectionGeometry] = self._build_sections()
        self._panels: List[Panel] = self._build_panels()
        self._ports: Dict[str, ConnectionPort] = self._build_ports()

    # ── Costruttori pubblici ─────────────────────────────────────────────────

    @classmethod
    def from_acoustics(
        cls,
        driver: DriverModel,
        cutoff_frequency: float,
        expansion: str = EXPANSION_HYPEX,
        *,
        hypex_T: float = 0.5,
        # Mouth: specifica 0, 1 o 2 di {aspect_ratio, width, height}
        mouth_aspect_ratio: Optional[float] = None,
        mouth_width: Optional[float] = None,
        mouth_height: Optional[float] = None,
        fold: int = 0,
        section_shape: str = "rectangular",
        throat_adapter: Optional[ThroatAdapter] = None,
        n_sections: int = DEFAULT_N_SECTIONS,
        panel_thickness: float = DEFAULT_PANEL_THICKNESS,
        panel_material: str = DEFAULT_PANEL_MATERIAL,
        c: float = SPEED_OF_SOUND,
        origin: Optional[np.ndarray] = None,
    ) -> "HornBlock":
        """
        Costruisce HornBlock partendo dai parametri acustici.

        Sincronizzazione mouth (3 parametri, ne specifichi al più 2):
          - 0 specificati  → area mouth ≈ λ²/π da Fc, aspect_ratio default 1.5
          - 1 specificato  → derivati da default aspect_ratio
          - 2 specificati  → terzo derivato
          - 3 specificati  → ValueError se incoerenti

        Args:
            driver: DriverModel selezionato dal database
            cutoff_frequency: Fc in Hz
            expansion: tipo espansione (exponential/conical/tractrix/hypex)
            hypex_T: parametro Salmon T (solo hypex), [0,1)
            mouth_aspect_ratio: width/height alla bocca
            mouth_width: larghezza bocca [m]
            mouth_height: altezza bocca [m]
            fold: 0 (dritta), 1 (1-fold), 2 (2-fold)
            section_shape: "rectangular" (entrambi i lati divergono mantenendo
                aspect_ratio) o "trapezoidal" (top/bottom paralleli, solo
                pareti laterali divergono)
            throat_adapter: opzionale, modifica area gola rispetto a Sd
            n_sections: discretizzazione profilo
            panel_thickness: spessore default pannelli [m]
            panel_material: materiale identificativo
            c: velocità del suono [m/s]
            origin: posizione iniziale gola nello spazio (default origine)
        """
        # Throat area (con eventuale adapter)
        if driver.sd <= 0.0:
            raise ValueError("Driver.sd deve essere > 0 per costruire una tromba")
        if throat_adapter is None:
            throat_area = driver.sd
        else:
            throat_area = throat_adapter.resolve_throat_area(driver.sd)

        # Mouth: sincronizzazione dei 3 parametri
        m_w, m_h, m_ar = cls._resolve_mouth_params(
            mouth_aspect_ratio=mouth_aspect_ratio,
            mouth_width=mouth_width,
            mouth_height=mouth_height,
            cutoff_frequency=cutoff_frequency,
            c=c,
        )

        return cls(
            driver=driver,
            cutoff_frequency=cutoff_frequency,
            expansion=expansion,
            hypex_T=hypex_T,
            throat_area=throat_area,
            mouth_width=m_w,
            mouth_height=m_h,
            fold=fold,
            section_shape=section_shape,
            n_sections=n_sections,
            throat_adapter=throat_adapter,
            panel_thickness=panel_thickness,
            panel_material=panel_material,
            c=c,
            origin=origin,
        )

    @classmethod
    def from_constraints(
        cls,
        driver: DriverModel,
        max_width: float,
        max_height: float,
        max_depth: float,
        *,
        fold: int = 1,
        expansion: str = EXPANSION_HYPEX,
        hypex_T: float = 0.5,
        section_shape: str = "rectangular",
        throat_adapter: Optional[ThroatAdapter] = None,
        optimize_for: str = "lowest_fc",
        fc_search_range: Tuple[float, float] = (25.0, 200.0),
        n_sections: int = DEFAULT_N_SECTIONS,
        panel_thickness: float = DEFAULT_PANEL_THICKNESS,
        panel_material: str = DEFAULT_PANEL_MATERIAL,
        c: float = SPEED_OF_SOUND,
        origin: Optional[np.ndarray] = None,
    ) -> "HornBlock":
        """
        Costruisce HornBlock partendo da vincoli dimensionali.

        L'ottimizzazione cerca la combinazione di Fc + dimensioni mouth
        che soddisfa il bounding box e massimizza il criterio scelto.

        optimize_for:
            "lowest_fc"        : minimizza Fc compatibile con i vincoli
            "spl_at_fc"        : massimizza area mouth (≈SPL@Fc)
            "flattest_response": Fc moderato + ratio bocca/gola conservativo

        Implementazione: scansione lineare semplice (questa fase 1).
        Sostituibile con scipy.optimize in futuro.
        """
        if not all(v > 0 for v in (max_width, max_height, max_depth)):
            raise ValueError("max_width/height/depth devono essere > 0")
        if optimize_for not in ("lowest_fc", "spl_at_fc", "flattest_response"):
            raise ValueError(f"optimize_for non valido: {optimize_for!r}")

        # Larghezza/altezza mouth massimi imposti dal bounding box.
        # Per fold=0: depth = horn_length (limita Fc minimo).
        # Per fold=1: depth ≈ length/2  (semplificato, asse piega a metà)
        # Per fold=2: depth ≈ length/3
        depth_to_length = {0: 1.0, 1: 2.0, 2: 3.0}[fold]
        max_horn_length = max_depth * depth_to_length

        m_w_cap = max_width
        m_h_cap = max_height
        mouth_area_cap = m_w_cap * m_h_cap

        # Scansione Fc
        fc_min, fc_max = fc_search_range
        if fc_min >= fc_max:
            raise ValueError("fc_search_range non valido")

        n_grid = 80
        fcs = np.linspace(fc_min, fc_max, n_grid)
        candidates: List[Tuple[float, float, float, float]] = []  # (score, Fc, m_w, m_h)

        if throat_adapter is None:
            S0 = driver.sd
        else:
            S0 = throat_adapter.resolve_throat_area(driver.sd)

        for fc in fcs:
            try:
                m = calculate_flare_rate(
                    fc, c=c, expansion_type=expansion, hypex_T=hypex_T,
                )
            except Exception:
                continue
            # Tentativo: usa l'intero bounding box per la mouth
            mouth_area_try = mouth_area_cap
            try:
                L = calculate_horn_length(
                    throat_area_m2=S0,
                    mouth_area_m2=mouth_area_try,
                    flare_rate_m=m,
                    expansion_type=expansion,
                    hypex_T=hypex_T,
                )
            except Exception:
                continue
            if L > max_horn_length or not np.isfinite(L):
                # Riduci mouth fino ad entrare nel limite di lunghezza
                # Cerca mouth_area che dà esattamente max_horn_length
                m_area_lo, m_area_hi = S0 * 1.001, mouth_area_try
                for _ in range(40):
                    mid = 0.5 * (m_area_lo + m_area_hi)
                    try:
                        L_mid = calculate_horn_length(
                            S0, mid, m, expansion, hypex_T,
                        )
                    except Exception:
                        m_area_hi = mid
                        continue
                    if L_mid > max_horn_length:
                        m_area_hi = mid
                    else:
                        m_area_lo = mid
                mouth_area_try = m_area_lo
                if mouth_area_try <= S0 * 1.01:
                    continue
                L = max_horn_length
            # Allochiamo mouth_area_try in width × height rispettando i cap
            ar = m_w_cap / m_h_cap  # aspect ratio dal bounding box
            m_h = float(np.sqrt(mouth_area_try / ar))
            m_w = ar * m_h
            if m_w > m_w_cap or m_h > m_h_cap:
                # caso limite: già al cap, lascia così
                m_w = min(m_w, m_w_cap)
                m_h = min(m_h, m_h_cap)
                mouth_area_try = m_w * m_h
            # Score
            if optimize_for == "lowest_fc":
                score = -fc
            elif optimize_for == "spl_at_fc":
                score = mouth_area_try
            else:  # flattest_response: ratio modesto, fc medio
                ratio = mouth_area_try / S0
                score = -abs(ratio - 4.0) - 0.01 * abs(fc - 0.5 * (fc_min + fc_max))
            candidates.append((score, fc, m_w, m_h))

        if not candidates:
            raise ValueError(
                "Nessun design valido trovato nei vincoli forniti. "
                "Aumenta max_depth o l'intervallo di ricerca Fc."
            )
        candidates.sort(key=lambda t: t[0], reverse=True)
        _, best_fc, best_w, best_h = candidates[0]

        return cls.from_acoustics(
            driver=driver,
            cutoff_frequency=best_fc,
            expansion=expansion,
            hypex_T=hypex_T,
            mouth_width=best_w,
            mouth_height=best_h,
            fold=fold,
            section_shape=section_shape,
            throat_adapter=throat_adapter,
            n_sections=n_sections,
            panel_thickness=panel_thickness,
            panel_material=panel_material,
            c=c,
            origin=origin,
        )

    # ── Sincronizzazione parametri mouth ────────────────────────────────────

    @staticmethod
    def _resolve_mouth_params(
        mouth_aspect_ratio: Optional[float],
        mouth_width: Optional[float],
        mouth_height: Optional[float],
        cutoff_frequency: float,
        c: float,
    ) -> Tuple[float, float, float]:
        """Restituisce (width, height, aspect_ratio) coerenti."""
        ar = mouth_aspect_ratio
        w = mouth_width
        h = mouth_height
        n_given = sum(v is not None for v in (ar, w, h))

        if n_given == 3:
            assert ar is not None and w is not None and h is not None
            if abs(w / h - ar) > 1e-3 * ar:
                raise ValueError(
                    f"mouth params incoerenti: width/height={w/h:.4f} ≠ "
                    f"aspect_ratio={ar:.4f}"
                )
            return float(w), float(h), float(ar)

        if n_given == 0:
            # Area da Fc: λ = c/fc; mouth area target ≈ λ²/π (criterio classico)
            wavelength = c / cutoff_frequency
            mouth_area = wavelength ** 2 / np.pi
            ar = DEFAULT_ASPECT_RATIO
            h = float(np.sqrt(mouth_area / ar))
            w = ar * h
            return w, h, ar

        if n_given == 1:
            ar_eff = ar if ar is not None else DEFAULT_ASPECT_RATIO
            if w is not None:
                return float(w), float(w / ar_eff), float(ar_eff)
            if h is not None:
                return float(ar_eff * h), float(h), float(ar_eff)
            # solo aspect_ratio: deriva area da Fc
            assert ar is not None
            wavelength = c / cutoff_frequency
            mouth_area = wavelength ** 2 / np.pi
            h_calc = float(np.sqrt(mouth_area / ar))
            w_calc = ar * h_calc
            return w_calc, h_calc, float(ar)

        # n_given == 2
        if ar is None:
            assert w is not None and h is not None
            return float(w), float(h), float(w / h)
        if w is None:
            assert ar is not None and h is not None
            return float(ar * h), float(h), float(ar)
        # h is None
        assert ar is not None and w is not None
        return float(w), float(w / ar), float(ar)

    # ── Setter runtime per mouth (mantengono aspect_ratio se richiesto) ─────

    def set_mouth_width(self, width: float) -> None:
        """Aggiorna larghezza mouth, ricalcola altezza per mantenere aspect_ratio."""
        if width <= 0:
            raise ValueError("width deve essere > 0")
        ar = self.mouth_width / self.mouth_height
        self._reinit_mouth(width, width / ar)

    def set_mouth_height(self, height: float) -> None:
        """Aggiorna altezza mouth, ricalcola larghezza per mantenere aspect_ratio."""
        if height <= 0:
            raise ValueError("height deve essere > 0")
        ar = self.mouth_width / self.mouth_height
        self._reinit_mouth(ar * height, height)

    def set_mouth_aspect_ratio(self, ar: float, *, keep: str = "height") -> None:
        """Aggiorna aspect_ratio mantenendo o l'altezza o la larghezza."""
        if ar <= 0:
            raise ValueError("aspect_ratio deve essere > 0")
        if keep == "height":
            self._reinit_mouth(ar * self.mouth_height, self.mouth_height)
        elif keep == "width":
            self._reinit_mouth(self.mouth_width, self.mouth_width / ar)
        else:
            raise ValueError("keep deve essere 'height' o 'width'")

    def _reinit_mouth(self, new_w: float, new_h: float) -> None:
        self.mouth_width = float(new_w)
        self.mouth_height = float(new_h)
        self.mouth_area = new_w * new_h
        self.length = calculate_horn_length(
            throat_area_m2=self.throat_area,
            mouth_area_m2=self.mouth_area,
            flare_rate_m=self.flare_rate,
            expansion_type=self.expansion,
            hypex_T=self.hypex_T,
        )
        self._sections = self._build_sections()
        self._panels = self._build_panels()
        self._ports = self._build_ports()

    # ── Costruzione sezioni profilo ──────────────────────────────────────────

    def _section_dims(self, area: float, x_norm: float) -> Tuple[float, float]:
        """
        Da area sezione → (width, height) in funzione di section_shape.

        rectangular: aspect_ratio cost. = aspect_ratio della bocca
                     w = sqrt(area * AR), h = sqrt(area / AR)
        trapezoidal: height costante = mouth_height, width = area / height
                     (top/bottom paralleli; pareti laterali divergono)
        """
        if self.section_shape == "rectangular":
            ar = self.mouth_width / self.mouth_height
            h = float(np.sqrt(area / ar))
            w = ar * h
            return w, h
        # trapezoidal: altezza costante
        h = self.mouth_height
        w = area / h
        return w, h

    def _build_sections(self) -> List[HornSectionGeometry]:
        """
        Genera le N sezioni del profilo lungo l'asse della tromba.

        L'asse è "srotolato": x_axial va da 0 (gola) a self.length (bocca).
        Per fold=0 le sezioni sono allineate lungo +Z dal punto origin.
        Per fold=1/2 il fold è applicato in `_apply_fold_transform`.
        """
        N = self.n_sections
        xs = np.linspace(0.0, self.length, N)
        sections: List[HornSectionGeometry] = []

        for x in xs:
            area = area_at_position(
                x_m=x,
                throat_area_m2=self.throat_area,
                flare_rate_m=self.flare_rate,
                expansion_type=self.expansion,
                hypex_T=self.hypex_T,
            )
            # Limita a mouth_area per evitare overshoot numerico
            if x >= self.length:
                area = self.mouth_area
            w, h = self._section_dims(area, x / self.length if self.length > 0 else 0.0)

            # Posizionamento in spazio "srotolato" (asse +Z)
            center_unfolded = np.array([0.0, 0.0, x])
            normal_unfolded = np.array([0.0, 0.0, 1.0])
            verts_unfolded = self._section_quad(
                center_unfolded, normal_unfolded, w, h
            )

            # Applica trasformazione di fold
            center, normal, verts = self._apply_fold_transform(
                x, center_unfolded, normal_unfolded, verts_unfolded,
            )
            # Sposta nel sistema globale (origin)
            center = center + self.origin
            verts = verts + self.origin

            sections.append(HornSectionGeometry(
                x_axial=float(x),
                area=float(area),
                width=float(w),
                height=float(h),
                center=center,
                normal=normal,
                vertices=verts,
            ))
        return sections

    @staticmethod
    def _section_quad(
        center: np.ndarray, normal: np.ndarray, w: float, h: float,
    ) -> np.ndarray:
        """Costruisce 4 vertici di un rettangolo centrato in `center` con
        normale `normal`. Larghezza lungo X, altezza lungo Y (nel sistema
        non-folded). Ordine antiorario visto da -normal.
        """
        # Base ortonormale: assume normal ≈ Z, x_local = X, y_local = Y
        # Per fold semplice (rotazione attorno a Y) questa assunzione regge
        # perché ruotiamo nel piano XZ → larghezza resta lungo X.
        # Per generalità futura, ricaviamo basi:
        n = normal / np.linalg.norm(normal)
        if abs(n[1]) < 0.9:
            ref = np.array([0.0, 1.0, 0.0])
        else:
            ref = np.array([1.0, 0.0, 0.0])
        x_loc = np.cross(ref, n)
        x_loc /= np.linalg.norm(x_loc)
        y_loc = np.cross(n, x_loc)
        y_loc /= np.linalg.norm(y_loc)
        hw, hh = w * 0.5, h * 0.5
        return np.array([
            center - hw * x_loc - hh * y_loc,
            center + hw * x_loc - hh * y_loc,
            center + hw * x_loc + hh * y_loc,
            center - hw * x_loc + hh * y_loc,
        ])

    def _apply_fold_transform(
        self,
        x_axial: float,
        center: np.ndarray,
        normal: np.ndarray,
        verts: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Applica la piegatura dell'asse della tromba.

        fold=0: identità.
        fold=1: l'asse piega di 180° a x = L/2 (lungo asse Y, verso -Z).
        fold=2: due piegature a x = L/3 e 2L/3.

        Implementazione semplificata: riflessione/rotazione rigida del
        sistema locale in segmenti. Le sezioni mantengono area e dimensioni;
        si genereranno le paratie di piegatura come pannelli interni a parte.
        """
        if self.fold == 0:
            return center, normal, verts

        L = self.length
        if self.fold == 1:
            # Segmento 1: 0 → L/2 lungo +Z
            # Segmento 2: L/2 → L lungo -Z spostato in +Y di mouth_height
            x0 = L / 2.0
            if x_axial <= x0:
                return center, normal, verts
            # Riflessione: nuovo asse va a -Z, partendo da z=x0, traslato in +Y
            new_z = x0 - (x_axial - x0)
            shift_y = self.mouth_height
            new_center = np.array([center[0], center[1] + shift_y, new_z])
            new_normal = np.array([0.0, 0.0, -1.0])
            # Rotazione 180° attorno asse Y dei vertici intorno a (0, 0, x0)
            rotated = self._rotate_y_180(verts, pivot_z=x0)
            rotated[:, 1] += shift_y
            return new_center, new_normal, rotated

        if self.fold == 2:
            x1 = L / 3.0
            x2 = 2.0 * L / 3.0
            if x_axial <= x1:
                return center, normal, verts
            if x_axial <= x2:
                # Segmento 2: -Z dopo prima piega, traslato in +Y
                new_z = x1 - (x_axial - x1)
                shift_y = self.mouth_height
                new_center = np.array([center[0], center[1] + shift_y, new_z])
                new_normal = np.array([0.0, 0.0, -1.0])
                rotated = self._rotate_y_180(verts, pivot_z=x1)
                rotated[:, 1] += shift_y
                return new_center, new_normal, rotated
            # Segmento 3: torna a +Z dopo seconda piega, traslato +Y di 2*mouth_height
            # Nel segmento 2 a x=x2, z = x1 - (x2 - x1) = 2x1 - x2 = -L/3 (negativo!)
            # ricalibriamo: posizione di pivot per la 2a piega
            z_at_x2 = x1 - (x2 - x1)  # punto in cui avviene 2a piega lungo Z
            new_z = z_at_x2 + (x_axial - x2)
            shift_y = 2.0 * self.mouth_height
            new_center = np.array([center[0], center[1] + shift_y, new_z])
            new_normal = np.array([0.0, 0.0, 1.0])
            # Doppia rotazione → identità su normale, ma posizione ricalcolata
            rotated = self._rotate_y_180(verts, pivot_z=x1)  # prima piega
            rotated = self._rotate_y_180(rotated, pivot_z=z_at_x2)  # seconda piega
            rotated[:, 1] += shift_y
            return new_center, new_normal, rotated

        return center, normal, verts

    @staticmethod
    def _rotate_y_180(verts: np.ndarray, pivot_z: float) -> np.ndarray:
        """Rotazione 180° attorno a asse Y passante per (0,*,pivot_z)."""
        out = verts.copy()
        out[:, 0] = -out[:, 0]
        out[:, 2] = 2.0 * pivot_z - out[:, 2]
        return out

    # ── Costruzione pannelli costruttivi ────────────────────────────────────

    def _build_panels(self) -> List[Panel]:
        """
        Genera la lista pannelli costruttivi.

        Per ora: pannelli "side", "top", "bottom" come strisce di quadrilateri
        tra sezioni adiacenti (uno per intervallo). Per pannelli reali in
        legno, in fase 3 verranno aggregati e linearizzati.

        Pannelli speciali:
          - throat_baffle: pannello di chiusura alla gola con cutout driver
          - throat_adapter: se presente, pannello adattatore separato
          - mouth_frame: cornice della bocca (opzionale, qui ne creiamo uno
            simbolico)
          - fold_baffle_N: paratie di piegatura interne (fold ≥ 1)
        """
        panels: List[Panel] = []
        secs = self._sections

        # Strisce laterali tra sezioni adiacenti
        # Vertici di sezione (ordine antiorario): 0=BL, 1=BR, 2=TR, 3=TL
        # bottom = 0-1, right = 1-2, top = 2-3, left = 3-0
        for i in range(len(secs) - 1):
            a = secs[i].vertices
            b = secs[i + 1].vertices
            panels.append(Panel(
                name=f"bottom[{i}]",
                vertices=np.array([a[0], a[1], b[1], b[0]]),
                thickness=self.panel_thickness,
                material=self.panel_material,
            ))
            panels.append(Panel(
                name=f"side_R[{i}]",
                vertices=np.array([a[1], a[2], b[2], b[1]]),
                thickness=self.panel_thickness,
                material=self.panel_material,
            ))
            panels.append(Panel(
                name=f"top[{i}]",
                vertices=np.array([a[2], a[3], b[3], b[2]]),
                thickness=self.panel_thickness,
                material=self.panel_material,
            ))
            panels.append(Panel(
                name=f"side_L[{i}]",
                vertices=np.array([a[3], a[0], b[0], b[3]]),
                thickness=self.panel_thickness,
                material=self.panel_material,
            ))

        # Throat baffle (chiude la gola, contiene cutout driver)
        throat_v = secs[0].vertices
        driver_cutout = {
            "type": "circular",
            "diameter": 2.0 * float(np.sqrt(self.driver.sd / np.pi)),
            "center_local": [0.0, 0.0],
            "purpose": "driver_mount",
            "driver_model": self.driver.model,
        }
        panels.append(Panel(
            name="throat_baffle",
            vertices=throat_v.copy(),
            thickness=self.panel_thickness,
            material=self.panel_material,
            cutouts=[driver_cutout] if self.throat_adapter is None else [],
        ))

        # Throat adapter (se presente): pannello con doppio cutout
        if self.throat_adapter is not None and self.throat_adapter.mode != "match":
            # Posizionato self.throat_adapter.adapter_length DIETRO la gola
            n = secs[0].normal
            offset = -self.throat_adapter.adapter_length * n
            adapter_v = throat_v + offset
            panels.append(Panel(
                name="throat_adapter",
                vertices=adapter_v,
                thickness=self.panel_thickness,
                material=self.panel_material,
                cutouts=[
                    {
                        "type": "circular",
                        "diameter": 2.0 * float(np.sqrt(self.driver.sd / np.pi)),
                        "center_local": [0.0, 0.0],
                        "purpose": "driver_mount",
                        "driver_model": self.driver.model,
                    },
                    {
                        "type": "rectangular",
                        "width": secs[0].width,
                        "height": secs[0].height,
                        "center_local": [0.0, 0.0],
                        "purpose": "horn_throat",
                    },
                ],
                is_internal=True,
            ))

        # Mouth frame (simbolico): pannello a cornice attorno alla bocca
        # Lo rappresentiamo come pannello pieno con cutout rettangolare
        # Verrà tagliato in fase di generazione 3D
        mouth_v = secs[-1].vertices
        panels.append(Panel(
            name="mouth_frame",
            vertices=mouth_v.copy(),
            thickness=self.panel_thickness,
            material=self.panel_material,
            cutouts=[{
                "type": "rectangular",
                "width": secs[-1].width,
                "height": secs[-1].height,
                "center_local": [0.0, 0.0],
                "purpose": "mouth_opening",
            }],
        ))

        # Fold baffles (paratie interne di piegatura): semplificate
        # Posizione: piano orizzontale che separa i segmenti folded
        if self.fold >= 1:
            # Paratia 1: a y = mouth_height/2, copre estensione folded
            # Approssimazione: rettangolo che copre l'overlap dei due segmenti
            x_max = self.mouth_width / 2.0 * 1.2  # margine
            z_lo = -self.length / 2.0 * 1.2
            z_hi = self.length / 2.0 * 1.2
            y_baffle = self.mouth_height / 2.0
            v = np.array([
                [-x_max, y_baffle, z_lo],
                [+x_max, y_baffle, z_lo],
                [+x_max, y_baffle, z_hi],
                [-x_max, y_baffle, z_hi],
            ]) + self.origin
            panels.append(Panel(
                name="fold_baffle_1",
                vertices=v,
                thickness=self.panel_thickness,
                material=self.panel_material,
                is_internal=True,
            ))
        if self.fold >= 2:
            x_max = self.mouth_width / 2.0 * 1.2
            z_lo = -self.length / 2.0 * 1.2
            z_hi = self.length / 2.0 * 1.2
            y_baffle = 1.5 * self.mouth_height
            v = np.array([
                [-x_max, y_baffle, z_lo],
                [+x_max, y_baffle, z_lo],
                [+x_max, y_baffle, z_hi],
                [-x_max, y_baffle, z_hi],
            ]) + self.origin
            panels.append(Panel(
                name="fold_baffle_2",
                vertices=v,
                thickness=self.panel_thickness,
                material=self.panel_material,
                is_internal=True,
            ))

        return panels

    def _build_ports(self) -> Dict[str, ConnectionPort]:
        first = self._sections[0]
        last = self._sections[-1]
        return {
            "throat": ConnectionPort(
                name="throat",
                position=first.center,
                normal=-first.normal,  # uscente verso il driver
                area=first.area,
                shape="rectangular",
                width=first.width,
                height=first.height,
            ),
            "mouth": ConnectionPort(
                name="mouth",
                position=last.center,
                normal=last.normal,
                area=last.area,
                shape="rectangular",
                width=last.width,
                height=last.height,
            ),
        }

    # ── API Block ────────────────────────────────────────────────────────────

    @property
    def panels(self) -> List[Panel]:
        return self._panels

    @property
    def connection_ports(self) -> Dict[str, ConnectionPort]:
        return self._ports

    @property
    def sections(self) -> List[HornSectionGeometry]:
        return self._sections

    @property
    def bounding_box(self) -> Tuple[float, float, float]:
        """(width, height, depth) effettivo dopo fold."""
        all_verts = np.concatenate([s.vertices for s in self._sections], axis=0)
        mins = all_verts.min(axis=0)
        maxs = all_verts.max(axis=0)
        ext = maxs - mins
        return (float(ext[0]), float(ext[1]), float(ext[2]))

    @property
    def internal_volume(self) -> float:
        """Volume aria interno (integrazione trapezoidale di area lungo asse)."""
        xs = np.array([s.x_axial for s in self._sections])
        areas = np.array([s.area for s in self._sections])
        # numpy >= 2.0 rinomina trapz -> trapezoid
        trap = getattr(np, "trapezoid", None) or np.trapz  # type: ignore[attr-defined]
        return float(trap(areas, xs))

    @property
    def driver_mount(self) -> Dict[str, Any]:
        """Informazioni di mounting del driver alla gola/adapter."""
        first = self._sections[0]
        return {
            "driver_model": self.driver.model,
            "driver_sd": self.driver.sd,
            "throat_area": self.throat_area,
            "mounted_on": "throat_adapter" if (
                self.throat_adapter is not None
                and self.throat_adapter.mode != "match"
            ) else "throat_baffle",
            "position": first.center.tolist(),
            "normal": first.normal.tolist(),
        }

    @property
    def geometry_implementation_status(self) -> Dict[str, Any]:
        """Riepilogo stato di completezza della geometria generata.

        Esposto per trasparenza durante la fase di sviluppo: certi elementi
        (paratie fold, mouth frame come solido) sono semplificati e verranno
        precisati nel Layer 3 (panel_generator + build123d).
        """
        return {
            "horn_walls": "complete",
            "throat_baffle": "complete",
            "mouth_frame": "simplified_placeholder",
            "throat_adapter": "geometric_placeholder",
            "fold_baffles": "approximate" if self.fold > 0 else "n/a",
            "build123d_solid": "not_implemented_yet",
        }

    def validate(self) -> List[ValidationWarning]:
        warnings: List[ValidationWarning] = []

        # 1. Coerenza driver Sd vs throat
        sd = self.driver.sd
        if sd <= 0:
            warnings.append(ValidationWarning(
                Severity.ERROR, "DRIVER_SD_INVALID",
                "Driver.sd <= 0: parametro mancante o incoerente.",
            ))
        else:
            ratio = self.throat_area / sd
            if self.throat_adapter is None and abs(ratio - 1.0) > 0.05:
                warnings.append(ValidationWarning(
                    Severity.WARNING, "THROAT_SD_MISMATCH",
                    f"throat_area ({self.throat_area*1e4:.1f} cm²) ≠ "
                    f"driver Sd ({sd*1e4:.1f} cm²) e nessun throat_adapter "
                    f"presente.",
                ))
            if ratio < 0.25:
                warnings.append(ValidationWarning(
                    Severity.WARNING, "COMPRESSION_RATIO_HIGH",
                    f"Compression ratio Sd/St = {1.0/ratio:.2f}× molto elevato; "
                    f"verifica xmax e potenza alle alte frequenze.",
                ))

        # 2. Vincolo Olson 1957: ratio area sezioni adiacenti ≤ 4
        for i in range(len(self._sections) - 1):
            a0 = self._sections[i].area
            a1 = self._sections[i + 1].area
            if a0 > 0 and a1 / a0 > MAX_AREA_RATIO_ADJACENT:
                warnings.append(ValidationWarning(
                    Severity.WARNING, "AREA_RATIO_TOO_HIGH",
                    f"Sezioni adiacenti con ratio {a1/a0:.2f} > "
                    f"{MAX_AREA_RATIO_ADJACENT} (Olson 1957). "
                    f"Aumenta n_sections o riduci variazione locale.",
                    location=f"section[{i}->{i+1}]",
                ))
                break  # un solo avviso per non spammare

        # 3. Mouth area vs Fc — criteri pratici
        # target classico: λ²/π  (caricamento ottimale, raro nei sub reali)
        # accettabile:    λ²/(4π) (criterio rilassato comune)
        # patologico:     λ²/(16π) → la bocca è < λ/2 in entrambe le dimensioni
        wavelength = self.c / self.cutoff_frequency
        mouth_target = wavelength ** 2 / np.pi
        mouth_acceptable = wavelength ** 2 / (4.0 * np.pi)
        mouth_critical = wavelength ** 2 / (16.0 * np.pi)
        if self.mouth_area < mouth_critical:
            warnings.append(ValidationWarning(
                Severity.ERROR, "MOUTH_TOO_SMALL",
                f"mouth_area {self.mouth_area:.3f} m² < soglia critica "
                f"λ²/(16π) = {mouth_critical:.3f} m² @ Fc={self.cutoff_frequency} Hz. "
                f"La tromba non caricherà alla frequenza di taglio.",
            ))
        elif self.mouth_area < mouth_acceptable:
            warnings.append(ValidationWarning(
                Severity.WARNING, "MOUTH_UNDERSIZED",
                f"mouth_area {self.mouth_area:.3f} m² < limite pratico "
                f"λ²/(4π) = {mouth_acceptable:.3f} m² @ Fc={self.cutoff_frequency} Hz. "
                f"Roll-off prematuro probabile.",
            ))
        elif self.mouth_area < mouth_target:
            warnings.append(ValidationWarning(
                Severity.INFO, "MOUTH_BELOW_TARGET",
                f"mouth_area {self.mouth_area:.3f} m² < target "
                f"λ²/π = {mouth_target:.3f} m² @ Fc={self.cutoff_frequency} Hz. "
                f"Caricamento subottimale, ma accettabile.",
            ))

        # 4. ThroatAdapter: profilo coerente
        if self.throat_adapter is not None and self.throat_adapter.mode == "expand":
            if self.throat_area <= self.driver.sd:
                warnings.append(ValidationWarning(
                    Severity.WARNING, "ADAPTER_MODE_MISMATCH",
                    "ThroatAdapter mode='expand' ma throat_area ≤ Sd.",
                ))
        if self.throat_adapter is not None and self.throat_adapter.mode == "reduce":
            if self.throat_area >= self.driver.sd:
                warnings.append(ValidationWarning(
                    Severity.WARNING, "ADAPTER_MODE_MISMATCH",
                    "ThroatAdapter mode='reduce' ma throat_area ≥ Sd.",
                ))

        # 5. Lunghezza tromba ragionevole
        if not np.isfinite(self.length) or self.length <= 0.0:
            warnings.append(ValidationWarning(
                Severity.ERROR, "HORN_LENGTH_INVALID",
                f"Lunghezza tromba calcolata non valida: {self.length}. "
                f"Verifica throat_area, mouth_area e flare_rate.",
            ))

        return warnings

    # ── Serializzazione ──────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_type": self.block_type,
            "driver": {
                "manufacturer": self.driver.manufacturer,
                "model": self.driver.model,
                "sd": self.driver.sd,
                # nota: per ricostruzione reale si dovrà fare lookup nel DB
            },
            "cutoff_frequency": self.cutoff_frequency,
            "expansion": self.expansion,
            "hypex_T": self.hypex_T,
            "throat_area": self.throat_area,
            "mouth_width": self.mouth_width,
            "mouth_height": self.mouth_height,
            "mouth_area": self.mouth_area,
            "fold": self.fold,
            "section_shape": self.section_shape,
            "n_sections": self.n_sections,
            "throat_adapter": (
                self.throat_adapter.to_dict() if self.throat_adapter else None
            ),
            "panel_thickness": self.panel_thickness,
            "panel_material": self.panel_material,
            "c": self.c,
            "origin": self.origin.tolist(),
            # derivati (informativi)
            "flare_rate": self.flare_rate,
            "length": self.length,
            "bounding_box": list(self.bounding_box),
            "internal_volume": self.internal_volume,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], driver: DriverModel) -> "HornBlock":
        """
        Ricostruisce HornBlock dal dizionario serializzato.

        Args:
            data: dict prodotto da to_dict()
            driver: DriverModel risolto esternamente (lookup DB) — non
                memorizzato completamente nel dict perché può avere
                molti parametri non rilevanti per la geometria.
        """
        ta_data = data.get("throat_adapter")
        ta = ThroatAdapter(**ta_data) if ta_data else None
        return cls(
            driver=driver,
            cutoff_frequency=data["cutoff_frequency"],
            expansion=data["expansion"],
            hypex_T=data.get("hypex_T", 0.5),
            throat_area=data["throat_area"],
            mouth_width=data["mouth_width"],
            mouth_height=data["mouth_height"],
            fold=data.get("fold", 0),
            section_shape=data.get("section_shape", "rectangular"),
            n_sections=data.get("n_sections", DEFAULT_N_SECTIONS),
            throat_adapter=ta,
            panel_thickness=data.get("panel_thickness", DEFAULT_PANEL_THICKNESS),
            panel_material=data.get("panel_material", DEFAULT_PANEL_MATERIAL),
            c=data.get("c", SPEED_OF_SOUND),
            origin=np.asarray(data.get("origin", [0, 0, 0])),
        )
