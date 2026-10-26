from typing import List
from app.schemas.intake import VitalsInput, SafetyEvaluation

CRITICAL_SYMPTOMS = {
    "chest pain",
    "difficulty breathing",
    "shortness of breath",
    "stroke signs",
    "severe bleeding",
    "loss of consciousness",
    "seizure",
    "anaphylaxis",
}

def evaluate_safety(vitals: VitalsInput, symptoms: List[str]) -> SafetyEvaluation:
    flags: List[str] = []

    # vital sign thresholds
    if vitals.spo2 < 92:
        flags.append("hypoxia: spo2 below 92%")

    if vitals.hr > 130 or vitals.hr < 40:
        flags.append("hemodynamic instability: abnormal heart rate")

    if vitals.sbp < 90:
        flags.append("hypotension: systolic bp below 90 mmhg")

    if vitals.temp_c >= 40.0:
        flags.append("hyperpyrexia: temperature at or above 40 c")

    # symptom keyword evaluation
    normalized_symptoms = {s.strip().lower() for s in symptoms}
    critical_matches = normalized_symptoms & CRITICAL_SYMPTOMS
    if critical_matches:
        flags.append(f"critical symptoms: {', '.join(sorted(critical_matches))}")

    return SafetyEvaluation(
        is_safe=len(flags) == 0,
        flags=flags
    )