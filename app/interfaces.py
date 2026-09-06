from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class IEngineModel(Protocol):
    def predict(self, inputs: Any) -> Dict[str, float]:
        ...
    def simulate(self, **kwargs) -> Dict[str, float]:
        ...


@runtime_checkable
class ITelemetryProvider(Protocol):
    def get_telemetry(self) -> Dict[str, Any]:
        ...


@runtime_checkable
class IMissionModel(Protocol):
    def get_position(self, progress_ratio: float, **kwargs) -> Any:
        ...


@runtime_checkable
class IFaultModel(Protocol):
    def apply(self, telemetry: Dict[str, Any], state: Any) -> Dict[str, Any]:
        ...


@runtime_checkable
class IDigitalTwin(Protocol):
    def compare(self, telemetry: Dict[str, Any], context: Optional[dict] = None) -> Dict[str, Any]:
        ...


@runtime_checkable
class IHealthEstimator(Protocol):
    def analyze(self, telemetry: Dict[str, Any], context: Optional[dict] = None) -> Dict[str, Any]:
        ...


@runtime_checkable
class IRULModel(Protocol):
    def predict(self, telemetry: Dict[str, Any], context: Optional[dict] = None) -> Dict[str, Any]:
        ...


@runtime_checkable
class IRiskModel(Protocol):
    def calculate(self, analysis: Dict[str, Any], context: Optional[dict] = None) -> Dict[str, Any]:
        ...


@runtime_checkable
class ITelemetryTransport(Protocol):
    def send_packet(self, data: bytes) -> bool:
        ...
    def receive_packet(self) -> Optional[bytes]:
        ...
