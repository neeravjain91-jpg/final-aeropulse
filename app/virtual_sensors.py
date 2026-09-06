"""Modular Virtual Sensor Subsystem for AeroPulse-X SIL Environment.

Simulates physical transducers with configurable noise, bias, drift, scale error,
quantization, saturation, stuck-at, dropout, and timestamp jitter under deterministic seeds.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SensorFaultConfig:
    """Configurable degradation and fault parameters for a single virtual sensor."""
    noise_std: float = 0.0
    bias: float = 0.0
    drift_rate_per_sec: float = 0.0
    scale_factor_error: float = 0.0  # e.g., 0.05 for +5% sensitivity error
    quantization_step: Optional[float] = None  # e.g., 0.1 for 0.1 unit resolution
    min_saturation: Optional[float] = None
    max_saturation: Optional[float] = None
    stuck_at_value: Optional[float] = None
    is_dropout: bool = False
    dropout_value: Optional[float] = None  # None indicates missing telemetry
    intermittent_dropout_prob: float = 0.0
    timestamp_jitter_ms_std: float = 0.0
    rng_seed: Optional[int] = None


@dataclass
class SensorReading:
    """Represents the output of a virtual sensor conversion cycle."""
    channel_name: str
    physical_unit: str
    raw_physical_value: float
    sensor_output_value: Optional[float]
    timestamp_ms: float
    is_valid: bool
    fault_flags: List[str] = field(default_factory=list)


class VirtualSensor:
    """Simulates a single physical transducer converting true physical quantity into a sensor signal."""

    def __init__(
        self,
        channel_name: str,
        physical_unit: str,
        nominal_min: float,
        nominal_max: float,
        fault_config: Optional[SensorFaultConfig] = None,
    ):
        self.channel_name = channel_name
        self.physical_unit = physical_unit
        self.nominal_min = nominal_min
        self.nominal_max = nominal_max
        self.fault_config = fault_config or SensorFaultConfig()
        self._rng = random.Random(self.fault_config.rng_seed if self.fault_config.rng_seed is not None else 42)
        self._start_sim_time_s: Optional[float] = None

    def configure_fault(self, config: SensorFaultConfig) -> None:
        self.fault_config = config
        if config.rng_seed is not None:
            self._rng = random.Random(config.rng_seed)

    def reset(self) -> None:
        self.fault_config = SensorFaultConfig()
        self._rng = random.Random(42)
        self._start_sim_time_s = None

    def read(self, physical_value: float, sim_time_s: float = 0.0) -> SensorReading:
        """
        Executes sensor transfer function:
        physical_value -> scale/bias -> drift -> noise -> saturation -> quantization -> stuck/dropout
        """
        if self._start_sim_time_s is None:
            self._start_sim_time_s = sim_time_s

        cfg = self.fault_config
        flags: List[str] = []

        # Base timestamp with optional jitter
        base_ts_ms = sim_time_s * 1000.0
        if cfg.timestamp_jitter_ms_std > 0.0:
            jitter = self._rng.gauss(0.0, cfg.timestamp_jitter_ms_std)
            base_ts_ms += jitter
            flags.append("TIMESTAMP_JITTER")

        # 1. Check Hard Dropout
        if cfg.is_dropout:
            flags.append("HARD_DROPOUT")
            return SensorReading(
                channel_name=self.channel_name,
                physical_unit=self.physical_unit,
                raw_physical_value=physical_value,
                sensor_output_value=cfg.dropout_value,
                timestamp_ms=round(base_ts_ms, 2),
                is_valid=False,
                fault_flags=flags,
            )

        # 2. Check Intermittent Dropout
        if cfg.intermittent_dropout_prob > 0.0 and self._rng.random() < cfg.intermittent_dropout_prob:
            flags.append("INTERMITTENT_DROPOUT")
            return SensorReading(
                channel_name=self.channel_name,
                physical_unit=self.physical_unit,
                raw_physical_value=physical_value,
                sensor_output_value=cfg.dropout_value,
                timestamp_ms=round(base_ts_ms, 2),
                is_valid=False,
                fault_flags=flags,
            )

        # 3. Check Stuck-at Fault
        if cfg.stuck_at_value is not None:
            flags.append("STUCK_AT_VALUE")
            return SensorReading(
                channel_name=self.channel_name,
                physical_unit=self.physical_unit,
                raw_physical_value=physical_value,
                sensor_output_value=float(cfg.stuck_at_value),
                timestamp_ms=round(base_ts_ms, 2),
                is_valid=True,
                fault_flags=flags,
            )

        # 4. Scale error and fixed bias
        val = physical_value * (1.0 + cfg.scale_factor_error) + cfg.bias
        if abs(cfg.bias) > 1e-6 or abs(cfg.scale_factor_error) > 1e-6:
            flags.append("BIAS_OR_SCALE_ERROR")

        # 5. Temporal linear drift
        elapsed_s = max(0.0, sim_time_s - self._start_sim_time_s)
        if abs(cfg.drift_rate_per_sec) > 1e-9:
            drift = cfg.drift_rate_per_sec * elapsed_s
            val += drift
            flags.append("TEMPORAL_DRIFT")

        # 6. Measurement Gaussian noise
        if cfg.noise_std > 0.0:
            noise = self._rng.gauss(0.0, cfg.noise_std)
            val += noise
            flags.append("NOISE_INJECTED")

        # 7. Saturation / Clamping
        if cfg.min_saturation is not None and val < cfg.min_saturation:
            val = cfg.min_saturation
            flags.append("MIN_SATURATION_CLAMP")
        if cfg.max_saturation is not None and val > cfg.max_saturation:
            val = cfg.max_saturation
            flags.append("MAX_SATURATION_CLAMP")

        # 8. Quantization
        if cfg.quantization_step is not None and cfg.quantization_step > 0.0:
            val = round(val / cfg.quantization_step) * cfg.quantization_step
            flags.append("QUANTIZED")

        return SensorReading(
            channel_name=self.channel_name,
            physical_unit=self.physical_unit,
            raw_physical_value=physical_value,
            sensor_output_value=round(val, 4),
            timestamp_ms=round(base_ts_ms, 2),
            is_valid=True,
            fault_flags=flags,
        )


class VirtualSensorArray:
    """Comprehensive virtual sensor array representing all airborne propulsion transducers."""

    DEFAULT_SENSOR_SPECS = {
        "Engine_RPM": ("RPM", 0.0, 6500.0, 0.25),
        "EGT1": ("deg_F", 0.0, 1650.0, 0.1),
        "EGT2": ("deg_F", 0.0, 1650.0, 0.1),
        "EGT3": ("deg_F", 0.0, 1650.0, 0.1),
        "CHT": ("deg_F", 0.0, 500.0, 0.1),
        "Fuel_Flow": ("L/h", 0.0, 60.0, 0.01),
        "Oil_Temp": ("deg_F", -40.0, 350.0, 0.1),
        "Oil_Pressure": ("psi", 0.0, 150.0, 0.1),
        "Battery_Voltage": ("V", 0.0, 36.0, 0.01),
        "Battery_Current": ("A", -50.0, 100.0, 0.1),
        "Alternator_Temp": ("deg_F", -40.0, 300.0, 0.1),
        "EFI_Fuel_Temp": ("deg_F", -40.0, 200.0, 0.1),
        "EFI_Water_Temp": ("deg_F", -40.0, 300.0, 0.1),
        "MAP_Injector": ("inHg", 0.0, 120.0, 0.01),
        "Vibration": ("g", 0.0, 25.0, 0.001),
        "Knock_Intensity": ("pct", 0.0, 1.0, 0.001),
    }

    def __init__(self, master_seed: int = 42):
        self.master_seed = master_seed
        self.sensors: Dict[str, VirtualSensor] = {}
        for idx, (name, (unit, n_min, n_max, q_step)) in enumerate(self.DEFAULT_SENSOR_SPECS.items()):
            cfg = SensorFaultConfig(rng_seed=master_seed + idx, quantization_step=q_step)
            self.sensors[name] = VirtualSensor(name, unit, n_min, n_max, cfg)

    def configure_sensor_fault(self, channel_name: str, fault_config: SensorFaultConfig) -> None:
        if channel_name in self.sensors:
            self.sensors[channel_name].configure_fault(fault_config)

    def reset_all_sensors(self) -> None:
        for idx, (name, sensor) in enumerate(self.sensors.items()):
            sensor.reset()
            sensor.fault_config.rng_seed = self.master_seed + idx
            sensor.fault_config.quantization_step = self.DEFAULT_SENSOR_SPECS[name][3]

    def process_telemetry(self, physical_telemetry: Dict[str, Any], sim_time_s: float = 0.0) -> Dict[str, SensorReading]:
        """Convert a physical telemetry state vector into full sensor readings."""
        readings: Dict[str, SensorReading] = {}
        for name, sensor in self.sensors.items():
            raw_val = float(physical_telemetry.get(name, (sensor.nominal_min + sensor.nominal_max) / 2.0))
            readings[name] = sensor.read(raw_val, sim_time_s=sim_time_s)
        return readings

    def get_observed_telemetry(self, physical_telemetry: Dict[str, Any], sim_time_s: float = 0.0) -> Dict[str, Any]:
        """Returns the dictionary of observed sensor values passed to ADC / ECU."""
        readings = self.process_telemetry(physical_telemetry, sim_time_s=sim_time_s)
        observed = dict(physical_telemetry)
        for name, r in readings.items():
            if r.sensor_output_value is not None:
                observed[name] = r.sensor_output_value
            else:
                observed.pop(name, None)
        return observed
