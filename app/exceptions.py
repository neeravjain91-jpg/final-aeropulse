# Centralized AeroPulse Exception Hierarchy

class AeroPulseError(Exception):
    """Base exception for all AeroPulse-X runtime failures."""
    def __init__(self, message: str, error_code: str = "GENERIC_ERROR", context: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}

    def as_dict(self) -> dict:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
        }

class TelemetryCorruptedError(AeroPulseError):
    def __init__(self, message: str, context: dict = None):
        super().__init__(message, error_code="TELEMETRY_CORRUPTED", context=context)

class CANBusError(AeroPulseError):
    def __init__(self, message: str, error_code: str = "CAN_BUS_ERROR", context: dict = None):
        super().__init__(message, error_code=error_code, context=context)

class SecurityViolationError(AeroPulseError):
    def __init__(self, message: str, error_code: str = "SECURITY_VIOLATION", context: dict = None):
        super().__init__(message, error_code=error_code, context=context)

class ModelInferenceError(AeroPulseError):
    def __init__(self, message: str, context: dict = None):
        super().__init__(message, error_code="MODEL_INFERENCE_ERROR", context=context)

class MissionError(AeroPulseError):
    def __init__(self, message: str, context: dict = None):
        super().__init__(message, error_code="MISSION_ERROR", context=context)
