"""Virtual Power Subsystem and 28V DC Electrical Bus Model.

Simulates alternator generation, voltage regulation, battery backup, dynamic load sags,
transient brownouts, and low-voltage threshold alerts.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PowerBusState:
    """State vector of the virtual 28V DC power distribution bus."""
    bus_voltage_v: float
    total_current_a: float
    battery_charge_pct: float
    alternator_status: str  # "NOMINAL", "DEGRADED", "FAILED"
    regulator_status: str   # "REGULATING", "UNREGULATED", "OVERVOLTAGE"
    is_brownout: bool
    is_low_voltage_warning: bool
    timestamp_s: float


class VirtualPowerSubsystem:
    """
    Simulates the aircraft 28V DC electrical distribution system supplying
    the Virtual ECU, FADEC, Virtual Sensors, and Flight Computer.
    """

    NOMINAL_ALTERNATOR_V: float = 28.4
    BATTERY_NOMINAL_V: float = 24.8
    WARNING_VOLTAGE_THRESHOLD: float = 22.0
    BROWNOUT_VOLTAGE_THRESHOLD: float = 19.5
    INTERNAL_RESISTANCE_OHMS: float = 0.045

    def __init__(self, battery_capacity_ah: float = 20.0):
        self.battery_capacity_ah = battery_capacity_ah
        self.battery_energy_ah = battery_capacity_ah
        self.alternator_health: float = 1.0  # 1.0 = nominal, 0.0 = total alternator failure
        self.transient_voltage_offset: float = 0.0
        self.transient_duration_s: float = 0.0
        self.sim_time_s: float = 0.0

    def inject_transient_sag(self, voltage_drop_v: float = 4.5, duration_s: float = 2.0) -> None:
        """Inject a temporary transient voltage sag (e.g. actuator inrush / short)."""
        self.transient_voltage_offset = -abs(voltage_drop_v)
        self.transient_duration_s = duration_s

    def inject_alternator_failure(self, severity: float = 1.0) -> None:
        """Degrade or completely fail the engine-driven alternator."""
        self.alternator_health = max(0.0, min(1.0, 1.0 - severity))

    def reset(self) -> None:
        self.battery_energy_ah = self.battery_capacity_ah
        self.alternator_health = 1.0
        self.transient_voltage_offset = 0.0
        self.transient_duration_s = 0.0
        self.sim_time_s = 0.0

    def step(self, current_draw_a: float = 18.5, time_step_s: float = 0.1) -> PowerBusState:
        """Advances power model by time_step_s and calculates effective DC bus voltage."""
        self.sim_time_s += time_step_s

        # Decay active transient
        if self.transient_duration_s > 0.0:
            self.transient_duration_s = max(0.0, self.transient_duration_s - time_step_s)
            if self.transient_duration_s == 0.0:
                self.transient_voltage_offset = 0.0

        # Calculate Alternator Source Voltage
        if self.alternator_health > 0.8:
            alt_v = self.NOMINAL_ALTERNATOR_V
            alt_status = "NOMINAL"
        elif self.alternator_health > 0.2:
            alt_v = self.BATTERY_NOMINAL_V + (self.NOMINAL_ALTERNATOR_V - self.BATTERY_NOMINAL_V) * self.alternator_health
            alt_status = "DEGRADED"
        else:
            alt_v = 0.0
            alt_status = "FAILED"

        # Battery discharge if alternator cannot support load
        if alt_v < self.BATTERY_NOMINAL_V:
            effective_source_v = self.BATTERY_NOMINAL_V * (0.85 + 0.15 * (self.battery_energy_ah / self.battery_capacity_ah))
            discharge_ah = (current_draw_a * time_step_s) / 3600.0
            self.battery_energy_ah = max(0.0, self.battery_energy_ah - discharge_ah)
        else:
            effective_source_v = alt_v
            # Charge battery back up slowly if needed
            if self.battery_energy_ah < self.battery_capacity_ah:
                charge_ah = (2.0 * time_step_s) / 3600.0
                self.battery_energy_ah = min(self.battery_capacity_ah, self.battery_energy_ah + charge_ah)

        # Internal resistance load sag
        load_sag_v = current_draw_a * self.INTERNAL_RESISTANCE_OHMS
        bus_v = effective_source_v - load_sag_v + self.transient_voltage_offset

        bus_v = max(0.0, round(bus_v, 2))
        is_warning = bus_v < self.WARNING_VOLTAGE_THRESHOLD
        is_brownout = bus_v < self.BROWNOUT_VOLTAGE_THRESHOLD

        reg_status = "REGULATING" if not is_warning else ("LOW_VOLTAGE_SAG" if not is_brownout else "CRITICAL_BROWNOUT")
        batt_pct = round((self.battery_energy_ah / self.battery_capacity_ah) * 100.0, 1)

        return PowerBusState(
            bus_voltage_v=bus_v,
            total_current_a=round(current_draw_a, 1),
            battery_charge_pct=batt_pct,
            alternator_status=alt_status,
            regulator_status=reg_status,
            is_brownout=is_brownout,
            is_low_voltage_warning=is_warning,
            timestamp_s=round(self.sim_time_s, 3),
        )

    def step_power(
        self,
        engine_rpm: float = 3000.0,
        load_current_a: float = 18.5,
        time_step_s: float = 0.1,
    ) -> PowerBusState:
        """Convenience wrapper accepting engine RPM and load current."""
        return self.step(current_draw_a=load_current_a, time_step_s=time_step_s)
