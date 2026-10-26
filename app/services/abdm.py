import re
from typing import Dict, Any, Optional

ABHA_NUMBER_REGEX = re.compile(r"^\d{2}-\d{4}-\d{4}-\d{4}$")
ABHA_ADDRESS_REGEX = re.compile(r"^[a-zA-Z0-9._]{3,32}@[a-zA-Z0-9]{3,16}$")

# mock central abdm registry
MOCK_ABDM_REGISTRY: Dict[str, Dict[str, Any]] = {
    "91-4567-8901-2345": {
        "abha_number": "91-4567-8901-2345",
        "abha_address": "patient777@abdm",
        "full_name": "Aman Verma",
        "gender": "M",
        "dob": "2001-08-15",
        "state": "Bihar",
        "status": "ACTIVE",
    },
    "12-3456-7890-1234": {
        "abha_number": "12-3456-7890-1234",
        "abha_address": "rohit@abdm",
        "full_name": "Rohit Kumar",
        "gender": "M",
        "dob": "1998-04-20",
        "state": "Punjab",
        "status": "ACTIVE",
    },
}

def validate_abha_number_format(abha_number: str) -> bool:
    clean = abha_number.strip()
    return bool(ABHA_NUMBER_REGEX.match(clean))

def validate_abha_address_format(abha_address: str) -> bool:
    clean = abha_address.strip().lower()
    return bool(ABHA_ADDRESS_REGEX.match(clean))

def verify_abha_profile(
    abha_number: Optional[str] = None,
    abha_address: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if abha_number:
        clean_num = abha_number.strip()
        if clean_num in MOCK_ABDM_REGISTRY:
            return MOCK_ABDM_REGISTRY[clean_num]

    if abha_address:
        clean_addr = abha_address.strip().lower()
        for profile in MOCK_ABDM_REGISTRY.values():
            if profile["abha_address"].lower() == clean_addr:
                return profile

    # fallback simulation for valid formatted ids during testing
    if abha_number and validate_abha_number_format(abha_number):
        return {
            "abha_number": abha_number,
            "abha_address": f"user{abha_number.replace('-', '')[-4:]}@abdm",
            "full_name": "Verified ABDM Patient",
            "gender": "U",
            "dob": "2000-01-01",
            "state": "India",
            "status": "ACTIVE",
        }

    return None