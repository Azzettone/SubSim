"""
AssemblyModel — modello dati MVC centrale per la GUI.

Wrappa un :class:`Assembly` (da ``btk_speaker_designer.blocks``) e i parametri
correnti del progetto. Espone signals Qt che le viste osservano per
ricostruire l'interfaccia quando qualcosa cambia.

Architettura::

    InputPanel (View)  ─── set_*() ──▶  AssemblyModel  ─── solids_rebuilt ──▶  Viewport3DWidget (View)
                                              │
                                              ├─ HornBlock
                                              ├─ ChamberBlock
                                              ├─ PortBlock (opz)
                                              └─ DriverBlock

Il model è l'unica fonte di verità dello stato del progetto.
Le viste non comunicano fra loro: solo il model.

NOTA: la generazione dei solidi 3D è LAZY (build123d è lento).
Chiamando ``rebuild_solids()`` si forza la rigenerazione e si emette
``solids_rebuilt``. Il flag ``auto_rebuild_solids`` (default True) la
fa avvenire automaticamente dentro ``rebuild()``.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Optional

import numpy as np

try:
    from PyQt5.QtCore import QObject, pyqtSignal as Signal
except ImportError:                                   # pragma: no cover
    from PySide6.QtCore import QObject, Signal       # type: ignore

from btk_speaker_designer.blocks import (
    Assembly,
    ChamberBlock,
    DriverBlock,
    HornBlock,
    PortBlock,
)
from btk_speaker_designer.core.constants import (
    DEFAULT_FCUTOFF,
    EXPANSION_HYPEX,
    GEOMETRY_STRAIGHT,
    SPEAKER_TYPE_SUB,
)
from btk_speaker_designer.core.driver_model import DriverModel


# ---------------------------------------------------------------------------
# Parametri serializzabili
# ---------------------------------------------------------------------------
@dataclass
class HornParams:
    """Parametri tromba editabili dalla GUI."""
    cutoff_frequency: float = DEFAULT_FCUTOFF
    expansion: str = EXPANSION_HYPEX
    fold: int = 0                       # 0 / 1 / 2
    hypex_T: float = 0.5
    mouth_width: Optional[float] = None  # m, None = auto da Fc
    mouth_height: Optional[float] = None
    mouth_aspect_ratio: Optional[float] = None
    section_shape: str = "rectangular"
    n_sections: int = 25


@dataclass
class ChamberParams:
    """Parametri cabinet editabili dalla GUI."""
    enabled: bool = True
    width: float = 0.60     # m
    height: float = 0.60    # m
    depth: float = 0.50     # m
    panel_thickness: float = 0.018
    rear_width: Optional[float] = None
    shape: str = "rectangular"


@dataclass
class PortParams:
    """Parametri porta bass-reflex (opzionale)."""
    enabled: bool = False
    diameter: float = 0.10      # m (porta circolare)
    # Lunghezza fissa; se fb_hz>0 e vbox_l>0 viene ricalcolata via Helmholtz
    length: float = 0.20        # m
    fb_hz: float = 0.0          # Hz, accordo Helmholtz (0 = usa length diretto)
    vbox_l: float = 0.0         # L, volume camera (0 = autodetect da ChamberBlock)
    # Posizione della porta sul cabinet
    face: str = "rear"          # "rear"|"front"|"bottom"|"top"|"left"|"right"
    offset_x: float = 0.0       # m — offset laterale sul piano della faccia
    offset_y: float = 0.0       # m — offset verticale sul piano della faccia
    # Numero di porte identiche
    n_ports: int = 1


# ---------------------------------------------------------------------------
# Modello principale
# ---------------------------------------------------------------------------
class AssemblyModel(QObject):
    """
    Modello dati MVC della GUI: unica fonte di verità del progetto corrente.

    Signals:
        speaker_type_changed(str):       cambiato tipo (SUB/CD/FULLRANGE)
        driver_changed(DriverModel):     cambiato driver selezionato
        horn_params_changed():           cambiati parametri tromba
        chamber_params_changed():        cambiati parametri cabinet
        port_params_changed():           cambiati parametri porta
        assembly_changed():              ricostruito assembly (qualsiasi modifica)
        solids_rebuilt(dict):            rigenerati solidi 3D ({name: solid})
        validation_failed(str):          errore in fase di build (messaggio)
    """

    speaker_type_changed = Signal(str)
    driver_changed = Signal(object)            # DriverModel
    horn_params_changed = Signal()
    chamber_params_changed = Signal()
    port_params_changed = Signal()
    assembly_changed = Signal()
    solids_rebuilt = Signal(dict)              # {name: build123d Solid}
    validation_failed = Signal(str)

    # Notifica anche durante la fase di rebuild (utile per status bar):
    rebuild_started = Signal()
    rebuild_finished = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._speaker_type: str = SPEAKER_TYPE_SUB
        self._geometry_type: str = GEOMETRY_STRAIGHT
        self._driver: Optional[DriverModel] = None
        self._horn_params: HornParams = HornParams()
        self._chamber_params: ChamberParams = ChamberParams()
        self._port_params: PortParams = PortParams()

        # Stato derivato (ricostruito):
        self._assembly: Optional[Assembly] = None
        self._horn_block: Optional[HornBlock] = None
        self._chamber_block: Optional[ChamberBlock] = None
        self._port_block: Optional[PortBlock] = None
        self._driver_block: Optional[DriverBlock] = None
        self._solids_cache: Dict[str, Any] = {}

        # Comportamento:
        self.auto_rebuild_solids: bool = True

    # ------------------------------------------------------------------ getters
    @property
    def speaker_type(self) -> str:
        return self._speaker_type

    @property
    def geometry_type(self) -> str:
        return self._geometry_type

    @property
    def driver(self) -> Optional[DriverModel]:
        return self._driver

    @property
    def horn_params(self) -> HornParams:
        return self._horn_params

    @property
    def chamber_params(self) -> ChamberParams:
        return self._chamber_params

    @property
    def port_params(self) -> PortParams:
        return self._port_params

    @property
    def assembly(self) -> Optional[Assembly]:
        return self._assembly

    @property
    def horn_block(self) -> Optional[HornBlock]:
        return self._horn_block

    @property
    def chamber_block(self) -> Optional[ChamberBlock]:
        return self._chamber_block

    @property
    def port_block(self) -> Optional[PortBlock]:
        return self._port_block

    @property
    def driver_block(self) -> Optional[DriverBlock]:
        return self._driver_block

    @property
    def solids(self) -> Dict[str, Any]:
        """Dizionario {name: solid} dei solidi 3D (lazy, può essere vuoto)."""
        return dict(self._solids_cache)

    def has_valid_assembly(self) -> bool:
        return self._assembly is not None

    # ------------------------------------------------------------------ setters
    def set_speaker_type(self, value: str) -> None:
        if value == self._speaker_type:
            return
        self._speaker_type = value
        self.speaker_type_changed.emit(value)
        self._maybe_rebuild()

    def set_geometry_type(self, value: str) -> None:
        if value == self._geometry_type:
            return
        self._geometry_type = value
        # Sincronizza fold della tromba con la geometria scelta
        from btk_speaker_designer.core.constants import (
            GEOMETRY_2FOLDED,
            GEOMETRY_FOLDED,
            GEOMETRY_STRAIGHT,
        )
        fold_map = {GEOMETRY_STRAIGHT: 0, GEOMETRY_FOLDED: 1, GEOMETRY_2FOLDED: 2}
        self._horn_params = replace(self._horn_params, fold=fold_map.get(value, 0))
        self.horn_params_changed.emit()
        self._maybe_rebuild()

    def set_driver(self, driver: Optional[DriverModel]) -> None:
        if driver is self._driver:
            return
        self._driver = driver
        self.driver_changed.emit(driver)
        self._maybe_rebuild()

    def update_horn_params(self, **kwargs: Any) -> None:
        """Aggiorna uno o più campi di HornParams (replace su dataclass)."""
        if not kwargs:
            return
        self._horn_params = replace(self._horn_params, **kwargs)
        self.horn_params_changed.emit()
        self._maybe_rebuild()

    def update_chamber_params(self, **kwargs: Any) -> None:
        if not kwargs:
            return
        self._chamber_params = replace(self._chamber_params, **kwargs)
        self.chamber_params_changed.emit()
        self._maybe_rebuild()

    def update_port_params(self, **kwargs: Any) -> None:
        if not kwargs:
            return
        self._port_params = replace(self._port_params, **kwargs)
        self.port_params_changed.emit()
        self._maybe_rebuild()

    # ------------------------------------------------------------------ rebuild
    def rebuild(self) -> bool:
        """
        Ricostruisce assembly + blocchi dai parametri correnti.

        Returns:
            True se l'assembly è valido, False altrimenti (in tal caso
            ``validation_failed`` è già stato emesso).
        """
        self.rebuild_started.emit()
        try:
            # Driver: se mancante, niente assembly possibile
            if self._driver is None:
                self._reset_blocks()
                self.assembly_changed.emit()
                return False

            # HornBlock dai parametri acustici
            hp = self._horn_params
            # Nota: cabinet_depth non viene impostato qui automaticamente.
            # Il ChamberBlock è la camera posteriore del driver (z < 0),
            # non il cabinet della tromba (che si estende a z > 0).
            # Il fold_depth è calcolato internamente come L/(fold+1).
            try:
                horn = HornBlock.from_acoustics(
                    driver=self._driver,
                    cutoff_frequency=hp.cutoff_frequency,
                    expansion=hp.expansion,
                    hypex_T=hp.hypex_T,
                    mouth_aspect_ratio=hp.mouth_aspect_ratio,
                    mouth_width=hp.mouth_width,
                    mouth_height=hp.mouth_height,
                    fold=hp.fold,
                    section_shape=hp.section_shape,
                    n_sections=hp.n_sections,
                )
            except Exception as exc:
                self._reset_blocks()
                self.validation_failed.emit(f"HornBlock: {exc}")
                self.assembly_changed.emit()
                return False

            # ChamberBlock (opzionale) — posizionata DIETRO la gola della tromba.
            # Camera: front-face a z=0 (= gola tromba), si estende verso -Z.
            # Centrata verticalmente su Y (tromba è centrata a y=0).
            chamber: Optional[ChamberBlock] = None
            if self._chamber_params.enabled:
                cp = self._chamber_params
                try:
                    # origin=[0, -H/2, -D] → front a z=0, centrata in Y
                    chamber_origin = np.array([0.0, -cp.height / 2, -cp.depth])
                    if cp.shape == "trapezoidal" and cp.rear_width is not None:
                        chamber = ChamberBlock(
                            width=cp.width, height=cp.height, depth=cp.depth,
                            shape="trapezoidal", rear_width=cp.rear_width,
                            panel_thickness=cp.panel_thickness,
                            origin=chamber_origin,
                        )
                    else:
                        chamber = ChamberBlock.from_dimensions(
                            width=cp.width, height=cp.height, depth=cp.depth,
                            panel_thickness=cp.panel_thickness,
                            origin=chamber_origin,
                        )
                except Exception as exc:
                    self.validation_failed.emit(f"ChamberBlock: {exc}")
                    chamber = None

            # PortBlock (opzionale)
            # La posizione viene calcolata dalla faccia del cabinet selezionata.
            port: Optional[PortBlock] = None
            if self._port_params.enabled:
                pp = self._port_params
                try:
                    # Posizione e normale in base alla faccia del cabinet
                    pos, nrm = self._port_position_on_face(
                        pp, self._chamber_params
                    )
                    # Volume camera: usa quello dichiarato o quello del ChamberBlock
                    if pp.fb_hz > 0:
                        vbox = pp.vbox_l if pp.vbox_l > 0 else (
                            self._chamber_params.width
                            * self._chamber_params.height
                            * self._chamber_params.depth
                            * 1000.0  # m³ → L
                        )
                        try:
                            port = PortBlock.from_tuning(
                                Fb=pp.fb_hz,
                                chamber_volume=vbox / 1000.0,  # L → m³
                                diameter=pp.diameter,
                                position=pos,
                                normal=nrm,
                            )
                        except Exception:
                            # fallback a length fissa
                            port = PortBlock.from_dimensions(
                                diameter=pp.diameter, length=pp.length,
                                position=pos, normal=nrm,
                            )
                    else:
                        port = PortBlock.from_dimensions(
                            diameter=pp.diameter, length=pp.length,
                            position=pos, normal=nrm,
                        )
                except Exception as exc:
                    self.validation_failed.emit(f"PortBlock: {exc}")

            # DriverBlock: front-face a z=0 (gola tromba), cestello verso -Z
            # (nella camera). mounting_depth=50mm è la profonditò visiva default.
            _DRV_DEPTH = 0.05  # 50 mm
            try:
                driver_block = DriverBlock(
                    driver=self._driver,
                    mounting_depth=_DRV_DEPTH,
                    position=np.array([0.0, 0.0, -_DRV_DEPTH]),
                )
            except Exception as exc:
                self.validation_failed.emit(f"DriverBlock: {exc}")
                driver_block = None

            # Assembly + topologia (driver ↔ horn ↔ chamber ↔ port).
            assembly = Assembly(name="Project")
            horn_id = assembly.add(horn)
            chamber_id = assembly.add(chamber) if chamber is not None else None
            port_id = assembly.add(port) if port is not None else None
            driver_id = assembly.add(driver_block) if driver_block is not None else None

            self._apply_topology(
                assembly,
                horn_id=horn_id,
                chamber_id=chamber_id,
                port_id=port_id,
                driver_id=driver_id,
            )

            self._horn_block = horn
            self._chamber_block = chamber
            self._port_block = port
            self._driver_block = driver_block
            self._assembly = assembly

            self.assembly_changed.emit()
            if self.auto_rebuild_solids:
                self.rebuild_solids()
            return True
        finally:
            self.rebuild_finished.emit()

    def rebuild_solids(self) -> Dict[str, Any]:
        """
        Rigenera la cache dei solidi 3D dai blocchi correnti.

        Skippa silenziosamente blocchi None o conversioni fallite (warning).
        Emette ``solids_rebuilt`` al termine.
        """
        from btk_speaker_designer.geometry import (
            chamber_inner_volume,
            chamber_shell,
            driver_to_solid,
            horn_inner_volume,
            horn_wall_shell,
            port_to_solid,
        )

        solids: Dict[str, Any] = {}

        if self._horn_block is not None:
            for name, fn in (
                ("horn_cavity", horn_inner_volume),
                ("horn_walls", horn_wall_shell),
            ):
                try:
                    solids[name] = fn(self._horn_block)
                except Exception as exc:
                    warnings.warn(
                        f"AssemblyModel: solid '{name}' fallito: {exc}",
                        stacklevel=2,
                    )

        if self._chamber_block is not None:
            for name, fn in (
                ("chamber_inner", chamber_inner_volume),
                ("chamber_shell", chamber_shell),
            ):
                try:
                    solids[name] = fn(self._chamber_block)
                except Exception as exc:
                    warnings.warn(
                        f"AssemblyModel: solid '{name}' fallito: {exc}",
                        stacklevel=2,
                    )

        if self._port_block is not None:
            pp = self._port_params
            n_ports = max(1, getattr(pp, "n_ports", 1))
            W = float(self._chamber_params.width) if self._chamber_block is not None else 0.6
            # Spaziatura orizzontale per N porte: le distribuisce simmetricamente
            spacing = W / (n_ports + 1)
            for i in range(n_ports):
                # offset x simmetrico rispetto al centro della porta principale
                dx = spacing * (i + 1) - W / 2.0
                raw_pos = self._port_block.position.copy()
                raw_pos[0] = float(self._port_block.position[0]) + dx
                from copy import copy as _copy
                port_i = _copy(self._port_block)
                port_i.position = raw_pos
                key = "port" if n_ports == 1 else f"port_{i+1}"
                try:
                    solids[key] = port_to_solid(port_i)
                except Exception as exc:
                    warnings.warn(f"AssemblyModel: solid '{key}' fallito: {exc}",
                                  stacklevel=2)

        if self._driver_block is not None:
            try:
                solids["driver"] = driver_to_solid(self._driver_block)
            except Exception as exc:
                warnings.warn(f"AssemblyModel: solid 'driver' fallito: {exc}",
                              stacklevel=2)

        self._solids_cache = solids
        print(f"[AssemblyModel] rebuild_solids: generati {len(solids)} solidi: "
              f"{[k for k,v in solids.items() if v is not None]}")
        self.solids_rebuilt.emit(dict(solids))
        return dict(solids)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _port_position_on_face(
        pp: "PortParams",
        cp: "ChamberParams",
    ) -> "Tuple[np.ndarray, np.ndarray]":
        """Calcola posizione e normale del port in base alla faccia del cabinet.

        Facce disponibili (coordinate interne al cabinet):
        - "rear"  :  z = -depth,  nrm = -Z   (parete posteriore)
        - "front" :  z = 0,       nrm = +Z   (parete frontale / gola tromba)
        - "bottom":  y = -H/2,    nrm = -Y   (parete inferiore)
        - "top"   :  y = +H/2,    nrm = +Y
        - "left"  :  x = -W/2,    nrm = -X
        - "right" :  x = +W/2,    nrm = +X

        offset_x, offset_y si applicano all'interno del piano della faccia.
        """
        W = float(cp.width)
        H = float(cp.height)
        D = float(cp.depth)
        ox = float(pp.offset_x)
        oy = float(pp.offset_y)

        face = (pp.face or "rear").lower()
        if face == "rear":
            pos = np.array([ox, oy, -D])
            nrm = np.array([0.0, 0.0, -1.0])
        elif face == "front":
            pos = np.array([ox, oy, 0.0])
            nrm = np.array([0.0, 0.0, 1.0])
        elif face == "bottom":
            pos = np.array([ox, -H / 2.0, oy])
            nrm = np.array([0.0, -1.0, 0.0])
        elif face == "top":
            pos = np.array([ox, H / 2.0, oy])
            nrm = np.array([0.0, 1.0, 0.0])
        elif face == "left":
            pos = np.array([-W / 2.0, oy, ox])
            nrm = np.array([-1.0, 0.0, 0.0])
        elif face == "right":
            pos = np.array([W / 2.0, oy, ox])
            nrm = np.array([1.0, 0.0, 0.0])
        else:
            pos = np.array([0.0, 0.0, -D])
            nrm = np.array([0.0, 0.0, -1.0])
        return pos, nrm

    def _maybe_rebuild(self) -> None:
        """Se è disponibile un driver, ricostruisce automaticamente."""
        if self._driver is not None:
            self.rebuild()

    def _apply_topology(
        self,
        assembly: Assembly,
        *,
        horn_id: Optional[str],
        chamber_id: Optional[str],
        port_id: Optional[str],
        driver_id: Optional[str],
    ) -> None:
        """
        Crea connessioni topologiche standard tra i blocchi:

        * driver.front ↔ horn.throat   (driver carica la tromba)
        * driver.back  ↔ chamber.front  (rear chamber sigillata)
        * port.inner   ↔ chamber.back   (porta reflex sul retro camera)

        Errori non bloccanti: se una porta non esiste o è già in uso
        emette ``validation_failed`` ma prosegue (assembly resta valido).
        """
        def _try_connect(a_id: str, a_port: str, b_id: str, b_port: str) -> None:
            try:
                assembly.connect(a_id, a_port, b_id, b_port)
            except (KeyError, ValueError) as exc:
                self.validation_failed.emit(
                    f"connect {a_id}.{a_port} ↔ {b_id}.{b_port}: {exc}"
                )

        if driver_id is not None and horn_id is not None:
            _try_connect(driver_id, "front", horn_id, "throat")
        if driver_id is not None and chamber_id is not None:
            _try_connect(driver_id, "back", chamber_id, "front")
        if port_id is not None and chamber_id is not None:
            _try_connect(port_id, "inner", chamber_id, "back")

    def to_horn_geometry(self):
        """
        Converte il ``HornBlock`` corrente in un ``HornGeometry`` legacy
        (compatibile con simulation_engine, analysis_tabs, exporters).

        Ritorna ``None`` se non c'è ancora un horn_block valido.
        """
        from btk_speaker_designer.core.constants import (
            AIR_DENSITY, SPEED_OF_SOUND,
        )
        from btk_speaker_designer.core.horn_calculator import (
            HornGeometry, HornSection,
        )
        import numpy as np

        h = self._horn_block
        if h is None:
            return None

        throat_imp = (AIR_DENSITY * SPEED_OF_SOUND) / max(h.throat_area, 1e-12)
        sections_legacy = []
        n = max(len(h.sections) - 1, 1)
        for i, s in enumerate(h.sections):
            r = float(np.sqrt(s.area / np.pi))
            sections_legacy.append(
                HornSection(
                    position=i / n,
                    x_m=float(s.x_axial),
                    area_m2=float(s.area),
                    radius_m=r,
                    width_m=float(s.width),
                    height_m=float(s.height),
                )
            )
        return HornGeometry(
            throat_area_m2=float(h.throat_area),
            mouth_area_m2=float(h.mouth_area),
            horn_length_m=float(h.length),
            flare_rate_m=float(h.flare_rate),
            cutoff_frequency_hz=float(h.cutoff_frequency),
            throat_impedance=float(throat_imp),
            coupling_volume_m3=float(h.internal_volume),
            expansion_type=h.expansion,
            sections=sections_legacy,
            hypex_T=float(h.hypex_T),
        )

    def _reset_blocks(self) -> None:
        self._horn_block = None
        self._chamber_block = None
        self._port_block = None
        self._driver_block = None
        self._assembly = None
        self._solids_cache = {}
