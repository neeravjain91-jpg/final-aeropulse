import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.sensor_health import assess_sensor_health
from app.digital_twin import ReferenceTwin

client = TestClient(app)

REQUIRED_TOP_KEYS = [
    'health_state',
    'health_index',
    'fault_candidates',
    'sensor_health',
    'twin',
    'mission_risk',
    'telemetry',
    'maintenance_advisory',
]

def test_analyze_healthy_baseline_contract():
    payload = {
        'operating_state': 'CRUISE',
        'altitude_ft': 3000,
        'ambient_c': 25,
        'duration_h': 1.0,
        'rapid_throttle': False,
        'fault': 'none',
        'severity': 0.6,
    }
    response = client.post('/api/analyze', json=payload)
    assert response.status_code == 200, f'Analyze failed: {response.text}'
    data = response.json()

    for key in REQUIRED_TOP_KEYS:
        assert key in data, f'Missing required key: {key}'

    assert isinstance(data['fault_candidates'], list)
    for cand in data['fault_candidates']:
        assert 'name' in cand
        assert 'severity' in cand
        assert isinstance(cand.get('evidence'), list)

    sh = data['sensor_health']
    assert isinstance(sh, dict)
    assert 'overall_trust_score' in sh
    assert 'overall_status' in sh
    assert sh['overall_status'] in {'TRUSTED', 'CHECK', 'SUSPECT'}
    assert isinstance(sh.get('sensors'), list)
    assert isinstance(sh.get('channels'), list)
    assert len(sh['sensors']) > 0
    assert len(sh['channels']) == len(sh['sensors'])

    for sensor in sh['sensors']:
        assert 'name' in sensor
        assert 'trust_score' in sensor
        assert 'status' in sensor
        assert 'reason' in sensor

    twin = data['twin']
    assert isinstance(twin, dict)
    assert isinstance(twin.get('dominant_deviations'), list)
    assert isinstance(twin.get('expected'), dict)
    assert isinstance(twin.get('z_scores'), dict)

    mr = data['mission_risk']
    assert isinstance(mr, dict)
    assert 'level' in mr
    assert 'score' in mr
    assert isinstance(mr.get('components'), dict)

@pytest.mark.parametrize('fault_name', [
    'none',
    'injector',
    'lubrication',
    'overheating',
    'misfire',
    'electrical',
    'sensor_drift',
    'sensor_bias',
    'sensor_spike',
])
def test_analyze_all_fault_modes_contracts(fault_name):
    payload = {
        'operating_state': 'CRUISE',
        'altitude_ft': 4500,
        'ambient_c': 30,
        'duration_h': 2.0,
        'rapid_throttle': False,
        'fault': fault_name,
        'severity': 0.7,
    }
    response = client.post('/api/analyze', json=payload)
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data['fault_candidates'], list)
    assert isinstance(data['sensor_health']['sensors'], list)
    assert isinstance(data['sensor_health']['channels'], list)
    assert isinstance(data['twin']['dominant_deviations'], list)
    assert isinstance(data['telemetry'], dict)

def test_sensor_health_assess_direct_contract():
    twin_engine = ReferenceTwin()
    base = twin_engine.expected('CRUISE')
    twin_comp = twin_engine.compare(base)

    sh = assess_sensor_health(base, twin_comp)
    assert 'overall_trust_score' in sh
    assert 'overall_status' in sh
    assert sh['overall_status'] in {'TRUSTED', 'CHECK', 'SUSPECT'}
    assert 'sensors' in sh
    assert 'channels' in sh
    assert 'suspect_sensors' in sh
    assert 'suspect_channels' in sh
    assert isinstance(sh['sensors'], list)
    assert isinstance(sh['channels'], list)
    assert isinstance(sh['suspect_sensors'], list)
    assert isinstance(sh['suspect_channels'], list)
