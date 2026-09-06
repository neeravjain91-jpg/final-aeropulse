"""Virtual ADC (Analog-to-Digital Converter) and Digital Sensor Interface.

Models resolution quantization (10-bit, 12-bit, 16-bit), reference voltage scaling,
input saturation, conversion times, and four-tier signal traceability:
Simulated Physical Quantity -> Sensor Output -> ADC Counts -> ECU Observed Value.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ADCChannelConfig:
    """Configuration for an individual ADC conversion channel or digital sensor bus."""
    channel_name: str
    resolution_bits: int = 12  # Standard 12-bit ADC (4096 levels)
    v_ref_volts: float = 5.0
    input_v_min: float = 0.0
    input_v_max: float = 5.0
    engineering_min: float = 0.0
    engineering_max: float = 100.0
    is_digital_bus: bool = False  # True for direct digital I2C/SPI transducers
    digital_word_bits: int = 16


@dataclass
class ADCConversionResult:
    """Four-tier auditable traceability for an ADC / Sensor conversion cycle."""
    channel_name: str
    simulated_physical_value: float
    sensor_analog_voltage: Optional[float]
    adc_digital_counts: Optional[int]
    ecu_observed_value: Optional[float]
    is_saturated: bool
    conversion_valid: bool
    resolution_bits: int


class VirtualADCSystem:
    """
    Simulates onboard airborne micro-controller ADC peripherals and digital sensor interfaces.
    """

    DEFAULT_ADC_CONFIGS = {
        "Engine_RPM": ADCChannelConfig("Engine_RPM", 16, 5.0, 0.0, 5.0, 0.0, 6500.0, is_digital_bus=True),  # Optical/Hall pulse counter
        "EGT1": ADCChannelConfig("EGT1", 12, 5.0, 0.0, 5.0, 0.0, 1650.0),  # Thermocouple amplifier
        "EGT2": ADCChannelConfig("EGT2", 12, 5.0, 0.0, 5.0, 0.0, 1650.0),
        "EGT3": ADCChannelConfig("EGT3", 12, 5.0, 0.0, 5.0, 0.0, 1650.0),
        "CHT": ADCChannelConfig("CHT", 12, 5.0, 0.0, 5.0, 0.0, 500.0),  # RTD / Thermocouple amplifier
        "Fuel_Flow": ADCChannelConfig("Fuel_Flow", 12, 5.0, 0.0, 5.0, 0.0, 60.0),
        "Oil_Temp": ADCChannelConfig("Oil_Temp", 12, 5.0, 0.0, 5.0, -40.0, 350.0),
        "Oil_Pressure": ADCChannelConfig("Oil_Pressure", 12, 5.0, 0.5, 4.5, 0.0, 150.0),  # 0.5V - 4.5V ratiometric transducer
        "Battery_Voltage": ADCChannelConfig("Battery_Voltage", 12, 5.0, 0.0, 5.0, 0.0, 36.0),  # Resistor voltage divider
        "Battery_Current": ADCChannelConfig("Battery_Current", 12, 5.0, 0.0, 5.0, -50.0, 100.0),  # Hall current sensor
        "Alternator_Temp": ADCChannelConfig("Alternator_Temp", 12, 5.0, 0.0, 5.0, -40.0, 300.0),
        "EFI_Fuel_Temp": ADCChannelConfig("EFI_Fuel_Temp", 16, 3.3, 0.0, 3.3, -40.0, 200.0, is_digital_bus=True),
        "EFI_Water_Temp": ADCChannelConfig("EFI_Water_Temp", 16, 3.3, 0.0, 3.3, -40.0, 300.0, is_digital_bus=True),
        "MAP_Injector": ADCChannelConfig("MAP_Injector", 12, 5.0, 0.5, 4.5, 0.0, 120.0),
        "Vibration": ADCChannelConfig("Vibration", 12, 5.0, 0.0, 5.0, 0.0, 25.0),  # Piezo / MEMS analog accelerometer
        "Knock_Intensity": ADCChannelConfig("Knock_Intensity", 10, 3.3, 0.0, 3.3, 0.0, 1.0),
    }

    def __init__(self, channel_configs: Optional[Dict[str, ADCChannelConfig]] = None):
        self.channels = channel_configs or dict(self.DEFAULT_ADC_CONFIGS)

    def convert_channel(self, channel_name: str, sensor_value: Optional[float]) -> ADCConversionResult:
        """
        Executes four-tier conversion for an individual channel:
        1. Simulated physical value
        2. Sensor analog voltage (or digital packet)
        3. ADC quantized integer counts
        4. ECU reconstructed engineering value
        """
        if channel_name not in self.channels:
            # Pass-through for non-ADC parameters (e.g. Operating_State)
            return ADCConversionResult(
                channel_name=channel_name,
                simulated_physical_value=sensor_value or 0.0,
                sensor_analog_voltage=None,
                adc_digital_counts=None,
                ecu_observed_value=sensor_value,
                is_saturated=False,
                conversion_valid=sensor_value is not None,
                resolution_bits=16,
            )

        cfg = self.channels[channel_name]

        if sensor_value is None:
            return ADCConversionResult(
                channel_name=channel_name,
                simulated_physical_value=0.0,
                sensor_analog_voltage=None,
                adc_digital_counts=None,
                ecu_observed_value=None,
                is_saturated=False,
                conversion_valid=False,
                resolution_bits=cfg.resolution_bits,
            )

        eng_val = float(sensor_value)
        eng_range = max(1e-6, cfg.engineering_max - cfg.engineering_min)
        norm_ratio = (eng_val - cfg.engineering_min) / eng_range

        # Compute analog voltage
        v_span = cfg.input_v_max - cfg.input_v_min
        v_in = cfg.input_v_min + norm_ratio * v_span

        is_saturated = False
        if v_in < cfg.input_v_min:
            v_in = cfg.input_v_min
            is_saturated = True
        elif v_in > cfg.input_v_max:
            v_in = cfg.input_v_max
            is_saturated = True

        # Compute ADC Digital Counts
        max_counts = (1 << cfg.resolution_bits) - 1
        adc_norm = max(0.0, min(1.0, (v_in - cfg.input_v_min) / max(1e-6, v_span)))
        counts = int(round(adc_norm * max_counts))

        # Reconstruct ECU Engineering Value from Digital Counts
        reconstructed_norm = float(counts) / float(max_counts)
        ecu_val = cfg.engineering_min + reconstructed_norm * eng_range

        return ADCConversionResult(
            channel_name=channel_name,
            simulated_physical_value=eng_val,
            sensor_analog_voltage=round(v_in, 4),
            adc_digital_counts=counts,
            ecu_observed_value=round(ecu_val, 4),
            is_saturated=is_saturated,
            conversion_valid=True,
            resolution_bits=cfg.resolution_bits,
        )

    def convert_sensor_readings(self, sensor_readings: Dict[str, Any]) -> Dict[str, ADCConversionResult]:
        """Converts an entire dictionary of virtual sensor outputs into ADC conversion results."""
        results = {}
        for name, val in sensor_readings.items():
            results[name] = self.convert_channel(name, val)
        return results

    def get_ecu_ingested_telemetry(self, sensor_readings: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts the final reconstructed telemetry dictionary observed by the Virtual ECU."""
        results = self.convert_sensor_readings(sensor_readings)
        ecu_telemetry = {}
        for name, res in results.items():
            if res.ecu_observed_value is not None:
                ecu_telemetry[name] = res.ecu_observed_value
        return ecu_telemetry
