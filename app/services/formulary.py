from typing import List, Dict, Any

APPROVED_FORMULARY: Dict[str, Dict[str, float]] = {
    "paracetamol": {"max_single_dose_mg": 1000.0, "min_interval_hrs": 4.0},
    "cetirizine": {"max_single_dose_mg": 10.0, "min_interval_hrs": 24.0},
    "ibuprofen": {"max_single_dose_mg": 400.0, "min_interval_hrs": 6.0},
    "saline nasal spray": {"max_single_dose_mg": 0.0, "min_interval_hrs": 0.0},
}

def verify_prescription_safety(medications: List[Dict[str, Any]], patient_allergies: List[str]) -> List[str]:
    violations: List[str] = []
    normalized_allergies = [a.strip().lower() for a in patient_allergies]

    for med in medications:
        name = med.get("name", "").strip().lower()
        dose = float(med.get("dose_mg", 0))

        if name not in APPROVED_FORMULARY:
            violations.append(f"unapproved formulary medication: {name}")
            continue

        rule = APPROVED_FORMULARY[name]
        if rule["max_single_dose_mg"] > 0 and dose > rule["max_single_dose_mg"]:
            violations.append(
                f"dose {dose}mg exceeds maximum single dose limit {rule['max_single_dose_mg']}mg for {name}"
            )

        for allergy in normalized_allergies:
            if allergy and allergy in name:
                violations.append(f"allergy conflict detected: patient allergic to {allergy}")

    return violations