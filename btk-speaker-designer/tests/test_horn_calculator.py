"""
Test per il modulo horn_calculator.
Verifica la correttezza delle formule di calcolo della tromba acustica.
"""

import sys
import os
import math
import pytest
import numpy as np

# Aggiunge il path del progetto
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from btk_speaker_designer.core.horn_calculator import (
    calculate_flare_rate,
    calculate_throat_area,
    calculate_mouth_area,
    calculate_horn_length,
    area_at_position,
    calculate_throat_impedance,
    calculate_coupling_volume,
    calculate_horn_sections,
    design_horn,
    horn_frequency_response,
)
from btk_speaker_designer.core.constants import (
    SPEED_OF_SOUND, AIR_DENSITY,
    EXPANSION_EXPONENTIAL, EXPANSION_CONICAL,
    NUM_HORN_SECTIONS
)


class TestFlareRate:
    """Test per il calcolo del flare rate."""

    def test_basic_calculation(self):
        """Testa calcolo base flare rate esponenziale."""
        m = calculate_flare_rate(70.0, SPEED_OF_SOUND, EXPANSION_EXPONENTIAL)
        # m = 4π * fc / c
        expected = 4 * math.pi * 70.0 / SPEED_OF_SOUND
        assert abs(m - expected) < 1e-6

    def test_reference_values(self):
        """Testa con i valori di riferimento del foglio Excel."""
        # Dal foglio originale: fc=70Hz, c=342.016, m≈2.5706
        m = calculate_flare_rate(70.0, 342.016, EXPANSION_EXPONENTIAL)
        assert abs(m - 2.5706) < 0.005, f"Atteso ~2.5706, ottenuto {m:.4f}"

    def test_proportional_to_frequency(self):
        """Il flare rate deve essere proporzionale alla frequenza."""
        m1 = calculate_flare_rate(100.0, SPEED_OF_SOUND)
        m2 = calculate_flare_rate(200.0, SPEED_OF_SOUND)
        assert abs(m2 / m1 - 2.0) < 0.001, "m deve essere proporzionale a fc"

    def test_different_expansion_types(self):
        """Diversi tipi di espansione producono flare rate diversi."""
        m_exp = calculate_flare_rate(100.0, SPEED_OF_SOUND, EXPANSION_EXPONENTIAL)
        m_con = calculate_flare_rate(100.0, SPEED_OF_SOUND, EXPANSION_CONICAL)
        assert m_exp != m_con


class TestHornAreas:
    """Test per il calcolo delle aree gola e bocca."""

    def test_throat_area_no_compression(self):
        """Senza compressione, area gola = area diaframma."""
        sd = 0.091  # 18" woofer
        s_throat = calculate_throat_area(sd, compression_ratio=1.0)
        assert abs(s_throat - sd) < 1e-10

    def test_throat_area_with_compression(self):
        """Con rapporto compressione, area gola è ridotta."""
        sd = 0.091
        s_throat = calculate_throat_area(sd, compression_ratio=4.0)
        assert abs(s_throat - sd / 4.0) < 1e-10

    def test_mouth_area_ratio(self):
        """Area bocca = area gola × rapporto."""
        s_throat = 0.05
        ratio = 3.5
        s_mouth = calculate_mouth_area(s_throat, ratio)
        assert abs(s_mouth / s_throat - ratio) < 1e-10

    def test_mouth_area_greater_than_throat(self):
        """Area bocca sempre maggiore di area gola per ratio > 1."""
        s_throat = 0.02
        s_mouth = calculate_mouth_area(s_throat, 2.0)
        assert s_mouth > s_throat


class TestHornLength:
    """Test per il calcolo della lunghezza tromba."""

    def test_exponential_formula(self):
        """Testa la formula ln(Smouth/Sthroat) / m."""
        s_throat = 0.05
        s_mouth = 0.10  # ratio = 2
        m = 2.5706
        L = calculate_horn_length(s_throat, s_mouth, m, EXPANSION_EXPONENTIAL)
        expected = math.log(2.0) / m
        assert abs(L - expected) < 1e-6

    def test_reference_values(self):
        """Testa con valori di riferimento dal foglio Excel."""
        # Dal foglio: S0=0.9503m², Smouth=S0*2=1.9006, m=2.5706, L≈0.2696m
        s_throat = 0.9503
        s_mouth = s_throat * 2.0
        m = 2.5706
        L = calculate_horn_length(s_throat, s_mouth, m)
        assert abs(L - 0.2696) < 0.001, f"Atteso ~0.2696m, ottenuto {L:.4f}m"

    def test_length_positive(self):
        """La lunghezza deve essere sempre positiva per ratio > 1."""
        L = calculate_horn_length(0.01, 0.02, 3.0)
        assert L > 0

    def test_zero_flare_rate_raises(self):
        """Flare rate = 0 deve sollevare un errore."""
        with pytest.raises(ValueError):
            calculate_horn_length(0.01, 0.02, 0.0)


class TestAreaAtPosition:
    """Test per il calcolo dell'area in una posizione."""

    def test_at_throat(self):
        """Area alla gola (x=0) deve essere uguale a S_throat."""
        s_throat = 0.05
        area = area_at_position(0, s_throat, 2.5706)
        assert abs(area - s_throat) < 1e-10

    def test_exponential_growth(self):
        """L'area deve crescere esponenzialmente per exp."""
        s_throat = 0.01
        m = 2.0
        x = 0.5
        area = area_at_position(x, s_throat, m, EXPANSION_EXPONENTIAL)
        expected = s_throat * math.exp(m * x)
        assert abs(area - expected) < 1e-10

    def test_area_increases_with_x(self):
        """L'area deve aumentare con la distanza dalla gola."""
        s_throat = 0.01
        m = 2.0
        areas = [area_at_position(x, s_throat, m) for x in [0, 0.1, 0.2, 0.3]]
        assert all(areas[i] < areas[i+1] for i in range(len(areas)-1))


class TestThroatImpedance:
    """Test per il calcolo dell'impedenza alla gola."""

    def test_formula(self):
        """Testa la formula Z = rho * c / S_throat."""
        s_throat = 0.1
        Z = calculate_throat_impedance(s_throat, SPEED_OF_SOUND, AIR_DENSITY)
        expected = (AIR_DENSITY * SPEED_OF_SOUND) / s_throat
        assert abs(Z - expected) < 1e-6

    def test_zero_area_raises(self):
        """Area gola = 0 deve sollevare un errore."""
        with pytest.raises(ValueError):
            calculate_throat_impedance(0.0)


class TestDesignHorn:
    """Test per la funzione principale design_horn."""

    def test_returns_geometry_object(self):
        """design_horn deve restituire un oggetto HornGeometry."""
        from btk_speaker_designer.core.horn_calculator import HornGeometry
        geom = design_horn(70.0, 0.091, 2.0)
        assert isinstance(geom, HornGeometry)

    def test_sections_count(self):
        """Il numero di sezioni deve corrispondere a NUM_HORN_SECTIONS."""
        geom = design_horn(70.0, 0.091, 2.0, n_sections=NUM_HORN_SECTIONS)
        assert len(geom.sections) == NUM_HORN_SECTIONS

    def test_consistency_areas(self):
        """Area bocca / area gola deve essere uguale al rapporto specificato."""
        ratio = 2.5
        geom = design_horn(70.0, 0.091, ratio)
        computed_ratio = geom.mouth_area_m2 / geom.throat_area_m2
        assert abs(computed_ratio - ratio) < 0.01

    def test_cutoff_frequency_preserved(self):
        """La frequenza di taglio deve essere preservata."""
        fc = 85.0
        geom = design_horn(fc, 0.091)
        assert geom.cutoff_frequency_hz == fc

    def test_reference_case(self):
        """Testa con il caso di riferimento del foglio Excel."""
        # Parametri dal foglio:
        # Fc=70Hz, c=342.016, Sd=0.091m² (circa 18"), ratio=2.0
        geom = design_horn(
            cutoff_freq_hz=70.0,
            driver_sd_m2=0.091,
            smouth_sthroat_ratio=2.0,
            c=342.016
        )
        # Il flare rate deve essere circa 2.5706
        assert abs(geom.flare_rate_m - 2.5706) < 0.01
        # La lunghezza deve essere circa 0.27m
        assert 0.25 < geom.horn_length_m < 0.30

    def test_horn_length_positive(self):
        """La lunghezza tromba deve essere sempre positiva."""
        geom = design_horn(50.0, 0.05, 3.0)
        assert geom.horn_length_m > 0

    def test_coupling_volume_positive(self):
        """Il volume di accoppiamento deve essere positivo."""
        geom = design_horn(70.0, 0.091, 2.0)
        assert geom.coupling_volume_m3 > 0


class TestHornFrequencyResponse:
    """Test per la risposta in frequenza della tromba."""

    def setup_method(self):
        """Prepara una geometria per i test."""
        self.geom = design_horn(70.0, 0.091, 2.0)
        self.frequencies = np.array([20, 50, 70, 100, 200, 500, 1000, 5000])

    def test_returns_arrays(self):
        """La funzione deve restituire due array numpy."""
        amplitude, phase = horn_frequency_response(self.frequencies, self.geom)
        assert isinstance(amplitude, np.ndarray)
        assert isinstance(phase, np.ndarray)
        assert len(amplitude) == len(self.frequencies)

    def test_attenuation_below_cutoff(self):
        """Sotto la frequenza di taglio, deve esserci forte attenuazione."""
        freq_below = np.array([20.0, 50.0])
        amplitude, _ = horn_frequency_response(freq_below, self.geom)
        assert all(amplitude < -10), "Attenuazione insufficiente sotto Fc"

    def test_gain_above_cutoff(self):
        """Sopra la frequenza di taglio, l'ampiezza deve essere vicina a 0dB."""
        freq_above = np.array([200.0, 500.0, 1000.0])
        amplitude, _ = horn_frequency_response(freq_above, self.geom)
        # Deve essere vicino a 0 dB (non molto negativo)
        assert all(amplitude > -5), f"Guadagno troppo basso sopra Fc: {amplitude}"
