from __future__ import annotations

from typing import Any, Dict, Optional
from ..engine_config import EngineConfig
from ..engine_model import EngineInputs, EngineState, ReducedOrderPistonEngine
from ..interfaces import IEngineModel


class Rotax914TurboPistonEngine(IEngineModel):
    """
    Plugin implementation for the Rotax 914 F/UL 115 HP Turbocharged 4-cylinder aero engine.
    Demonstrates modular plug-and-play substitution through the IEngineModel protocol.
    """

    def __init__(self):
        self.config = EngineConfig(
            name="Rotax-914-Turbo-115HP",
            displacement_l=1.211,
            bore_mm=79.5,
            stroke_mm=61.0,
            num_cylinders=4,
            compression_ratio=9.0,
            base_power_kw=84.5,
            nominal_rpm=5500.0,
            max_rpm=5800.0,
            idle_rpm=1400.0,
            turbo_critical_alt_ft=16000.0,
        )
        self.core = ReducedOrderPistonEngine(config=self.config)

    def predict(self, inputs: Any) -> Dict[str, float]:
        if not isinstance(inputs, EngineInputs):
            inputs = EngineInputs(**inputs) if isinstance(inputs, dict) else EngineInputs()
        return self.core.predict(inputs)

    def simulate(self, **kwargs) -> Dict[str, float]:
        return self.core.simulate(**kwargs)
