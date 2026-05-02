"""
Modelli di enclosure acustica per BTK Speaker Designer.

Supporta tutti i tipi di caricamento:
  - Horn (tromba caricata) — vedi horn_calculator.py
  - Bass-Reflex standard
  - Bandpass 4° ordine  (camera chiusa posteriore + reflex frontale)
  - Bandpass 6° ordine  (reflex posteriore + reflex frontale)
  - Ibridi: Horn+Reflex, Bandpass+Horn, Bandpass+Reflex

Riferimenti:
  - Thiele A.N. (1971) JAES — alignments Butterworth/Chebyshev per reflex
  - Small R.H. (1973) JAES — vented box design
  - Benson J.E. (1972) JAES — bandpass enclosures
  - Beranek L.L. (1954) "Acoustics" — Helmholtz resonator
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List

from .constants import (
    SPEED_OF_SOUND, AIR_DENSITY,
    ENCLOSURE_HORN, ENCLOSURE_REFLEX,
    ENCLOSURE_BANDPASS_4, ENCLOSURE_BANDPASS_6,
    ENCLOSURE_HORN_REFLEX, ENCLOSURE_BANDPASS_HORN, ENCLOSURE_BANDPASS_REFLEX,
    PORT_TYPE_CIRCULAR, PORT_TYPE_SLOT, PORT_TYPE_PASSIVE,
)


# ─── Dataclass porta reflex ───────────────────────────────────────────────────

@dataclass
class ReflexPort:
    """Geometria e parametri di una porta reflex."""

    port_type: str = PORT_TYPE_CIRCULAR     # circular / slot / passive_radiator
    diameter_mm: float = 100.0              # diametro (per porta circolare)
    width_mm: float = 200.0                 # larghezza slot
    height_mm: float = 50.0                 # altezza slot
    length_mm: float = 200.0                # lunghezza del condotto
    n_ports: int = 1                        # numero di porte identiche
    tuning_hz: float = 40.0                 # frequenza di accordo target

    # Calcolato
    area_m2: float = field(default=0.0, init=False)

    def __post_init__(self):
        self._update_area()

    def _update_area(self):
        if self.port_type == PORT_TYPE_CIRCULAR:
            r = (self.diameter_mm / 2) * 1e-3
            self.area_m2 = np.pi * r ** 2 * self.n_ports
        elif self.port_type == PORT_TYPE_SLOT:
            self.area_m2 = (self.width_mm * self.height_mm) * 1e-6 * self.n_ports
        else:
            self.area_m2 = (self.width_mm * self.height_mm) * 1e-6 * self.n_ports

    def update(self):
        self._update_area()


# ─── Dataclass enclosure reflex ───────────────────────────────────────────────

@dataclass
class ReflexEnclosureResult:
    """Risultato del design di un enclosure reflex / bandpass."""

    enclosure_type: str
    box_volume_front_l: float          # volume camera frontale (L)
    box_volume_rear_l: float           # volume camera posteriore (L); 0 per reflex std
    port_front: Optional[ReflexPort] = None   # porta frontale
    port_rear: Optional[ReflexPort] = None    # porta posteriore (bandpass 6° / bandpass_reflex)
    tuning_freq_hz: float = 0.0        # frequenza di accordo effettiva
    f3_low_hz: float = 0.0             # frequenza -3 dB inferiore
    f3_high_hz: float = 0.0            # frequenza -3 dB superiore
    frequencies: np.ndarray = field(default_factory=lambda: np.array([]))
    spl_db: np.ndarray = field(default_factory=lambda: np.array([]))
    phase_deg: np.ndarray = field(default_factory=lambda: np.array([]))
    impedance: np.ndarray = field(default_factory=lambda: np.array([]))
    warnings: List[str] = field(default_factory=list)


# ─── Helmholtz: frequenza di accordo data porta ──────────────────────────────

def helmholtz_tuning_frequency(
    port_area_m2: float,
    port_length_m: float,
    box_volume_m3: float,
    c: float = SPEED_OF_SOUND,
) -> float:
    """
    Frequenza di risonanza di un risuonatore di Helmholtz.

        fb = (c / 2π) * sqrt(Sp / (Vb * Leff))

    dove Leff = L_port + end_correction.

    Args:
        port_area_m2:  area della sezione porta [m²]
        port_length_m: lunghezza geometrica del condotto [m]
        box_volume_m3: volume interno del cabinet [m³]
        c:             velocità del suono [m/s]

    Returns:
        Frequenza di accordo [Hz]

    Rif: Beranek (1954) cap. 5; Small (1973) JAES
    """
    r_port = np.sqrt(port_area_m2 / np.pi)
    end_correction = 0.85 * r_port  # correzione per un'estremità flangiata
    L_eff = max(port_length_m + end_correction, 1e-4)
    return (c / (2 * np.pi)) * np.sqrt(port_area_m2 / (box_volume_m3 * L_eff))


def calculate_port_length(
    target_fb_hz: float,
    port_area_m2: float,
    box_volume_m3: float,
    c: float = SPEED_OF_SOUND,
) -> float:
    """
    Calcola la lunghezza del condotto reflex necessaria per accordare a fb.

    Args:
        target_fb_hz:  frequenza di accordo desiderata [Hz]
        port_area_m2:  area porta [m²]
        box_volume_m3: volume cabinet [m³]
        c:             velocità del suono [m/s]

    Returns:
        Lunghezza condotto [m] (minimo 0.03 m per evitare valori negativi)

    Rif: Small R.H. (1973) JAES 21(6)
    """
    omega_b = 2 * np.pi * target_fb_hz
    L_ideal = (c / omega_b) ** 2 * (port_area_m2 / box_volume_m3)
    r_port = np.sqrt(port_area_m2 / np.pi)
    end_corr = 0.85 * r_port
    L = L_ideal - end_corr
    return max(L, 0.03)


def port_air_velocity_peak(
    driver_sd_m2: float,
    driver_xmax_m: float,
    port_area_m2: float,
    fb_hz: float,
) -> float:
    """
    Velocità di picco dell'aria nel condotto reflex all'accordo.
    Usato per check turbolenza (Re).

    v_peak = (Sd * Xmax * ωb) / Sp

    Rif: Beranek (1954); Harris (1999) AES preprint
    """
    omega_b = 2 * np.pi * fb_hz
    return (driver_sd_m2 * driver_xmax_m * omega_b) / port_area_m2


def port_reynolds_number(
    v_peak: float,
    port_diameter_m: float,
    rho: float = AIR_DENSITY,
    mu: float = 1.81e-5,
) -> float:
    """
    Numero di Reynolds per flusso nel condotto reflex.
    Re > 2300 → possibile turbolenza e rumore di porta.

    Rif: Reynolds O. (1883); Beranek (1954)
    """
    return rho * v_peak * port_diameter_m / mu


# ─── Design bass-reflex (Small 1973) ─────────────────────────────────────────

def design_bass_reflex(
    fs_hz: float,
    qts: float,
    vas_l: float,
    sd_m2: float,
    xmax_m: float,
    target_fb_hz: Optional[float] = None,
    port: Optional[ReflexPort] = None,
    c: float = SPEED_OF_SOUND,
) -> ReflexEnclosureResult:
    """
    Progetta un enclosure bass-reflex ottimale (allineamento Butterworth).

    Per l'allineamento Butterworth (quasi-Butterworth QB3):
        Vb = Vas * (Qts / 0.4)^(-2.87)  (approssimazione Small 1973)
        fb = fs * (Vas / Vb)^0.31        (allineamento QB3)

    Args:
        fs_hz:        freq risonanza driver [Hz]
        qts:          Q totale driver
        vas_l:        volume equivalente driver [L]
        sd_m2:        area diaframma [m²]
        xmax_m:       escursione massima [m]
        target_fb_hz: freq accordo porta (None = calcolo automatico)
        port:         porto reflex (None = crea automaticamente)
        c:            velocità del suono [m/s]

    Returns:
        ReflexEnclosureResult con tutte le dimensioni e la risposta simulata

    Rif: Small R.H. (1973) JAES 21(6):438; Thiele A.N. (1971) JAES 19(5)
    """
    warnings = []

    # ── Volume ottimale con allineamento QB3 ──────────────────────────────
    # Vb = Vas * (Qts/0.4)^(-2.87)  — Small (1973) Table 1
    qts_clamped = max(qts, 0.05)
    vb_l = vas_l * (qts_clamped / 0.4) ** (-2.87)
    vb_l = max(vb_l, 5.0)   # minimo 5L per vasi piccoli
    vb_m3 = vb_l * 1e-3

    if qts > 0.5:
        warnings.append(
            f"Qts = {qts:.3f} elevato — il reflex può risultare scarsamente controllato. "
            "Considera un allineamento chiuso (sealed)."
        )

    # ── Frequenza di accordo ───────────────────────────────────────────────
    if target_fb_hz is None:
        # Allineamento QB3: fb = fs * (Vas/Vb)^0.31
        fb_hz = fs_hz * (vas_l / vb_l) ** 0.31
    else:
        fb_hz = target_fb_hz
    fb_hz = max(fb_hz, 10.0)

    # ── Geometria porta ───────────────────────────────────────────────────
    if port is None:
        # Porta circolare con diametro suggerito = sqrt(Sd) * 0.6
        diam_m = np.sqrt(sd_m2) * 0.6
        diam_mm = diam_m * 1e3
        port = ReflexPort(
            port_type=PORT_TYPE_CIRCULAR,
            diameter_mm=round(diam_mm / 5) * 5,  # arrotonda a 5 mm
            n_ports=1,
            tuning_hz=fb_hz,
        )
        port.update()

    port_area_m2 = port.area_m2

    port_length_m = calculate_port_length(fb_hz, port_area_m2, vb_m3, c)
    port.length_mm = port_length_m * 1e3
    port.tuning_hz = fb_hz

    # ── Check velocità aria nella porta ───────────────────────────────────
    v_peak = port_air_velocity_peak(sd_m2, xmax_m, port_area_m2, fb_hz)
    d_port = np.sqrt(port_area_m2 / np.pi) * 2  # diametro equivalente
    re_num = port_reynolds_number(v_peak, d_port)
    if re_num > 2300:
        warnings.append(
            f"Re porta = {re_num:.0f} > 2300 — rischio turbolenza/chuffing alla massima escursione. "
            "Aumenta il diametro della porta."
        )

    # ── Risposta in frequenza (modello analitico Small) ───────────────────
    freqs = np.logspace(np.log10(10), np.log10(500), 500)
    spl_db, phase_deg, impedance = _reflex_response(
        freqs, fs_hz, qts, vas_l, sd_m2, vb_l, fb_hz, c
    )

    # f3 inferiore (primo incrocio con -3 dB dalla banda passante)
    f3_low = _find_f3_low(freqs, spl_db)
    f3_high = _find_f3_high(freqs, spl_db)

    return ReflexEnclosureResult(
        enclosure_type=ENCLOSURE_REFLEX,
        box_volume_front_l=vb_l,
        box_volume_rear_l=0.0,
        port_front=port,
        tuning_freq_hz=fb_hz,
        f3_low_hz=f3_low,
        f3_high_hz=f3_high,
        frequencies=freqs,
        spl_db=spl_db,
        phase_deg=phase_deg,
        impedance=impedance,
        warnings=warnings,
    )


# ─── Design bandpass 4° ordine ───────────────────────────────────────────────

def design_bandpass_4th(
    fs_hz: float,
    qts: float,
    vas_l: float,
    sd_m2: float,
    xmax_m: float,
    f_low_hz: float = 40.0,
    f_high_hz: float = 100.0,
    port_front: Optional[ReflexPort] = None,
    c: float = SPEED_OF_SOUND,
) -> ReflexEnclosureResult:
    """
    Bandpass 4° ordine: camera posteriore chiusa + camera anteriore reflex.

    Il driver è montato tra le due camere. La camera anteriore apre sull'esterno
    tramite una porta reflex che determina la frequenza alta del passabanda.

    Design equations (Benson 1972, Kreschmer 1979):
        Vr = Vas * (Qts/Qb)^2    (camera chiusa posteriore)
        Vf tuned at fb_high
        fb_low ≈ fs * (Vas/(Vr+Vas))^0.5

    Args:
        fs_hz, qts, vas_l, sd_m2, xmax_m: parametri T&S del driver
        f_low_hz:   freq -3dB bassa del passabanda desiderata [Hz]
        f_high_hz:  freq -3dB alta del passabanda desiderata [Hz]
        port_front: porta anteriore (None = calcolo auto)
        c:          velocità del suono [m/s]

    Returns:
        ReflexEnclosureResult con entrambe le dimensioni camera

    Rif: Benson J.E. (1972) JAES; Small R.H. (1973) JAES
    """
    warnings = []

    # Camera posteriore (closed): Vr ottimizzato per Qb = 0.707
    # Vr = Vas * (Qts/Qb)^2   con Qb target = 0.707 (Butterworth)
    qb_target = 0.707
    vr_l = vas_l * (qts / qb_target) ** 2
    vr_l = max(vr_l, 3.0)
    vr_m3 = vr_l * 1e-3

    # Camera anteriore (reflex): accordata a f_high_hz
    vf_l = vr_l * 0.7   # inizialmente camera anteriore = 70% della posteriore
    vf_l = max(vf_l, 3.0)
    vf_m3 = vf_l * 1e-3

    # Porta anteriore
    if port_front is None:
        diam_mm = np.sqrt(sd_m2) * 0.55 * 1e3
        port_front = ReflexPort(
            port_type=PORT_TYPE_CIRCULAR,
            diameter_mm=round(diam_mm / 5) * 5,
            n_ports=1,
            tuning_hz=f_high_hz,
        )
        port_front.update()

    port_area_m2 = port_front.area_m2
    L_port = calculate_port_length(f_high_hz, port_area_m2, vf_m3, c)
    port_front.length_mm = L_port * 1e3
    port_front.tuning_hz = f_high_hz

    # Check turbolenza porta
    v_peak = port_air_velocity_peak(sd_m2, xmax_m, port_area_m2, f_high_hz)
    d_equiv = np.sqrt(port_area_m2 / np.pi) * 2
    re_num = port_reynolds_number(v_peak, d_equiv)
    if re_num > 2300:
        warnings.append(
            f"Re porta front = {re_num:.0f} > 2300 — rischio chuffing. "
            "Aumenta il diametro della porta anteriore."
        )

    # Risposta bandpass approssimata
    freqs = np.logspace(np.log10(10), np.log10(1000), 600)
    spl_db, phase_deg, impedance = _bandpass4_response(
        freqs, fs_hz, qts, vas_l, vr_l, vf_l, f_high_hz, c
    )

    f3_low = _find_f3_low(freqs, spl_db)
    f3_high = _find_f3_high(freqs, spl_db)

    return ReflexEnclosureResult(
        enclosure_type=ENCLOSURE_BANDPASS_4,
        box_volume_front_l=vf_l,
        box_volume_rear_l=vr_l,
        port_front=port_front,
        tuning_freq_hz=f_high_hz,
        f3_low_hz=f3_low,
        f3_high_hz=f3_high,
        frequencies=freqs,
        spl_db=spl_db,
        phase_deg=phase_deg,
        impedance=impedance,
        warnings=warnings,
    )


# ─── Design bandpass 6° ordine ───────────────────────────────────────────────

def design_bandpass_6th(
    fs_hz: float,
    qts: float,
    vas_l: float,
    sd_m2: float,
    xmax_m: float,
    f_low_hz: float = 40.0,
    f_high_hz: float = 100.0,
    port_rear: Optional[ReflexPort] = None,
    port_front: Optional[ReflexPort] = None,
    c: float = SPEED_OF_SOUND,
) -> ReflexEnclosureResult:
    """
    Bandpass 6° ordine: camera posteriore reflex + camera anteriore reflex.

    Entrambe le camere hanno porte reflex accordate a frequenze diverse.
    Offre maggiore SPL della versione 4°, ma pendenza 24 dB/ott laterale.

    Rif: Benson J.E. (1972); Small R.H. (1973); Keele D.B. (1990) AES Conv.89
    """
    warnings = []

    # Camera posteriore: reflex accordata a f_low_hz
    vr_l = vas_l * 0.9
    vr_l = max(vr_l, 5.0)
    vr_m3 = vr_l * 1e-3

    if port_rear is None:
        diam_mm = np.sqrt(sd_m2) * 0.65 * 1e3
        port_rear = ReflexPort(
            port_type=PORT_TYPE_CIRCULAR,
            diameter_mm=round(diam_mm / 5) * 5,
            n_ports=1,
            tuning_hz=f_low_hz,
        )
        port_rear.update()
    L_rear = calculate_port_length(f_low_hz, port_rear.area_m2, vr_m3, c)
    port_rear.length_mm = L_rear * 1e3
    port_rear.tuning_hz = f_low_hz

    # Camera anteriore: reflex accordata a f_high_hz
    vf_l = vr_l * 0.6
    vf_l = max(vf_l, 3.0)
    vf_m3 = vf_l * 1e-3

    if port_front is None:
        diam_mm = np.sqrt(sd_m2) * 0.55 * 1e3
        port_front = ReflexPort(
            port_type=PORT_TYPE_CIRCULAR,
            diameter_mm=round(diam_mm / 5) * 5,
            n_ports=1,
            tuning_hz=f_high_hz,
        )
        port_front.update()
    L_front = calculate_port_length(f_high_hz, port_front.area_m2, vf_m3, c)
    port_front.length_mm = L_front * 1e3
    port_front.tuning_hz = f_high_hz

    # Check turbolenza porte
    for fb, port, label in [(f_low_hz, port_rear, "rear"), (f_high_hz, port_front, "front")]:
        v_peak = port_air_velocity_peak(sd_m2, xmax_m, port.area_m2, fb)
        d_eq = np.sqrt(port.area_m2 / np.pi) * 2
        re_num = port_reynolds_number(v_peak, d_eq)
        if re_num > 2300:
            warnings.append(
                f"Re porta {label} = {re_num:.0f} > 2300 — rischio chuffing. "
                f"Aumenta diametro porta {label}."
            )

    # Risposta bandpass 6° ordine
    freqs = np.logspace(np.log10(10), np.log10(1000), 600)
    spl_db, phase_deg, impedance = _bandpass6_response(
        freqs, fs_hz, qts, vas_l, vr_l, vf_l, f_low_hz, f_high_hz, c
    )

    f3_low = _find_f3_low(freqs, spl_db)
    f3_high = _find_f3_high(freqs, spl_db)

    return ReflexEnclosureResult(
        enclosure_type=ENCLOSURE_BANDPASS_6,
        box_volume_front_l=vf_l,
        box_volume_rear_l=vr_l,
        port_front=port_front,
        port_rear=port_rear,
        tuning_freq_hz=(f_low_hz + f_high_hz) / 2,
        f3_low_hz=f3_low,
        f3_high_hz=f3_high,
        frequencies=freqs,
        spl_db=spl_db,
        phase_deg=phase_deg,
        impedance=impedance,
        warnings=warnings,
    )


# ─── Modelli per ibridi (stubs con risposta approssimata) ────────────────────

def design_horn_reflex_hybrid(
    fs_hz: float,
    qts: float,
    vas_l: float,
    sd_m2: float,
    xmax_m: float,
    box_volume_l: float = 50.0,
    port: Optional[ReflexPort] = None,
    c: float = SPEED_OF_SOUND,
) -> ReflexEnclosureResult:
    """
    Tromba frontale + porta reflex nell'enclosure.

    Il reflex aumenta il guadagno alle basse frequenze (sotto la Fc della tromba)
    compensando il roll-off del carico a tromba.

    Usato per: sub compatti con estensione grave migliorata.
    """
    # Porta accordata a Fs del driver
    fb_hz = fs_hz * 0.9
    if port is None:
        diam_mm = np.sqrt(sd_m2) * 0.5 * 1e3
        port = ReflexPort(
            port_type=PORT_TYPE_CIRCULAR,
            diameter_mm=round(diam_mm / 5) * 5,
            n_ports=1,
            tuning_hz=fb_hz,
        )
        port.update()

    vb_m3 = box_volume_l * 1e-3
    L_port = calculate_port_length(fb_hz, port.area_m2, vb_m3, c)
    port.length_mm = L_port * 1e3
    port.tuning_hz = fb_hz

    warnings = []
    v_peak = port_air_velocity_peak(sd_m2, xmax_m, port.area_m2, fb_hz)
    d_eq = np.sqrt(port.area_m2 / np.pi) * 2
    re_num = port_reynolds_number(v_peak, d_eq)
    if re_num > 2300:
        warnings.append(f"Re porta = {re_num:.0f} > 2300 — rischio chuffing alla massima escursione.")

    freqs = np.logspace(np.log10(10), np.log10(500), 500)
    spl_db, phase_deg, impedance = _reflex_response(
        freqs, fs_hz, qts, vas_l, sd_m2, box_volume_l, fb_hz, c
    )

    return ReflexEnclosureResult(
        enclosure_type=ENCLOSURE_HORN_REFLEX,
        box_volume_front_l=box_volume_l,
        box_volume_rear_l=0.0,
        port_front=port,
        tuning_freq_hz=fb_hz,
        f3_low_hz=_find_f3_low(freqs, spl_db),
        f3_high_hz=_find_f3_high(freqs, spl_db),
        frequencies=freqs,
        spl_db=spl_db,
        phase_deg=phase_deg,
        impedance=impedance,
        warnings=warnings,
    )


def design_bandpass_horn(
    fs_hz: float,
    qts: float,
    vas_l: float,
    sd_m2: float,
    xmax_m: float,
    f_low_hz: float = 40.0,
    f_high_hz: float = 120.0,
    box_rear_volume_l: float = 100.0,
    port_rear: Optional[ReflexPort] = None,
    c: float = SPEED_OF_SOUND,
) -> ReflexEnclosureResult:
    """
    Bandpass + Tromba frontale (stile DC10 / SPKP 2018).

    Camera posteriore chiusa o reflex → driver → tromba frontale.
    La tromba estende la risposta alle medie frequenze.
    Il bandpass posteriore controlla le basse.

    Questa è la topologia del DC10 Monitor del 2018:
    - Camera posteriore: chiusa o reflex (per le basse)
    - Camera anteriore: aperta sulla tromba HF

    Args:
        f_low_hz:           freq di taglio bassa del passabanda [Hz]
        f_high_hz:          freq di taglio alta (Fc tromba) [Hz]
        box_rear_volume_l:  volume camera posteriore [L]
        port_rear:          porta posteriore per estensione grave (None = chiusa)
    """
    warnings = []

    vr_l = box_rear_volume_l
    vr_m3 = vr_l * 1e-3

    if port_rear is not None:
        L_rear = calculate_port_length(f_low_hz, port_rear.area_m2, vr_m3, c)
        port_rear.length_mm = L_rear * 1e3
        port_rear.tuning_hz = f_low_hz
        v_peak = port_air_velocity_peak(sd_m2, xmax_m, port_rear.area_m2, f_low_hz)
        d_eq = np.sqrt(port_rear.area_m2 / np.pi) * 2
        re_num = port_reynolds_number(v_peak, d_eq)
        if re_num > 2300:
            warnings.append(f"Re porta rear = {re_num:.0f} — rischio chuffing.")

    # Risposta approssimata come bandpass 4° (la tromba aggiunge inclinazione HF)
    vf_l = vr_l * 0.5
    freqs = np.logspace(np.log10(10), np.log10(1000), 600)
    spl_db, phase_deg, impedance = _bandpass4_response(
        freqs, fs_hz, qts, vas_l, vr_l, vf_l, f_high_hz, c
    )

    return ReflexEnclosureResult(
        enclosure_type=ENCLOSURE_BANDPASS_HORN,
        box_volume_front_l=vf_l,
        box_volume_rear_l=vr_l,
        port_rear=port_rear,
        tuning_freq_hz=(f_low_hz + f_high_hz) / 2,
        f3_low_hz=_find_f3_low(freqs, spl_db),
        f3_high_hz=_find_f3_high(freqs, spl_db),
        frequencies=freqs,
        spl_db=spl_db,
        phase_deg=phase_deg,
        impedance=impedance,
        warnings=warnings,
    )


# ─── Modelli analitici di risposta ───────────────────────────────────────────

def _reflex_response(
    freqs: np.ndarray,
    fs: float, qts: float, vas_l: float,
    sd_m2: float, vb_l: float, fb: float,
    c: float = SPEED_OF_SOUND,
):
    """
    Risposta in frequenza di un enclosure bass-reflex.

    Usa il modello a funzioni di trasferimento del 4° ordine di Small (1973):
        H(s) = s^4 / D(s)
    dove D(s) è il polinomio caratteristico del sistema.

    Rif: Small R.H. (1973) JAES 21(6); Thiele A.N. (1971) JAES 19(5)
    """
    s = 1j * 2 * np.pi * freqs

    # Normalizzazione
    ws = 2 * np.pi * fs
    wb = 2 * np.pi * fb
    alpha = vas_l / vb_l  # rapporto volume

    # Funzione di trasferimento bassa (approssimazione 4° ordine Small)
    # H(jω) = (ω/ωs)^4 / [(ω/ωs)^4 - A*(ω/ωs)^2 + (ωb/ωs)^2]
    omega = 2 * np.pi * freqs
    x = omega / ws
    xb = wb / ws

    # Coefficienti del denominatore QB3 approssimato
    h = (x ** 4) / (x ** 4 - (1 + alpha + xb ** 2 / (qts ** 2)) * x ** 2 + xb ** 2 + 1j * 1e-12)
    # Amplitudine rispetto alla banda passante (normalizzata = 0 dB)
    h_ref = float(np.abs(h[len(h) // 2]))
    if h_ref < 1e-10:
        h_ref = 1.0

    spl_db = 20 * np.log10(np.abs(h) / h_ref + 1e-12)
    phase_deg = np.degrees(np.angle(h))

    # Impedenza: modello semplificato Z(f) = Re + jωLe + back-EMF
    # (senza parametri Re/Le qui, usare driver_model per la versione precisa)
    z_magnitude = 8.0 * (1 + 0.5 * np.exp(-((freqs - fs) / (fs * 0.3)) ** 2)
                         + 0.5 * np.exp(-((freqs - fb) / (fb * 0.2)) ** 2))
    impedance = z_magnitude

    return spl_db, phase_deg, impedance


def _bandpass4_response(
    freqs: np.ndarray,
    fs: float, qts: float, vas_l: float,
    vr_l: float, vf_l: float, fb_front: float,
    c: float = SPEED_OF_SOUND,
):
    """
    Risposta approssimata bandpass 4° ordine.
    Camera chiusa posteriore + reflex frontale.
    """
    omega = 2 * np.pi * freqs
    ws = 2 * np.pi * fs
    wb = 2 * np.pi * fb_front

    alpha = vas_l / vr_l
    x = omega / ws
    xb = wb / ws

    # BP4: prodotto di risposta passa-alto (closed) × passa-basso (reflex)
    # HP chiuso: H_hp = x^2 / (x^2 - j*x/(qts*sqrt(1+alpha)) + (1+alpha))
    qa = qts * np.sqrt(1 + alpha) / (1 + alpha)
    h_hp = x ** 2 / (x ** 2 + 1j * x / qa + 1)

    # LP reflex camera anteriore: Passa-basso 2° ordine smorzato
    xb2 = omega / wb
    h_lp = 1.0 / (1 + 1j * xb2 / 0.707 - xb2 ** 2 + 1e-12)

    h = h_hp * h_lp
    h_ref = float(np.max(np.abs(h))) or 1.0
    spl_db = 20 * np.log10(np.abs(h) / h_ref + 1e-12)
    phase_deg = np.degrees(np.angle(h))

    impedance = 8.0 * (1 + 0.4 * np.exp(-((freqs - fs) / (fs * 0.3)) ** 2))

    return spl_db, phase_deg, impedance


def _bandpass6_response(
    freqs: np.ndarray,
    fs: float, qts: float, vas_l: float,
    vr_l: float, vf_l: float,
    fb_rear: float, fb_front: float,
    c: float = SPEED_OF_SOUND,
):
    """
    Risposta approssimata bandpass 6° ordine (doppio reflex).
    """
    omega = 2 * np.pi * freqs
    ws = 2 * np.pi * fs
    wr = 2 * np.pi * fb_rear
    wf = 2 * np.pi * fb_front

    x = omega / ws

    # HP con reflex posteriore
    xr = omega / wr
    h_rear = xr ** 2 / (xr ** 2 + 1j * xr / 0.707 + 1 + 1e-12)

    # LP con reflex anteriore
    xf = omega / wf
    h_front = 1.0 / (xf ** 2 - 1j * xf / 0.707 - 1 + 1e-12)
    h_front = np.abs(h_front)

    h = h_rear * h_front
    h_ref = float(np.max(np.abs(h))) or 1.0
    spl_db = 20 * np.log10(np.abs(h) / h_ref + 1e-12)
    phase_deg = np.degrees(np.angle(h))
    impedance = 8.0 * np.ones_like(freqs)

    return spl_db, phase_deg, impedance


# ─── Helper: trova –3 dB ─────────────────────────────────────────────────────

def _find_f3_low(freqs: np.ndarray, spl_db: np.ndarray) -> float:
    """Frequenza inferiore –3 dB (primo incrocio salendo da sinistra)."""
    peak = float(np.nanmax(spl_db))
    threshold = peak - 3.0
    for i in range(len(spl_db) - 1):
        if spl_db[i] < threshold <= spl_db[i + 1]:
            return float(freqs[i])
    return float(freqs[0])


def _find_f3_high(freqs: np.ndarray, spl_db: np.ndarray) -> float:
    """Frequenza superiore –3 dB (ultimo incrocio scendendo da destra)."""
    peak = float(np.nanmax(spl_db))
    threshold = peak - 3.0
    for i in range(len(spl_db) - 1, 0, -1):
        if spl_db[i] < threshold <= spl_db[i - 1]:
            return float(freqs[i])
    return float(freqs[-1])
