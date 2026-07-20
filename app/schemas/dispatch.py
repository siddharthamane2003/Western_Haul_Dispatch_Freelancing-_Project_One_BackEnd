from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID
from app.models import OrderStatus, DispatchStatus, Priority


# ── Order Location ──
class OrderLocationCreate(BaseModel):
    location_type: str = Field(..., pattern="^(pickup|delivery)$")
    sequence: int = Field(1, ge=1)
    name: str
    address: str
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None


class OrderLocationResponse(OrderLocationCreate):
    id: UUID
    completed_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


# ── Freight Order ──
class FreightOrderCreate(BaseModel):
    customer_id: UUID
    priority: Priority = Priority.NORMAL
    material_type: str = Field(..., min_length=1)
    material_description: Optional[str] = None
    weight_tons: float = Field(..., gt=0)
    volume_cbm: Optional[float] = None
    num_packages: Optional[int] = None
    fragile: bool = False
    hazardous: bool = False
    pickup_date: date
    pickup_time: Optional[str] = None
    delivery_date: Optional[date] = None
    freight_amount: float = 0.0
    additional_charges: float = 0.0
    discount: float = 0.0
    payment_mode: Optional[str] = None
    lr_number: Optional[str] = None
    eway_bill_number: Optional[str] = None
    special_instructions: Optional[str] = None
    internal_notes: Optional[str] = None
    status: Optional[OrderStatus] = OrderStatus.PENDING
    locations: List[OrderLocationCreate] = []


class FreightOrderUpdate(BaseModel):
    priority: Optional[Priority] = None
    material_type: Optional[str] = None
    material_description: Optional[str] = None
    weight_tons: Optional[float] = None
    volume_cbm: Optional[float] = None
    num_packages: Optional[int] = None
    fragile: Optional[bool] = None
    hazardous: Optional[bool] = None
    pickup_date: Optional[date] = None
    pickup_time: Optional[str] = None
    delivery_date: Optional[date] = None
    freight_amount: Optional[float] = None
    additional_charges: Optional[float] = None
    discount: Optional[float] = None
    payment_mode: Optional[str] = None
    payment_status: Optional[str] = None
    lr_number: Optional[str] = None
    eway_bill_number: Optional[str] = None
    special_instructions: Optional[str] = None
    internal_notes: Optional[str] = None
    status: Optional[OrderStatus] = None
    cancellation_reason: Optional[str] = None


class FreightOrderResponse(BaseModel):
    id: UUID
    order_number: str
    customer_id: UUID
    status: OrderStatus
    priority: Priority
    material_type: str
    material_description: Optional[str] = None
    weight_tons: float
    volume_cbm: Optional[float] = None
    num_packages: Optional[int] = None
    fragile: bool
    hazardous: bool
    pickup_date: date
    pickup_time: Optional[str] = None
    delivery_date: Optional[date] = None
    actual_pickup_time: Optional[datetime] = None
    actual_delivery_time: Optional[datetime] = None
    freight_amount: float
    additional_charges: float
    discount: float
    tax_amount: float
    total_amount: float
    payment_status: str
    payment_mode: Optional[str] = None
    invoice_number: Optional[str] = None
    lr_number: Optional[str] = None
    eway_bill_number: Optional[str] = None
    qr_code_url: Optional[str] = None
    special_instructions: Optional[str] = None
    internal_notes: Optional[str] = None
    cancellation_reason: Optional[str] = None
    locations: List[OrderLocationResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Dispatch ──
class DispatchCreate(BaseModel):
    order_id: UUID
    driver_id: UUID
    vehicle_id: UUID


class DispatchUpdate(BaseModel):
    status: Optional[DispatchStatus] = None
    driver_notes: Optional[str] = None
    cancellation_reason: Optional[str] = None
    reschedule_reason: Optional[str] = None
    actual_distance_km: Optional[float] = None


class DispatchResponse(BaseModel):
    id: UUID
    dispatch_number: str
    order_id: UUID
    driver_id: UUID
    vehicle_id: UUID
    assigned_by: UUID
    status: DispatchStatus
    dispatched_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    estimated_distance_km: Optional[float] = None
    actual_distance_km: Optional[float] = None
    estimated_duration_mins: Optional[int] = None
    estimated_arrival: Optional[datetime] = None
    driver_notes: Optional[str] = None
    pod_received: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Tracking ──
class TrackingUpdateCreate(BaseModel):
    latitude: float
    longitude: float
    speed_kmh: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class TrackingUpdateResponse(TrackingUpdateCreate):
    id: UUID
    dispatch_id: UUID
    recorded_at: datetime
    model_config = {"from_attributes": True}


# ── Common ──
class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    size: int
    pages: int


class StatusUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None


class SearchRequest(BaseModel):
    query: Optional[str] = None
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)
    sort_by: Optional[str] = None
    sort_order: str = Field("desc", pattern="^(asc|desc)$")
