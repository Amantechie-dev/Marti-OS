from typing import List, Optional
from pydantic import BaseModel, Field

class BillItem(BaseModel):
    description: str
    amount_inr: float

class InvoiceResponse(BaseModel):
    encounter_id: str
    items: List[BillItem]
    total_amount_inr: float
    payment_link: str
    is_paid: bool

class DispenseTokenResponse(BaseModel):
    encounter_id: str
    cabinet_slot: int
    medications: List[dict]
    pickup_code: str
    expires_in_minutes: int
    is_dispensed: bool