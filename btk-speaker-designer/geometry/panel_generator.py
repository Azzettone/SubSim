"""
panel_generator — converte blocchi acustici in solidi 3D B-rep.

Strategia:
- Ogni Panel del blocco è un quadrilatero planare con vertici in ordine
  antiorario VISTI DALL'ESTERNO (convenzione del progetto). La normale
  calcolata via cross product (v1-v0) × (v2-v0) punta quindi OUTWARD.
- panel_to_solid: estrude il quadrilatero verso l'interno (-normal) per
  panel.thickness → ottiene un prisma solido (loft tra outer e inner face).
- chamber_shell: unione (Compound) dei 6 pannelli di un ChamberBlock.
  NOTA: i pannelli si sovrappongono leggermente agli angoli (ognuno
  estruso verso interno per spessore pieno). Per panel-cutlist con
  miter joints servirà post-processing in Fase 3 (constructive layer).
- chamber_inner_volume: parallelepipedo o prisma trapezoidale della
  cavità interna (= cabinet esterno - tutti i pannelli). Utile per
  validare volume Vb e per BEM (boundary del fluido interno).

Esportazione:
- STEP: formato CAD universale (FreeCAD/Fusion/SolidWorks/...).
- STL: stampa 3D / mesh triangolata (no parametrica).

Tutte le unità sono in METRI (coerenti col resto del progetto).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Union

import numpy as np

# Import lazy: build123d richiede libGL system → fallisce su sistemi minimal.
# Spostiamo l'import in funzione per permettere `import geometry` senza errori.

from ..blocks.base_block import Panel
from ..blocks.chamber_block import ChamberBlock
from ..blocks.port_block import PortBlock
from ..blocks.driver_block import DriverBlock
from ..blocks.horn_block import HornBlock


# ─── Eccezioni ───────────────────────────────────────────────────────────────


class PanelGeometryError(RuntimeError):
    """Errore generico nella conversione blocco → geometria 3D."""


# ─── Helper interni ──────────────────────────────────────────────────────────


def _bd():
    """Import lazy di build123d con messaggio di errore esplicativo."""
    try:
        import build123d as bd  # noqa: F401
        return bd
    except ImportError as e:
        raise PanelGeometryError(
            "build123d non installato o libGL mancante. "
            "Installa: 'pip install build123d' e (Linux) "
            "'apt install libgl1 libglu1-mesa libxrender1 libxext6'."
        ) from e


def _outward_normal(vertices: np.ndarray) -> np.ndarray:
    """
    Calcola la normale unitaria di un quadrilatero planare (vertici 4×3
    in ordine CCW visti dall'esterno → normale OUTWARD).
    """
    v0, v1, v2 = vertices[0], vertices[1], vertices[2]
    n = np.cross(v1 - v0, v2 - v0)
    norm = np.linalg.norm(n)
    if norm < 1e-12:
        raise PanelGeometryError(
            "Pannello degenere: vertici collineari o coincidenti."
        )
    return n / norm


def _quad_face(bd, vertices: Sequence[np.ndarray]):
    """Crea una Face build123d da 4 punti 3D in ordine."""
    pts = [bd.Vector(*v) for v in vertices]
    wire = bd.Wire(bd.Polyline(*pts, close=True))
    return bd.Face(wire)


def _orient_along_normal(solid, normal: np.ndarray, position: np.ndarray):
    """
    Orienta e posiziona un solido build123d.

    Convenzione: il solido è creato con il punto di ingresso ALL'ORIGINE
    e l'asse principale lungo +Z (es: Cylinder con Align.MIN su Z).

    Questa funzione:
    1. Ruota il solido per allineare +Z alla direzione `normal`.
    2. Trasla di `position` (così il punto d'ingresso, prima all'origine,
       finisce esattamente a `position`).

    Args:
        solid: Part build123d (asse principale lungo +Z, inlet @ origin).
        normal: versore direzione (numpy array 3,).
        position: punto centro ingresso nello spazio globale (numpy array 3,).

    Returns:
        Part build123d riposizionato.
    """
    bd = _bd()
    n = np.asarray(normal, dtype=float)
    n = n / np.linalg.norm(n)
    z = np.array([0.0, 0.0, 1.0])

    if np.allclose(n, z, atol=1e-9):
        oriented = solid
    elif np.allclose(n, -z, atol=1e-9):
        # 180° attorno asse X (arbitrario, purché perpendicolare)
        oriented = solid.rotate(bd.Axis.X, 180.0)
    else:
        rot_axis = np.cross(z, n)
        rot_axis /= np.linalg.norm(rot_axis)
        angle_deg = float(np.degrees(np.arccos(np.clip(np.dot(z, n), -1.0, 1.0))))
        oriented = solid.rotate(
            bd.Axis(bd.Vector(0, 0, 0), bd.Vector(*rot_axis)), angle_deg
        )

    return oriented.translate(bd.Vector(*position))


# ─── API pubblica ────────────────────────────────────────────────────────────


def panel_to_solid(panel: Panel):
    """
    Converte un Panel in solido 3D estrudendolo verso l'interno.

    Il solido risultante ha:
    - Faccia esterna = panel.vertices (sul piano "fuori cabinet")
    - Faccia interna = panel.vertices traslati di -normal*thickness
    - Spessore = panel.thickness lungo la direzione opposta alla normale

    Args:
        panel: Panel con vertices (4,3) in ordine CCW visti dall'esterno.

    Returns:
        build123d.Part — solido del pannello.

    Raises:
        PanelGeometryError: se il pannello è degenere o build123d non disponibile.
    """
    bd = _bd()

    if panel.vertices.shape != (4, 3):
        raise PanelGeometryError(
            f"Panel '{panel.name}': vertices deve avere shape (4,3), "
            f"ricevuto {panel.vertices.shape}"
        )
    if panel.thickness <= 0:
        raise PanelGeometryError(
            f"Panel '{panel.name}': thickness deve essere > 0, "
            f"ricevuto {panel.thickness}"
        )

    n = _outward_normal(panel.vertices)
    outer = panel.vertices                    # facce esterna (CCW da fuori)
    inner = panel.vertices - n * panel.thickness  # faccia interna (verso dentro)

    # Per loft pulito: inner deve avere stesso ordine di winding che, vista
    # dall'esterno (dalla normale +n), risulta CW (perché è "sotto" outer).
    # build123d.loft gestisce automaticamente la chiusura tra le due face.
    f_outer = _quad_face(bd, outer)
    f_inner = _quad_face(bd, inner)

    try:
        solid = bd.loft([f_outer, f_inner])
    except Exception as e:
        raise PanelGeometryError(
            f"Loft fallito per pannello '{panel.name}': {e}"
        ) from e

    # Tagga il solido con il nome del pannello (utile per debug/export)
    solid.label = panel.name
    return solid


def chamber_shell(chamber: ChamberBlock):
    """
    Genera il guscio (shell) di una ChamberBlock come Compound dei 6
    pannelli estrusi inward.

    NOTA: i pannelli si sovrappongono agli angoli (ognuno con spessore
    pieno). Per cutlist CNC con miter joints serve post-processing.
    Per visualizzazione, export STL e validazione volume va benissimo.

    Args:
        chamber: ChamberBlock con 6 pannelli.

    Returns:
        build123d.Compound — assemblaggio dei 6 pannelli.
    """
    bd = _bd()
    panels = chamber.panels
    if len(panels) != 6:
        raise PanelGeometryError(
            f"ChamberBlock attesi 6 pannelli, trovati {len(panels)}"
        )
    solids = [panel_to_solid(p) for p in panels]
    compound = bd.Compound(children=solids)
    compound.label = f"chamber_{chamber.shape}"
    return compound


def chamber_inner_volume(chamber: ChamberBlock):
    """
    Genera il solido della cavità INTERNA della ChamberBlock — ossia
    l'aria contenuta dentro dopo aver montato i 6 pannelli.

    Per rectangular: parallelepipedo di dimensioni
       (W - 2t) × (H - 2t) × (D - 2t).
    Per trapezoidal: prisma trapezoidale (lofted) con stesse correzioni.

    Args:
        chamber: ChamberBlock.

    Returns:
        build123d.Part — solido della cavità interna.

    Raises:
        PanelGeometryError: se lo spessore dei pannelli è troppo grande
            rispetto alle dimensioni (cavità degenere).
    """
    bd = _bd()
    t = chamber.panel_thickness

    # Dimensioni interne lungo ciascun asse
    W_in = chamber.width - 2 * t
    H_in = chamber.height - 2 * t
    D_in = chamber.depth - 2 * t
    Wb_in = (chamber.rear_width or chamber.width) - 2 * t

    if min(W_in, H_in, D_in, Wb_in) <= 0:
        raise PanelGeometryError(
            f"Pannelli troppo spessi (t={t*1000:.1f}mm) per le dimensioni "
            f"della camera: cavità interna degenere."
        )

    ox, oy, oz = chamber.origin
    cx = ox  # asse di simmetria X (vedi ChamberBlock._corners)

    # Vertici cavità interna (sistema globale)
    # Back face @ z = oz + t
    z_back = oz + t
    z_front = oz + chamber.depth - t
    y_bot = oy + t
    y_top = oy + chamber.height - t

    back = [
        np.array([cx - Wb_in/2, y_bot, z_back]),
        np.array([cx + Wb_in/2, y_bot, z_back]),
        np.array([cx + Wb_in/2, y_top, z_back]),
        np.array([cx - Wb_in/2, y_top, z_back]),
    ]
    front = [
        np.array([cx - W_in/2, y_bot, z_front]),
        np.array([cx + W_in/2, y_bot, z_front]),
        np.array([cx + W_in/2, y_top, z_front]),
        np.array([cx - W_in/2, y_top, z_front]),
    ]

    f_back = _quad_face(bd, back)
    f_front = _quad_face(bd, front)
    try:
        solid = bd.loft([f_back, f_front])
    except Exception as e:
        raise PanelGeometryError(
            f"Loft cavità interna fallito: {e}"
        ) from e
    solid.label = f"chamber_{chamber.shape}_cavity"
    return solid


def port_to_solid(port: PortBlock):
    """
    Converte un PortBlock in solido 3D.

    Shape:
      - "circular": cilindro con inlet-face all'origine, loft a +Z.
      - "rectangular": box slot con inlet-face all'origine.

    Il solido è orientato lungo port.normal con inlet-face a port.position.
    Dimensioni: sezione = port.area, lunghezza = port.length.

    Args:
        port: PortBlock (area, length, shape, position, normal).

    Returns:
        build123d.Part — solido del condotto reflex.

    Raises:
        PanelGeometryError: se build123d non disponibile o dimensioni invalide.
    """
    bd = _bd()

    if port.area <= 0 or port.length <= 0:
        raise PanelGeometryError(
            f"PortBlock: area ({port.area}) e length ({port.length}) devono essere > 0"
        )

    try:
        if port.shape == "circular":
            radius = float(np.sqrt(port.area / np.pi))
            raw = bd.Cylinder(
                radius, port.length,
                align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
            )
        else:  # rectangular slot
            raw = bd.Box(
                port.width, port.height, port.length,
                align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
            )
    except Exception as e:
        raise PanelGeometryError(f"Creazione solido porta fallita: {e}") from e

    solid = _orient_along_normal(raw, port.normal, port.position)
    solid.label = f"port_{port.shape}"
    return solid


def driver_to_solid(driver: DriverBlock):
    """
    Genera il solido 3D rappresentativo del driver (basket + cono).

    Il driver è modellato come un cilindro con:
      - diametro = driver.diameter_emission (= 2·sqrt(Sd/π))
      - profondità = max(driver.mounting_depth, 0.05 m)

    Non genera pannelli costruttivi propri — per il cutout sul pannello ospite
    usa driver.cutout_for_panel().

    Il solido è orientato lungo driver.front_normal con la faccia "cono"
    (emissiva) centrata a driver.position.

    Args:
        driver: DriverBlock.

    Returns:
        build123d.Part — solido cilindrico del driver.

    Raises:
        PanelGeometryError: se build123d non disponibile.
    """
    bd = _bd()

    radius = driver.diameter_emission / 2.0          # m
    depth = max(driver.mounting_depth, 0.05)          # m, min 5 cm
    if radius <= 0:
        raise PanelGeometryError(
            f"DriverBlock: diametro emissivo negativo o nullo (Sd={driver.driver.sd})"
        )

    try:
        # Front-face (emissiva) all'origine, cestello si estende verso -Z nel
        # sistema locale → align MIN per Z significa che il solido
        # va da Z=0 (front) a Z=depth (back). Poi orientiamo long front_normal.
        raw = bd.Cylinder(
            radius, depth,
            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
        )
    except Exception as e:
        raise PanelGeometryError(f"Creazione solido driver fallita: {e}") from e

    solid = _orient_along_normal(raw, driver.front_normal, driver.position)
    solid.label = f"driver_{driver.driver.manufacturer}_{driver.driver.model}"
    return solid


def horn_inner_volume(horn: HornBlock):
    """
    Genera il solido della cavità acustica interna della tromba (colonna d'aria).

    Strategia: loft multi-sezione attraverso le N cross-sections del profilo.
    Per trombe folded (fold=1/2), le sezioni cambiano direzione ai punti di
    piega → normale di propagazione consecutiva si inverte (dot < 0).
    In quel caso si divide in segmenti tra pieghe e si crea un Compound.

    Il volume risultante è lo spazio aria INTERNO al cabinet attravarsato
    dall'onda acustica dalla gola (throat) alla bocca (mouth).

    Args:
        horn: HornBlock con sezioni già calcolate.

    Returns:
        build123d.Part (fold=0) o Compound (fold ≥ 1) — volume aria tromba.

    Raises:
        PanelGeometryError: se build123d non disponibile o loft fallisce.
    """
    bd = _bd()
    sections = horn.sections
    if len(sections) < 2:
        raise PanelGeometryError(
            "HornBlock deve avere almeno 2 sezioni per il loft (N_SECTIONS >= 2)"
        )

    # Individua fold boundaries: dot di normali consecutive < 0
    fold_cut = []
    for i in range(len(sections) - 1):
        d = float(np.dot(sections[i].normal, sections[i + 1].normal))
        if d < 0:
            fold_cut.append(i + 1)  # prima sezione del nuovo segmento

    # Gruppi di indici per segmento
    starts = [0] + fold_cut
    ends = fold_cut + [len(sections)]
    groups = [list(range(starts[k], ends[k])) for k in range(len(starts))]

    def _sec_face(sec):
        """Face build123d da HornSectionGeometry.vertices (4×3, global space)."""
        v = [bd.Vector(*pt) for pt in sec.vertices]
        wire = bd.Wire(bd.Polyline(*v, close=True))
        return bd.Face(wire)

    # Strategia di loft: pairwise (loft tra sezione i e i+1 per ogni coppia).
    # Motivo: loft multi-sezione con OCCT può produrre volume negativo per
    # espansioni a bassa curvatura iniziale (tractrix). Pairwise = sempre positivo
    # perché ogni coppia è garantita monotonica. Volume totale = somma slice.
    slices = []
    for group in groups:
        for i in range(len(group) - 1):
            si = sections[group[i]]
            sj = sections[group[i + 1]]
            fa = _sec_face(si)
            fb = _sec_face(sj)
            try:
                sl = bd.loft([fa, fb])
            except Exception as e:
                raise PanelGeometryError(
                    f"Loft slice [{group[i]}..{group[i+1]}] fallito: {e}"
                ) from e
            slices.append(sl)

    if not slices:
        raise PanelGeometryError("Nessun slice valido per il loft della tromba.")

    compound = bd.Compound(children=slices)
    compound.label = (
        f"horn_{horn.expansion}_cavity"
        if horn.fold == 0
        else f"horn_{horn.expansion}_cavity_fold{horn.fold}"
    )
    return compound


def horn_wall_shell(horn: HornBlock, skip_errors: bool = True):
    """
    Genera il guscio costruttivo della tromba (pareti + baffles) come
    Compound dei pannelli estrusi.

    Ogni `Panel` in horn.panels è convertito con `panel_to_solid`.
    Per pannelli che attraversano un fold (geometria degenere) viene
    emessa una `PanelGeometryError` silenziata se `skip_errors=True`.

    Nota: i pannelli strip laterali (bottom/top/side_L/side_R) coprono
    le pareti della tromba con step discreti (1 pannello per intervallo di
    sezione). Per panels CNC saranno aggregati e sviluppati in Fase 3.

    Args:
        horn: HornBlock.
        skip_errors: se True, pannelli degeneri vengono saltati (default True).

    Returns:
        build123d.Compound — insieme dei pannelli solidi.

    Raises:
        PanelGeometryError: se build123d non disponibile, o se skip_errors=False
            e almeno un pannello produce errore.
    """
    bd = _bd()
    solids = []
    errors = []
    for panel in horn.panels:
        try:
            s = panel_to_solid(panel)
            solids.append(s)
        except PanelGeometryError as e:
            if skip_errors:
                errors.append(str(e))
            else:
                raise

    if not solids:
        raise PanelGeometryError(
            f"Nessun pannello valido nella tromba (errori: {len(errors)})."
        )

    compound = bd.Compound(children=solids)
    compound.label = f"horn_{horn.expansion}_shell_fold{horn.fold}"
    return compound


# ─── Export ──────────────────────────────────────────────────────────────────


def export_step(solid, path: Union[str, Path], *, scale_to_mm: bool = True) -> Path:
    """
    Esporta un solido in formato STEP (AP214/AP242).

    Args:
        solid: Part / Compound build123d.
        path: percorso file (.step o .stp).
        scale_to_mm: se True (default) scala da metri a millimetri prima
            dell'export. STEP è agnostico ma la convenzione CAD industriale
            è il millimetro — apertura in FreeCAD/Fusion sarà nelle giuste
            dimensioni.

    Returns:
        Path al file scritto.
    """
    bd = _bd()
    path = Path(path)
    if scale_to_mm:
        scaled = solid.scale(1000.0)
        bd.export_step(scaled, str(path))
    else:
        bd.export_step(solid, str(path))
    return path


def export_stl(solid, path: Union[str, Path], *,
               tolerance: float = 1e-3, angular_tolerance: float = 0.1,
               scale_to_mm: bool = True) -> Path:
    """
    Esporta un solido in formato STL (mesh triangolata).

    Args:
        solid: Part / Compound build123d.
        path: percorso file (.stl).
        tolerance: tolleranza lineare tessellazione (m).
        angular_tolerance: tolleranza angolare tessellazione (rad).
        scale_to_mm: come export_step.

    Returns:
        Path al file scritto.
    """
    bd = _bd()
    path = Path(path)
    target = solid.scale(1000.0) if scale_to_mm else solid
    bd.export_stl(
        target, str(path),
        tolerance=tolerance * (1000.0 if scale_to_mm else 1.0),
        angular_tolerance=angular_tolerance,
    )
    return path
