from __future__ import annotations
import sys
import time

def run_self_test() -> int:
    print("================================================================================")
    print("AEROPULSE-X: COMPREHENSIVE SOFTWARE SYSTEM SELF-TEST")
    print("================================================================================")
    tests_run = 0
    tests_passed = 0

    def check(name: str, fn) -> bool:
        nonlocal tests_run, tests_passed
        tests_run += 1
        t0 = time.perf_counter()
        try:
            fn()
            dt = (time.perf_counter() - t0) * 1000.0
            print(f"  [PASS] {name:48s} ({dt:6.2f} ms)")
            tests_passed += 1
            return True
        except Exception as e:
            dt = (time.perf_counter() - t0) * 1000.0
            print(f"  [FAIL] {name:48s} ({dt:6.2f} ms) -> {e}")
            return False

    # 1. Physics Engine
    def test_physics():
        from app.engine_model import ReducedOrderPistonEngine, EngineInputs
        eng = ReducedOrderPistonEngine()
        p = eng.predict(EngineInputs(rpm=4544.0, throttle=0.60, altitude_ft=3000.0, ambient_c=25.0))
        assert 190.0 <= p["CHT"] <= 245.0
        assert 1200.0 <= p["EGT1"] <= 1450.0
        assert 50.0 <= p["Oil_Pressure"] <= 70.0
    check("1. Physics Digital Twin State Predictor", test_physics)

    # 2. Telemetry Ingestion & Input Sanitization
    def test_telemetry():
        from app.digital_twin import ReferenceTwin
        twin = ReferenceTwin()
        res = twin.compare({"Engine_RPM": None, "CHT": 205.0, "Operating_State": "CRUISE"})
        assert res["residuals"]["CHT"] is not None
    check("2. Telemetry Ingestion & Input Sanitization", test_telemetry)

    # 3. Sensor Health Matrix
    def test_sensors():
        from app.sensor_health import assess_sensor_health
        twin = {"z_scores": {"CHT": 4.5, "EFI_Water_Temp": 0.1, "Oil_Temp": 0.2, "EGT1": 0.1, "EGT2": 0.1, "EGT3": 0.1}}
        sh = assess_sensor_health({"CHT": 280.0, "EGT1": 1280.0, "EGT2": 1280.0, "EGT3": 1280.0, "EFI_Water_Temp": 180.0}, twin)
        assert sh["is_sensor_fault_only"] is True
    check("3. Sensor Health & Fault Isolation Matrix", test_sensors)

    # 4. HGB Diagnostic Inference
    def test_hgb():
        from app.inference import AeroTwinAI
        ai = AeroTwinAI()
        assert ai.health is not None
    check("4. HGB-PRO Health Model Loading & Inference", test_hgb)

    # 5. Lightweight TCN
    def test_tcn():
        import numpy as np
        from app.tcn_model import LightweightTCN
        tcn = LightweightTCN(num_inputs=14, num_classes=3)
        lbl, probs = tcn.predict_window(np.random.randn(30, 14).astype(np.float32))
        assert lbl in ["Normal", "Degraded", "Critical"]
    check("5. Lightweight Dilated Causal TCN", test_tcn)

    # 6. Temporal Conv Autoencoder
    def test_ae():
        import numpy as np
        from app.anomaly_autoencoder import TemporalConvAutoencoder
        ae = TemporalConvAutoencoder()
        res = ae.detect_anomaly(np.zeros((32, 14), dtype=np.float32))
        assert "is_unknown_anomaly" in res
    check("6. Temporal Convolutional Autoencoder", test_ae)

    # 7. Model Fusion Engine
    def test_fusion():
        from app.fusion import FusionEngine
        fe = FusionEngine()
        ev = fe.fuse({"Critical": 0.85, "Normal": 0.15}, None, 0.01, False, {"max_abs_z": 3.5, "residual_rms": 2.8}, {"overall_trust_score": 100.0})
        assert ev.final_diagnosis == "Critical"
    check("7. Multi-Model Fusion & Evidence Generator", test_fusion)

    # 8. RUL Prognostics
    def test_rul():
        from app.rul_service import RULService
        rul = RULService()
        p = rul.predict({"Engine_RPM": 4544.0, "CHT": 202.0})
        assert "rul_hours" in p
    check("8. RUL Degradation & Uncertainty Service", test_rul)

    # 9. CAN 2.0B HAL & CRC8
    def test_can():
        from app.can_bus import AeroPulseCANInterface
        can = AeroPulseCANInterface()
        frames = can.encode_telemetry({"Engine_RPM": 4500.0, "CHT": 200.0, "MAP_Injector": 30.0})
        dec = can.decode_frame(frames[0])
        assert dec["Engine_RPM"] == 4500.0
    check("9. CAN 2.0B Bus HAL & Frame Processing", test_can)

    # 10. Cryptographic Telemetry Authentication
    def test_security():
        from app.secure_telemetry import SecureTelemetryProtocol
        sec = SecureTelemetryProtocol(b"test_key_32_bytes_long_secret!!")
        pkt = sec.sign_telemetry({"Engine_RPM": 4500.0})
        auth = sec.verify_packet(pkt)
        assert auth is not None
    check("10. HMAC-SHA256 Telemetry Packet Security", test_security)

    # 11. UAV Mission Route & Environment
    def test_mission():
        from app.uav_mission import UAVMissionSimulator
        sim = UAVMissionSimulator(duration_min=10.0)
        profile = sim.generate()
        assert len(profile) > 0
    check("11. UAV Navigation & Flight Route Planner", test_mission)

    # 12. Mission Flight Replay Engine
    def test_replay():
        from app.inference import AeroTwinAI
        from app.replay import run_replay
        ai = AeroTwinAI()
        base = ai.twin.expected("CRUISE")
        base["Operating_State"] = "CRUISE"
        res = run_replay(ai, base, {"fault": "overheating", "severity": 0.5}, steps=10)
        assert "timeline" in res
    check("12. Mission Flight Replay Engine", test_replay)

    print("--------------------------------------------------------------------------------")
    print(f"RESULTS: {tests_passed}/{tests_run} TESTS PASSED ({(tests_passed/tests_run)*100:.1f}%)")
    print("================================================================================")
    return 0 if tests_passed == tests_run else 1

if __name__ == "__main__":
    sys.exit(run_self_test())
