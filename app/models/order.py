from pydantic import BaseModel, Field
from typing import Literal


class ShippingAddress(BaseModel):
    full_name: str
    phone: str
    address: str
    city: str
    state: str
    pincode: str


class PaymentDetails(BaseModel):
    payment_method: Literal["online", "cod"]


class OrderCreateInput(BaseModel):
    quantity: int = Field(gt=0)
    shipping_address: ShippingAddress
    payment: PaymentDetails
    