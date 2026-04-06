"""
Test per il modulo phase_summing.
Verifica il calcolo della somma in fase fronte/retro.
"""

import sys
import os
import math
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from btk_speaker_designer.core.phase_summing import (
    calculate_phase_delay,
    sum_front_back_radiation,
    calculate_back_radiation_spl,
    calculate_path_difference,
    find_interference_frequencies,
    calculate_combined_response,
)


class TestPhaseDelay:
    """Test per il calcolo del ritardo di fase."""

    def test_zero_path_zero_delay(self):
        """Con cammino zero, il ritardo deve essere zero."""
        freqs = np.array([100.0, 500.0, 1000.0])
        delay = calculate_phase_delay(0.0, freqs)
        np.testing.assert_array_almost_equal(delay, 0.0)

    def test_delay_proportional_to_frequency(self):
        """Il ritardo deve essere proporzionale alla frequenza."""
        path = 0.343  # 1ms a 343 m/s
        delay_100 = calculate_phase_delay(path, np.array([100.0]))
        delay_200 = calculate_phase_delay(path, np.array([200.0]))
        assert abs(delay_200[0] / delay_100[0] - 2.0) < 0.001

    def test_wavelength_equals_2pi(self):
        """Per un percorso = lunghezza d'onda, il ritardo deve essere 2π."""
        c = 343.0
        f = 100.0
        wavelength = c / f  # 3.43 m
        delay = calculate_phase_delay(wavelength, np.array([f]), c)
        assert abs(delay[0] - 2 * math.pi) < 0.001


class TestSumFrontBack:
    """Test per la somma fronte/retro."""

    def setup_method(self):
        """Prepara frequenze e SPL di test."""
        self.freqs = np.logspace(np.log10(50), np.log10(5000), 100)
        self.front_spl = np.full_like(self.freqs, 100.0)
        self.back_spl = np.full_like(self.freqs, 94.0)  # -6dB

    def test_returns_result_object(self):
        """Deve restituire un oggetto PhaseSummingResult."""
        from btk_speaker_designer.core.phase_summing import PhaseSummingResult
        result = sum_front_back_radiation(
            self.freqs, self.front_spl, self.back_spl, 0.3
        )
        assert isinstance(result, PhaseSummingResult)

    def test_combined_arrays_same_length(self):
        """Tutti gli array del risultato devono avere la stessa lunghezza."""
        result = sum_front_back_radiation(
            self.freqs, self.front_spl, self.back_spl, 0.3
        )
        n = len(self.freqs)
        assert len(result.combined_spl) == n
        assert len(result.phase_difference) == n
        assert len(result.interference_type) == n

    def test_in_phase_constructive(self):
        """In fase (path=0), pressioni uguali → +6dB rispetto al solo fronte."""
        freqs = np.array([100.0])
        front = np.array([100.0])
        back = np.array([100.0])
        # In fase: back_phase_offset=0 (stesso della frontale)
        result = sum_front_back_radiation(
            freqs, front, back, path_difference_m=0.0,
            front_phase_offset=0.0, back_phase_offset=0.0
        )
        # Due segnali uguali in fase → +6dB (20*log10(2) ≈ 6.02)
        assert abs(result.combined_spl[0] - 106.02) < 0.1

    def test_out_of_phase_cancellation(self):
        """In opposizione di fase (path=λ/2), deve esserci cancellazione."""
        c = 343.0
        f = 100.0
        half_wavelength = c / (2 * f)
        freqs = np.array([f])
        front = np.array([100.0])
        back = np.array([100.0])
        result = sum_front_back_radiation(
            freqs, front, back, path_difference_m=half_wavelength,
            front_phase_offset=0.0, back_phase_offset=0.0
        )
        # Cancellazione: SPL deve essere molto basso
        assert result.combined_spl[0] < 80.0

    def test_path_difference_stored(self):
        """La differenza di cammino deve essere memorizzata nel risultato."""
        path = 0.45
        result = sum_front_back_radiation(
            self.freqs, self.front_spl, self.back_spl, path
        )
        assert abs(result.path_difference_m - path) < 1e-10


class TestBackRadiationSPL:
    """Test per il calcolo dell'SPL emissione posteriore."""

    def test_lower_than_front(self):
        """L'emissione posteriore deve essere inferiore a quella frontale."""
        freqs = np.array([100.0, 500.0, 1000.0])
        front = np.array([100.0, 100.0, 100.0])
        back = calculate_back_radiation_spl(front, freqs, damping_factor=0.5)
        assert all(back < front)

    def test_damping_factor_zero(self):
        """Con damping=0, l'emissione posteriore deve essere uguale alla frontale."""
        freqs = np.array([100.0])
        front = np.array([100.0])
        back = calculate_back_radiation_spl(front, freqs, damping_factor=0.0)
        # -0dB = uguale al fronte (a basse frequenze, prima del breakup)
        assert back[0] >= front[0] - 1.0

    def test_high_freq_attenuation(self):
        """A frequenze alte, deve esserci maggiore attenuazione."""
        freqs = np.array([100.0, 4000.0])
        front = np.full(2, 100.0)
        back = calculate_back_radiation_spl(front, freqs, damping_factor=0.5)
        # A 4kHz deve esserci più attenuazione che a 100Hz
        assert back[1] < back[0]


class TestInterferenceFrequencies:
    """Test per la ricerca delle frequenze di interferenza."""

    def test_fundamental_frequency(self):
        """La frequenza fondamentale deve essere c/path."""
        c = 343.0
        path = 0.343  # lambda = 1m
        result = find_interference_frequencies(path, c, f_min=50, f_max=5000)
        assert abs(result["fundamental_hz"] - c / path) < 0.01

    def test_constructive_at_multiple_wavelengths(self):
        """Interferenza costruttiva a multipli interi della lunghezza d'onda."""
        c = 343.0
        path = 1.0
        result = find_interference_frequencies(path, c, f_min=50, f_max=5000)
        # Prima frequenza costruttiva ≈ c/path = 343 Hz
        if result["constructive_hz"]:
            f1 = result["constructive_hz"][0]
            assert abs(f1 - 343.0) < 5.0

    def test_result_has_required_keys(self):
        """Il risultato deve avere le chiavi richieste."""
        result = find_interference_frequencies(0.5, 343.0)
        assert "constructive_hz" in result
        assert "destructive_hz" in result
        assert "fundamental_hz" in result


class TestPathDifference:
    """Test per il calcolo della differenza di cammino."""

    def test_basic_calculation(self):
        """Test del calcolo base della differenza di cammino."""
        path = calculate_path_difference(
            horn_length_m=0.5,
            driver_depth_m=0.05,
            baffle_to_driver_m=0.0
        )
        assert abs(path - 0.55) < 0.001

    def test_longer_horn_longer_path(self):
        """Una tromba più lunga produce una differenza di cammino maggiore."""
        path_short = calculate_path_difference(0.3, 0.05)
        path_long = calculate_path_difference(0.8, 0.05)
        assert path_long > path_short
