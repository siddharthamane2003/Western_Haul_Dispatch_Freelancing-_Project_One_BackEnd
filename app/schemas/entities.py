from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID


# ── Customer ──
class CustomerBase(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: str = Field(..., min_length=5, max_length=20)
    alternate_phone: Optional[str] = None
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_pincode: Optional[str] = None
    credit_limit: float = 0.0
    notes: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None
    billing_address: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_pincode: Optional[str] = None
    credit_limit: Optional[float] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class CustomerResponse(CustomerBase):
    id: UUID
    customer_code: str
    outstanding_amount: float
    is_active: bool
    company_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Driver ──
class DriverBase(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=5, max_length=20)
    alternate_phone: Optional[str] = None
    email: Optional[EmailStr] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    license_number: str = Field(..., min_length=3)
    license_expiry: Optional[date] = None
    license_class: Optional[str] = None
    aadhar_number: Optional[str] = None
    pan_number: Optional[str] = None
    experience_years: int = 0
    notes: Optional[str] = None


class DriverCreate(DriverBase):
    pass


class DriverUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    alternate_phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    license_expiry: Optional[date] = None
    experience_years: Optional[int] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class DriverResponse(DriverBase):
    id: UUID
    driver_code: str
    status: str
    avatar_url: Optional[str] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    total_trips: int
    total_km: float
    rating: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DriverLocationUpdate(BaseModel):
    latitude: float
    longitude: float
    speed_kmh: Optional[float] = None


# ── Vehicle ──
class VehicleBase(BaseModel):
    registration_number: str = Field(..., min_length=3, max_length=50)
    vehicle_type: str = Field(..., min_length=1)
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    color: Optional[str] = None
    capacity_tons: float = Field(..., gt=0)
    capacity_cbm: Optional[float] = None
    fuel_type: Optional[str] = None
    engine_number: Optional[str] = None
    chassis_number: Optional[str] = None
    insurance_number: Optional[str] = None
    insurance_expiry: Optional[date] = None
    fitness_certificate: Optional[str] = None
    fitness_expiry: Optional[date] = None
    permit_number: Optional[str] = None
    permit_expiry: Optional[date] = None
    puc_number: Optional[str] = None
    puc_expiry: Optional[date] = None
    gps_device_id: Optional[str] = None
    notes: Optional[str] = None


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    vehicle_type: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    capacity_tons: Optional[float] = None
    insurance_number: Optional[str] = None
    insurance_expiry: Optional[date] = None
    fitness_expiry: Optional[date] = None
    permit_expiry: Optional[date] = None
    puc_expiry: Optional[date] = None
    odometer_km: Optional[float] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class VehicleResponse(VehicleBase):
    id: UUID
    status: str
    odometer_km: float
    photo_url: Optional[str] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VehicleAssignDriver(BaseModel):
    driver_id: UUID
    is_primary: bool = True
