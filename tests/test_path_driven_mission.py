"""Automated Unit & Integration Tests for Path-Driven UAV Mission Simulation."""
import pytest
from app.environment import _DEFAULT_ENV_SERVICE
from app.navigation import (
    DEFAULT_MISSION_WAYPOINTS,
    HIGH_ALT_SURVEILLANCE_WAYPOINTS,
    COASTAL_MARITIME_WAYPOINTS,
    PRESET_MISSIONS,
    MissionWaypoint,
    SimulatedGPSSource,
    UAVPosition,
)
from app.uav_mission import UAVMissionSimulator
from app.engine_model import ReducedOrderPistonEngine
from app.inference import AeroTwinAI
from app.risk import mission_risk
from app.replay import run_replay


@pytest.fixture(autouse=True)
def disable_live_weather_for_unit_tests():
    orig_live = _DEFAULT_ENV_SERVICE.enable_live
    _DEFAULT_ENV_SERVICE.enable_live = False
    yield
    _DEFAULT_ENV_SERVICE.enable_live = orig_live


def test_preset_missions_structure_and_validity():
    assert "border_patrol_alpha" in PRESET_MISSIONS
    assert "high_alt_surveillance" in PRESET_MISSIONS
    assert "coastal_maritime" in PRESET_MISSIONS

    for key, preset in PRESET_MISSIONS.items():
        assert len(preset["waypoints"]) >= 5
        assert len(preset["name"]) > 0
        summary = SimulatedGPSSource(preset["waypoints"]).get_flight_plan_summary()
        assert summary["total_distance_km"] > 50.0
        assert summary["estimated_duration_min"] > 10.0


def test_dynamic_waypoint_manipulation():
    # Construct custom route
    custom_wps = [
        MissionWaypoint("WP0", "Base Alpha", 28.45, 77.02, 1000.0, "BASE", 60.0),
        MissionWaypoint("WP1", "Climb Point", 28.60, 77.20, 10000.0, "CLIMB", 120.0),
        MissionWaypoint("WP2", "Target Recon", 28.85, 77.55, 18000.0, "ISR", 130.0, 15.0),
        MissionWaypoint("WP3", "Base Recovery", 28.45, 77.02, 1000.0, "RECOVERY", 65.0),
    ]
    gps = SimulatedGPSSource(custom_wps)
    assert len(gps.waypoints) == 4
    assert gps.total_distance_km > 50.0

    # Modify altitude of WP2
    custom_wps[2].altitude_ft = 22000.0
    gps_modified = SimulatedGPSSource(custom_wps)
    pos_at_target = gps_modified.get_position(0.66)
    assert pos_at_target.altitude_ft > 16000.0


def test_automatic_isa_atmosphere_temperature_lapse():
    gps = SimulatedGPSSource(ground_temp_c=35.0)
    
    # Sea level / low altitude
    t_sea, rho_sea, p_sea = gps.get_atmospheric_state(1000.0)
    assert 30.0 <= t_sea <= 35.0
    assert 0.90 <= rho_sea <= 1.05
    assert 28.0 <= p_sea <= 31.0

    # High altitude 20,000 ft: Temp should drop significantly (~ -4°C)
    t_high, rho_high, p_high = gps.get_atmospheric_state(20000.0)
    assert t_high < t_sea - 30.0  # Approx 35 - 39.6 = -4.6 C
    assert rho_high < rho_sea
    assert p_high < p_sea


def test_automatic_altitude_smooth_climb_and_descent():
    gps = SimulatedGPSSource(DEFAULT_MISSION_WAYPOINTS)
    steps = 40
    altitudes = []

    for i in range(steps):
        pos = gps.get_position(i / (steps - 1))
        altitudes.append(pos.altitude_ft)

    # Initial altitude is at airbase
    assert altitudes[0] <= 1500.0
    # Peak altitude is reached in the middle legs
    assert max(altitudes) >= 18000.0
    # Landing altitude returns to airbase
    assert altitudes[-1] <= 1500.0

    # Verify smooth gradient: no single step jump greater than 2,500 ft
    for j in range(len(altitudes) - 1):
        step_diff = abs(altitudes[j + 1] - altitudes[j])
        assert step_diff < 3000.0


def test_automatic_throttle_and_load_scheduling():
    gps = SimulatedGPSSource(DEFAULT_MISSION_WAYPOINTS)
    
    # Takeoff / Climb phase
    pos_climb = gps.get_position(0.08)
    assert pos_climb.auto_throttle >= 0.70
    assert pos_climb.operating_state in {"HIGH", "CRUISE"}

    # Cruise / Loiter phase
    pos_cruise = gps.get_position(0.50)
    assert 0.45 <= pos_cruise.auto_throttle <= 0.75

    # Recovery / Landing phase
    pos_landing = gps.get_position(0.99)
    assert pos_landing.auto_throttle <= 0.40


def test_uav_mission_simulator_with_path_driven_waypoints():
    mission = UAVMissionSimulator(waypoints=DEFAULT_MISSION_WAYPOINTS, ambient_c=32.0)
    assert mission.duration_min > 90.0
    
    point_start = mission.point(0, 50)
    point_mid = mission.point(25, 50)
    point_end = mission.point(49, 50)

    assert point_start.mission_phase in {"GROUND", "TAKEOFF"}
    assert point_mid.altitude_ft > 10000.0
    assert point_end.mission_phase in {"LANDING", "RETURN", "DESCENT"}

    # Connect to ReducedOrderPistonEngine
    engine = ReducedOrderPistonEngine()
    engine_data = engine.simulate(
        throttle=point_mid.throttle,
        rpm=3200,
        altitude_ft=point_mid.altitude_ft,
        ambient_c=point_mid.ambient_c,
        load=point_mid.load,
    )
    assert engine_data["CHT"] > 100.0
    assert engine_data["EGT1"] > 800.0
    assert engine_data["Fuel_Flow"] > 10.0


def test_path_driven_replay_with_custom_waypoints():
    ai = AeroTwinAI()
    base = {
        "Engine_RPM": 3000.0, "EGT1": 1000.0, "EGT2": 1005.0, "EGT3": 995.0,
        "CHT": 180.0, "Fuel_Flow": 20.0, "Oil_Temp": 90.0, "Oil_Pressure": 60.0,
        "Battery_Voltage": 27.0, "Battery_Current": 2.0, "Alternator_Temp": 80.0,
        "EFI_Fuel_Temp": 30.0, "EFI_Water_Temp": 85.0, "MAP_Injector": 20.0,
        "Operating_State": "CRUISE",
    }
    scenario = {
        "fault": "overheating",
        "severity": 0.5,
        "simulation_mode": "automatic",
        "waypoints": [wp.to_dict() for wp in HIGH_ALT_SURVEILLANCE_WAYPOINTS],
    }
    result = run_replay(ai, base, scenario, steps=20, step_minutes=5.0, fault_onset_ratio=0.35)
    
    assert "flight_plan_summary" in result
    assert "timeline" in result
    assert len(result["timeline"]) == 20

    # Ensure uav position is synchronized with automatic altitude and speed
    for pt in result["timeline"]:
        uav = pt["uav"]
        assert "altitude_ft" in uav
        assert "auto_throttle" in uav
        assert "ambient_c" in uav
        assert "ground_speed_kt" in uav
        assert "distance_remaining_km" in uav
