"""
Proprietà dei materiali da costruzione per casse acustiche.
Condiviso tra SubSim e BTK Speaker Designer.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Material:
    """Rappresenta un materiale da costruzione con le sue proprietà fisiche e acustiche."""

    name: str
    density: float          # kg/m³
    sound_speed: float      # m/s (velocità del suono nel materiale)
    young_modulus: float    # GPa
    loss_factor: float      # fattore di perdita interna (smorzamento)
    description: str = ""

    # Coefficienti di assorbimento acustico per banda di ottava
    # Chiavi: frequenza centrale in Hz, valori: coefficiente 0.0-1.0
    absorption_coefficients: Dict[int, float] = field(default_factory=dict)

    def absorption_at(self, frequency: int) -> float:
        """Restituisce il coefficiente di assorbimento alla frequenza più vicina."""
        if not self.absorption_coefficients:
            return 0.05  # valore di default
        freqs = list(self.absorption_coefficients.keys())
        nearest = min(freqs, key=lambda f: abs(f - frequency))
        return self.absorption_coefficients[nearest]

    def surface_mass(self, thickness_m: float) -> float:
        """Calcola la densità superficiale di massa in kg/m²."""
        return self.density * thickness_m


# Database materiali comuni per costruzione casse acustiche
MATERIALS: Dict[str, Material] = {
    "mdf_18mm": Material(
        name="MDF 18mm",
        density=750,
        sound_speed=1100,
        young_modulus=3.5,
        loss_factor=0.02,
        description="Pannello MDF standard 18mm - materiale più comune per casse acustiche",
        absorption_coefficients={
            125: 0.10, 250: 0.15, 500: 0.20, 1000: 0.25, 2000: 0.30, 4000: 0.35
        }
    ),
    "mdf_25mm": Material(
        name="MDF 25mm",
        density=750,
        sound_speed=1100,
        young_modulus=3.5,
        loss_factor=0.02,
        description="Pannello MDF rinforzato 25mm - per casse professionali",
        absorption_coefficients={
            125: 0.08, 250: 0.12, 500: 0.18, 1000: 0.22, 2000: 0.28, 4000: 0.32
        }
    ),
    "multiplex_birch_15mm": Material(
        name="Multiplex Betulla 15mm",
        density=620,
        sound_speed=4500,
        young_modulus=10.0,
        loss_factor=0.015,
        description="Multistrato di betulla 15mm - leggero e rigido, ideale per trasporto",
        absorption_coefficients={
            125: 0.12, 250: 0.18, 500: 0.22, 1000: 0.28, 2000: 0.32, 4000: 0.38
        }
    ),
    "multiplex_birch_18mm": Material(
        name="Multiplex Betulla 18mm",
        density=620,
        sound_speed=4500,
        young_modulus=10.0,
        loss_factor=0.015,
        description="Multistrato di betulla 18mm - standard professionale",
        absorption_coefficients={
            125: 0.10, 250: 0.15, 500: 0.20, 1000: 0.25, 2000: 0.30, 4000: 0.35
        }
    ),
    "plywood_standard_18mm": Material(
        name="Compensato Standard 18mm",
        density=600,
        sound_speed=4200,
        young_modulus=8.0,
        loss_factor=0.018,
        description="Compensato standard economico",
        absorption_coefficients={
            125: 0.12, 250: 0.17, 500: 0.22, 1000: 0.27, 2000: 0.32, 4000: 0.37
        }
    ),
    "fiberglass_8mm": Material(
        name="Fibra di Vetro 8mm",
        density=1800,
        sound_speed=3200,
        young_modulus=20.0,
        loss_factor=0.010,
        description="Pannello in fibra di vetro - per trombe e applicazioni outdoor",
        absorption_coefficients={
            125: 0.05, 250: 0.08, 500: 0.10, 1000: 0.12, 2000: 0.15, 4000: 0.18
        }
    ),
    "steel_2mm": Material(
        name="Acciaio 2mm",
        density=7850,
        sound_speed=5200,
        young_modulus=210.0,
        loss_factor=0.001,
        description="Lamiera di acciaio 2mm - per driver e componenti metallici",
        absorption_coefficients={
            125: 0.02, 250: 0.02, 500: 0.03, 1000: 0.03, 2000: 0.04, 4000: 0.04
        }
    ),
    "acoustic_foam_50mm": Material(
        name="Schiuma Acustica 50mm",
        density=30,
        sound_speed=340,
        young_modulus=0.01,
        loss_factor=0.50,
        description="Schiuma acustica fonoassorbente 50mm",
        absorption_coefficients={
            125: 0.15, 250: 0.35, 500: 0.65, 1000: 0.85, 2000: 0.90, 4000: 0.92
        }
    ),
}


def get_material(name: str) -> Optional[Material]:
    """
    Recupera un materiale dal database per nome.

    Args:
        name: Nome del materiale (chiave nel dizionario MATERIALS)

    Returns:
        Oggetto Material o None se non trovato
    """
    return MATERIALS.get(name)


def list_materials() -> List[str]:
    """
    Restituisce la lista di tutti i materiali disponibili.

    Returns:
        Lista di nomi dei materiali
    """
    return list(MATERIALS.keys())


def get_panel_cost(
    width_m: float,
    height_m: float,
    material_name: str = "mdf_18mm",
    price_per_m2: float = 30.0
) -> float:
    """
    Calcola il costo di un pannello dato materiale e prezzo.

    Args:
        width_m: Larghezza in metri
        height_m: Altezza in metri
        material_name: Nome del materiale
        price_per_m2: Prezzo per m² in Euro

    Returns:
        Costo del pannello in Euro
    """
    area = width_m * height_m
    return area * price_per_m2
