from app.schemas.intake import VitalsInput
from app.services.safety import evaluate_safety

def test_normal_patient_passes():
    vitals = VitalsInput(hr=72, sbp=120, dbp=80, spo2=98, temp_c=36.8)
    res = evaluate_safety(vitals, ["headache", "mild cough"])
    assert res.is_safe is True
    assert len(res.flags) == 0

def test_hypoxia_boundary():
    # 92 is acceptable boundary
    vitals_ok = VitalsInput(hr=75, sbp=115, dbp=75, spo2=92, temp_c=37.0)
    assert evaluate_safety(vitals_ok, ["fever"]).is_safe is True

    # 91 must trigger red flag
    vitals_bad = VitalsInput(hr=75, sbp=115, dbp=75, spo2=91, temp_c=37.0)
    res = evaluate_safety(vitals_bad, ["fever"])
    assert res.is_safe is False
    assert any("hypoxia" in f for f in res.flags)

def test_critical_symptom_triggers_escalation():
    vitals = VitalsInput(hr=80, sbp=120, dbp=80, spo2=99, temp_c=36.6)
    res = evaluate_safety(vitals, ["chest pain", "sweating"])
    assert res.is_safe is False
    assert any("critical symptoms" in f for f in res.flags)