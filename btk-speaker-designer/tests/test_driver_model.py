"""
Test per il modulo driver_model.
Verifica la correttezza del modello driver e dei calcoli T&S.
"""

import sys
import os
import math
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from btk_speaker_designer.core.driver_model import (
    DriverModel,
    calculate_driver_efficiency,
    calculate_sensitivity_from_ts,
)


class TestDriverModel:
    """Test per il modello driver DriverModel."""

    def make_sub(self) -> DriverModel:
        """Crea un driver di esempio per i test."""
        return DriverModel(
            manufacturer="Test",
            model="TS18",
            driver_type="subwoofer",
            fs=50.0,
            re=8.0,
            qes=0.5,
            qms=4.0,
            vas=100.0,
            sd=0.091,
            xmax=12.0,
            bl=12.0,
            mms=50.0,
            le=1.0,
            spl_1w_1m=98.0,
            power_rms=500.0,
            impedance_nominal=8.0,
            diameter_inch=18.0,
        )

    def test_qts_calculation(self):
        """Qts deve essere calcolato automaticamente da Qes e Qms."""
        driver = self.make_sub()
        qes, qms = 0.5, 4.0
        expected_qts = (qes * qms) / (qes + qms)
        assert abs(driver.qts - expected_qts) < 1e-6

    def test_power_program_auto(self):
        """Potenza programma deve essere 2x potenza RMS se non specificata."""
        driver = self.make_sub()
        assert abs(driver.power_program - driver.power_rms * 2) < 0.1

    def test_power_peak_auto(self):
        """Potenza picco deve essere 4x potenza RMS se non specificata."""
        driver = self.make_sub()
        assert abs(driver.power_peak - driver.power_rms * 4) < 0.1

    def test_sd_cm2_conversion(self):
        """Conversione da m² a cm² deve essere corretta."""
        driver = self.make_sub()
        assert abs(driver.sd_cm2 - driver.sd * 10000) < 0.001

    def test_xmax_meter_conversion(self):
        """Conversione Xmax da mm a m deve essere corretta."""
        driver = self.make_sub()
        assert abs(driver.xmax_m - driver.xmax / 1000) < 1e-9

    def test_diameter_meter_conversion(self):
        """Conversione diametro da pollici a m deve essere corretta."""
        driver = self.make_sub()
        expected = driver.diameter_inch * 0.0254
        assert abs(driver.diameter_m - expected) < 1e-9

    def test_max_spl(self):
        """Max SPL con potenza nominale deve essere corretto."""
        driver = self.make_sub()
        expected = driver.spl_1w_1m + 10 * math.log10(driver.power_rms)
        assert abs(driver.max_spl_1m() - expected) < 0.01

    def test_max_spl_custom_power(self):
        """Max SPL con potenza custom deve essere corretto."""
        driver = self.make_sub()
        custom_power = 1000.0
        expected = driver.spl_1w_1m + 10 * math.log10(custom_power)
        assert abs(driver.max_spl_1m(custom_power) - expected) < 0.01

    def test_impedance_calculation(self):
        """La risposta di impedenza deve avere il picco alla frequenza Fs."""
        driver = self.make_sub()
        frequencies = np.logspace(1, 4, 500)
        impedance = driver.calculate_impedance(frequencies)

        # Verifica che ci sia un picco intorno a Fs
        fs_idx = np.argmin(np.abs(frequencies - driver.fs))
        max_idx = np.argmax(impedance)

        # Il picco deve essere vicino a Fs (entro 2 ottave)
        assert abs(np.log2(frequencies[max_idx]) - np.log2(driver.fs)) < 2.0

    def test_str_representation(self):
        """La rappresentazione testuale deve includere produttore e modello."""
        driver = self.make_sub()
        s = str(driver)
        assert "Test" in s
        assert "TS18" in s

    def test_to_dict_serializable(self):
        """to_dict deve restituire un dizionario serializzabile."""
        import json
        driver = self.make_sub()
        d = driver.to_dict()
        assert isinstance(d, dict)
        # Deve essere serializzabile in JSON
        json_str = json.dumps(d)
        assert json_str is not None

    def test_from_dict_roundtrip(self):
        """from_dict deve ricreare il driver correttamente."""
        driver = self.make_sub()
        d = driver.to_dict()
        driver2 = DriverModel.from_dict(d)
        assert driver2.manufacturer == driver.manufacturer
        assert driver2.model == driver.model
        assert abs(driver2.fs - driver.fs) < 0.001


class TestDriverEfficiency:
    """Test per il calcolo dell'efficienza del driver."""

    def test_efficiency_positive(self):
        """L'efficienza di riferimento deve essere un valore positivo."""
        driver = DriverModel(
            manufacturer="Test", model="X", driver_type="subwoofer",
            fs=50.0, qes=0.5, vas=100.0, sd=0.091
        )
        eta = calculate_driver_efficiency(driver)
        assert eta > 0

    def test_efficiency_reasonable_range(self):
        """L'efficienza tipica è tra 0.001% e 1%."""
        driver = DriverModel(
            manufacturer="Test", model="X", driver_type="subwoofer",
            fs=50.0, qes=0.3, vas=150.0, sd=0.091
        )
        eta = calculate_driver_efficiency(driver)
        assert 0.00001 < eta < 0.1, f"Efficienza fuori range: {eta}"

    def test_sensitivity_from_ts(self):
        """La sensibilità calcolata deve essere in un range realistico."""
        driver = DriverModel(
            manufacturer="Test", model="X", driver_type="subwoofer",
            fs=50.0, qes=0.3, vas=150.0, sd=0.091
        )
        spl = calculate_sensitivity_from_ts(driver)
        assert 80 < spl < 115, f"Sensibilità fuori range: {spl}"

    def test_zero_params_returns_zero(self):
        """Parametri a zero devono restituire efficienza zero."""
        driver = DriverModel(
            manufacturer="Test", model="X",
            fs=0.0, qes=0.5, vas=100.0
        )
        eta = calculate_driver_efficiency(driver)
        assert eta == 0.0
