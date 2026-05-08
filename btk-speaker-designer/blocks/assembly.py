"""
Assembly — composizione di blocchi in un sistema acustico completo.

Un Assembly è una collezione di blocchi (HornBlock, ChamberBlock, PortBlock,
DriverBlock) connessi tramite ConnectionPort. L'Assembly:
- registra blocchi con id univoco
- registra connessioni tra porte di blocchi diversi
- aggrega pannelli, volumi, bounding box
- valida coerenza fisica (area, normali opposte, no overlap volumi)
- serializza/deserializza l'intero progetto

NOTA Fase 1: l'Assembly NON ri-posiziona automaticamente i blocchi nello
spazio sulla base delle connessioni (questo richiede ottimizzazione di
trasformazioni rigide, e sarà il Layer 3). I blocchi vengono aggiunti già
posizionati dall'utente; l'Assembly verifica la consistenza delle
connessioni dichiarate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .base_block import (
    Block, Panel, ConnectionPort, ValidationWarning, Severity,
)


# ─── Connection ──────────────────────────────────────────────────────────────

@dataclass
class Connection:
    """Connessione dichiarata tra due porte di due blocchi distinti."""
    block_a: str        # block_id sorgente
    port_a: str         # nome porta sul blocco a
    block_b: str
    port_b: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "block_a": self.block_a, "port_a": self.port_a,
            "block_b": self.block_b, "port_b": self.port_b,
        }


# ─── Assembly ────────────────────────────────────────────────────────────────

class Assembly:
    """
    Collezione di blocchi e connessioni acustiche.

    Esempio costruzione (sub bass-reflex semplice):
        asm = Assembly(name="Sub 18 reflex")
        asm.add(driver_block, block_id="driver")
        asm.add(chamber_block, block_id="chamber")
        asm.add(port_block, block_id="port")
        asm.connect("driver", "back", "chamber", "front")
        asm.connect("port", "inner", "chamber", "right")
    """

    AREA_TOLERANCE = 0.10   # 10% tolleranza match aree (cutout reali variano)
    POSITION_TOLERANCE = 0.05  # 5 cm

    def __init__(self, name: str = "Untitled") -> None:
        self.name: str = name
        self._blocks: Dict[str, Block] = {}
        self._connections: List[Connection] = []
        self._block_order: List[str] = []  # mantiene ordine inserimento

    # ── Manipolazione ────────────────────────────────────────────────────────

    def add(self, block: Block, *, block_id: Optional[str] = None) -> str:
        """
        Aggiunge un blocco all'assembly. Restituisce il block_id usato.

        Se block_id non specificato, genera "<block_type>_N" (N progressivo).
        """
        if block_id is None:
            base = block.block_type
            n = sum(1 for k in self._blocks if k.startswith(base))
            block_id = f"{base}_{n}"
        if block_id in self._blocks:
            raise ValueError(f"block_id duplicato: {block_id!r}")
        self._blocks[block_id] = block
        self._block_order.append(block_id)
        return block_id

    def remove(self, block_id: str) -> None:
        if block_id not in self._blocks:
            raise KeyError(block_id)
        # Rimuovi anche connessioni associate
        self._connections = [
            c for c in self._connections
            if c.block_a != block_id and c.block_b != block_id
        ]
        del self._blocks[block_id]
        self._block_order.remove(block_id)

    def connect(
        self, block_a: str, port_a: str,
        block_b: str, port_b: str,
    ) -> Connection:
        """Dichiara una connessione tra due porte."""
        if block_a not in self._blocks:
            raise KeyError(f"block_a sconosciuto: {block_a}")
        if block_b not in self._blocks:
            raise KeyError(f"block_b sconosciuto: {block_b}")
        if block_a == block_b:
            raise ValueError("Non si può connettere un blocco a sé stesso")
        ports_a = self._blocks[block_a].connection_ports
        ports_b = self._blocks[block_b].connection_ports
        if port_a not in ports_a:
            raise KeyError(
                f"porta {port_a!r} non esiste su {block_a} "
                f"(disponibili: {list(ports_a)})"
            )
        if port_b not in ports_b:
            raise KeyError(
                f"porta {port_b!r} non esiste su {block_b} "
                f"(disponibili: {list(ports_b)})"
            )
        # Evita doppia connessione sulla stessa porta
        for c in self._connections:
            if (c.block_a == block_a and c.port_a == port_a) or \
               (c.block_b == block_a and c.port_b == port_a) or \
               (c.block_a == block_b and c.port_a == port_b) or \
               (c.block_b == block_b and c.port_b == port_b):
                raise ValueError(
                    f"Porta già usata in altra connessione: "
                    f"{block_a}.{port_a} / {block_b}.{port_b}"
                )
        conn = Connection(block_a, port_a, block_b, port_b)
        self._connections.append(conn)
        return conn

    # ── Accessors ────────────────────────────────────────────────────────────

    @property
    def blocks(self) -> Dict[str, Block]:
        return dict(self._blocks)

    @property
    def block_ids(self) -> List[str]:
        return list(self._block_order)

    @property
    def connections(self) -> List[Connection]:
        return list(self._connections)

    def get(self, block_id: str) -> Block:
        return self._blocks[block_id]

    # ── Aggregazione ─────────────────────────────────────────────────────────

    @property
    def all_panels(self) -> List[Tuple[str, Panel]]:
        """Lista (block_id, Panel) per cutlist e mesh."""
        out: List[Tuple[str, Panel]] = []
        for bid in self._block_order:
            for p in self._blocks[bid].panels:
                out.append((bid, p))
        return out

    @property
    def total_volume(self) -> float:
        """Somma volumi aria interni di tutti i blocchi (m³).

        NOTA: questo è il volume *racchiuso*, non corretto per occupazione
        driver né per intersezioni geometriche. Per volume utile reale
        usare `effective_acoustic_volume` quando disponibile (Layer 3).
        """
        return float(sum(b.internal_volume for b in self._blocks.values()))

    @property
    def bounding_box(self) -> Tuple[float, float, float]:
        """Bounding box globale dell'assembly."""
        all_pts: List[np.ndarray] = []
        for b in self._blocks.values():
            for p in b.panels:
                all_pts.append(p.vertices)
        if not all_pts:
            return (0.0, 0.0, 0.0)
        pts = np.concatenate(all_pts, axis=0)
        ext = pts.max(axis=0) - pts.min(axis=0)
        return (float(ext[0]), float(ext[1]), float(ext[2]))

    # ── Validation ───────────────────────────────────────────────────────────

    def validate(self) -> List[ValidationWarning]:
        """Verifica coerenza fisica dell'assembly."""
        warnings: List[ValidationWarning] = []

        # 1) Validazione di ogni blocco
        for bid, blk in self._blocks.items():
            for w in blk.validate():
                # Annota il blocco di origine nel codice
                w_loc = f"{bid}/{w.location}" if w.location else bid
                warnings.append(ValidationWarning(
                    severity=w.severity, code=w.code, message=w.message,
                    location=w_loc,
                ))

        # 2) Validazione connessioni
        for c in self._connections:
            blk_a = self._blocks[c.block_a]
            blk_b = self._blocks[c.block_b]
            port_a = blk_a.connection_ports[c.port_a]
            port_b = blk_b.connection_ports[c.port_b]
            # Aree compatibili (entro tolleranza)
            ratio = port_a.area / port_b.area if port_b.area > 0 else 0
            if not (1 - self.AREA_TOLERANCE <= ratio <= 1 + self.AREA_TOLERANCE):
                warnings.append(ValidationWarning(
                    Severity.WARNING, "CONNECTION_AREA_MISMATCH",
                    f"Aree porta non corrispondono: "
                    f"{c.block_a}.{c.port_a}={port_a.area*1e4:.1f} cm² vs "
                    f"{c.block_b}.{c.port_b}={port_b.area*1e4:.1f} cm² "
                    f"(rapporto {ratio:.2f}).",
                    location=f"{c.block_a}.{c.port_a}<->{c.block_b}.{c.port_b}",
                ))
            # Normali opposte (≈ -1 dot product) — porte connesse si guardano
            dot = float(np.dot(port_a.normal, port_b.normal))
            if dot > -0.5:  # accetta fino a 60° di disallineamento
                warnings.append(ValidationWarning(
                    Severity.WARNING, "CONNECTION_NORMAL_MISALIGNED",
                    f"Normali porta non opposte: dot={dot:+.2f}. "
                    f"Riposiziona/orienta i blocchi connessi.",
                    location=f"{c.block_a}.{c.port_a}<->{c.block_b}.{c.port_b}",
                ))
            # Distanza posizioni (le porte connesse dovrebbero coincidere)
            dist = float(np.linalg.norm(port_a.position - port_b.position))
            if dist > self.POSITION_TOLERANCE:
                warnings.append(ValidationWarning(
                    Severity.INFO, "CONNECTION_POSITION_GAP",
                    f"Porte connesse a distanza {dist*1000:.0f} mm "
                    f"(tol {self.POSITION_TOLERANCE*1000:.0f} mm). "
                    f"Riposiziona blocchi o accetta gap come spessore pannello.",
                    location=f"{c.block_a}.{c.port_a}<->{c.block_b}.{c.port_b}",
                ))

        # 3) Connessioni mancanti per blocchi che richiedono accoppiamento
        # Heuristica: ogni HornBlock dovrebbe avere "throat" connesso
        for bid in self._block_order:
            blk = self._blocks[bid]
            if blk.block_type == "horn":
                if not self._port_is_connected(bid, "throat"):
                    warnings.append(ValidationWarning(
                        Severity.WARNING, "HORN_THROAT_NOT_CONNECTED",
                        f"Horn '{bid}' senza connessione alla gola: "
                        f"manca DriverBlock o ChamberBlock connesso.",
                        location=bid,
                    ))
            if blk.block_type == "driver":
                if not self._port_is_connected(bid, "front") and \
                   not self._port_is_connected(bid, "back"):
                    warnings.append(ValidationWarning(
                        Severity.INFO, "DRIVER_NOT_CONNECTED",
                        f"Driver '{bid}' senza connessioni: probabilmente "
                        f"emette in spazio libero.",
                        location=bid,
                    ))

        return warnings

    def _port_is_connected(self, block_id: str, port_name: str) -> bool:
        for c in self._connections:
            if (c.block_a == block_id and c.port_a == port_name) or \
               (c.block_b == block_id and c.port_b == port_name):
                return True
        return False

    # ── Serializzazione ──────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "blocks": [
                {"id": bid, **self._blocks[bid].to_dict()}
                for bid in self._block_order
            ],
            "connections": [c.to_dict() for c in self._connections],
        }

    def __repr__(self) -> str:
        return (
            f"Assembly(name={self.name!r}, "
            f"blocks={len(self._blocks)}, "
            f"connections={len(self._connections)})"
        )
