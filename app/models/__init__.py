import uuid
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    String, Boolean, Text, DateTime, Date, Numeric,
    Integer, ForeignKey, Enum as SAEnum, JSON, Float,
    BigInteger, Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
# Use cross-DB compatible types (works on SQLite and PostgreSQL)
from sqlalchemy import types as sa_types
from sqlalchemy.dialects import postgresql

class UUID(sa_types.TypeDecorator):
    """Platform-independent UUID type. Uses PostgreSQL UUID on Postgres, TEXT on others."""
    impl = sa_types.String(36)
    cache_ok = True
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(postgresql.UUID())
        return dialect.type_descriptor(sa_types.String(36))
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)
    def process_result_value(self, value, dialect):
        return value

JSONB = JSON  # SQLite uses JSON, PostgreSQL uses JSON (JSONB handled by dialect on Postgres)
import enum
from app.db.database import Base


# ─────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DISPATCHER = "dispatcher"
    DRIVER = "driver"
    CUSTOMER = "customer"

class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ASSIGNED = "assigned"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"
    RETURNED = "returned"
    # Dispatch workflow statuses
    GOING_FOR_PICKUP  = "going_for_pickup"
    INVOICED          = "invoiced"
    ONSITE_FOR_PICKUP = "onsite_for_pickup"
    PAID              = "paid"

class DispatchStatus(str, enum.Enum):
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"

class DriverStatus(str, enum.Enum):
    AVAILABLE = "available"
    ON_TRIP = "on_trip"
    OFF_DUTY = "off_duty"
    SUSPENDED = "suspended"

class VehicleStatus(str, enum.Enum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"

class DocumentType(str, enum.Enum):
    POD = "pod"
    INVOICE = "invoice"
    LICENSE = "license"
    INSURANCE = "insurance"
    FITNESS = "fitness"
    PHOTO = "photo"
    OTHER = "other"

class NotificationType(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"
    IN_APP = "in_app"

class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    READ = "read"

class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    ASSIGN = "assign"
    STATUS_CHANGE = "status_change"
    EXPORT = "export"
    UPLOAD = "upload"

class Priority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class MaintenanceStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# ─────────────────────────────────────────────
# MIXIN: Timestamps
# ─────────────────────────────────────────────

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ─────────────────────────────────────────────
# USER & AUTH
# ─────────────────────────────────────────────

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), nullable=False, default=UserRole.DISPATCHER)
    status: Mapped[UserStatus] = mapped_column(SAEnum(UserStatus), default=UserStatus.ACTIVE)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"), nullable=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(500))
    password_reset_expires: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    fcm_token: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="users")
    branch: Mapped[Optional["Branch"]] = relationship("Branch", back_populates="users")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="user")
    notifications: Mapped[List["Notification"]] = relationship("Notification", back_populates="user")
    driver_profile: Mapped[Optional["Driver"]] = relationship("Driver", back_populates="user", uselist=False)
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship("RefreshToken", back_populates="user")


class RefreshToken(Base, TimestampMixin):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


# ─────────────────────────────────────────────
# COMPANY & BRANCHES (Multi-tenant)
# ─────────────────────────────────────────────

class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    address: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="India")
    pincode: Mapped[Optional[str]] = mapped_column(String(20))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    gst_number: Mapped[Optional[str]] = mapped_column(String(50))
    pan_number: Mapped[Optional[str]] = mapped_column(String(20))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, default={})
    theme_color: Mapped[Optional[str]] = mapped_column(String(20))

    users: Mapped[List["User"]] = relationship("User", back_populates="company")
    branches: Mapped[List["Branch"]] = relationship("Branch", back_populates="company")
    customers: Mapped[List["Customer"]] = relationship("Customer", back_populates="company")


class Branch(Base, TimestampMixin):
    __tablename__ = "branches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(20))
    address: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    company: Mapped["Company"] = relationship("Company", back_populates="branches")
    users: Mapped[List["User"]] = relationship("User", back_populates="branch")


# ─────────────────────────────────────────────
# CUSTOMER
# ─────────────────────────────────────────────

class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    customer_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    alternate_phone: Mapped[Optional[str]] = mapped_column(String(20))
    gst_number: Mapped[Optional[str]] = mapped_column(String(50))
    pan_number: Mapped[Optional[str]] = mapped_column(String(20))
    billing_address: Mapped[Optional[str]] = mapped_column(Text)
    billing_city: Mapped[Optional[str]] = mapped_column(String(100))
    billing_state: Mapped[Optional[str]] = mapped_column(String(100))
    billing_pincode: Mapped[Optional[str]] = mapped_column(String(20))
    credit_limit: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    outstanding_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    company: Mapped["Company"] = relationship("Company", back_populates="customers")
    orders: Mapped[List["FreightOrder"]] = relationship("FreightOrder", back_populates="customer")


# ─────────────────────────────────────────────
# DRIVER
# ─────────────────────────────────────────────

class Driver(Base, TimestampMixin):
    __tablename__ = "drivers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    driver_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    alternate_phone: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    address: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    pincode: Mapped[Optional[str]] = mapped_column(String(20))
    license_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    license_expiry: Mapped[Optional[date]] = mapped_column(Date)
    license_class: Mapped[Optional[str]] = mapped_column(String(20))
    aadhar_number: Mapped[Optional[str]] = mapped_column(String(20))
    pan_number: Mapped[Optional[str]] = mapped_column(String(20))
    experience_years: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[DriverStatus] = mapped_column(SAEnum(DriverStatus), default=DriverStatus.AVAILABLE)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    current_latitude: Mapped[Optional[float]] = mapped_column(Float)
    current_longitude: Mapped[Optional[float]] = mapped_column(Float)
    last_location_update: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    total_trips: Mapped[int] = mapped_column(Integer, default=0)
    total_km: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    rating: Mapped[float] = mapped_column(Numeric(3, 2), default=5.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped[Optional["User"]] = relationship("User", back_populates="driver_profile")
    vehicles: Mapped[List["VehicleDriverAssignment"]] = relationship("VehicleDriverAssignment", back_populates="driver")
    dispatches: Mapped[List["Dispatch"]] = relationship("Dispatch", back_populates="driver")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="driver")


# ─────────────────────────────────────────────
# VEHICLE
# ─────────────────────────────────────────────

class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(100), nullable=False)
    make: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    year: Mapped[Optional[int]] = mapped_column(Integer)
    color: Mapped[Optional[str]] = mapped_column(String(50))
    capacity_tons: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    capacity_cbm: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    fuel_type: Mapped[Optional[str]] = mapped_column(String(30))
    engine_number: Mapped[Optional[str]] = mapped_column(String(100))
    chassis_number: Mapped[Optional[str]] = mapped_column(String(100))
    insurance_number: Mapped[Optional[str]] = mapped_column(String(100))
    insurance_expiry: Mapped[Optional[date]] = mapped_column(Date)
    fitness_certificate: Mapped[Optional[str]] = mapped_column(String(100))
    fitness_expiry: Mapped[Optional[date]] = mapped_column(Date)
    permit_number: Mapped[Optional[str]] = mapped_column(String(100))
    permit_expiry: Mapped[Optional[date]] = mapped_column(Date)
    puc_number: Mapped[Optional[str]] = mapped_column(String(100))
    puc_expiry: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[VehicleStatus] = mapped_column(SAEnum(VehicleStatus), default=VehicleStatus.AVAILABLE)
    odometer_km: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    last_service_date: Mapped[Optional[date]] = mapped_column(Date)
    next_service_km: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    gps_device_id: Mapped[Optional[str]] = mapped_column(String(100))
    current_latitude: Mapped[Optional[float]] = mapped_column(Float)
    current_longitude: Mapped[Optional[float]] = mapped_column(Float)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    driver_assignments: Mapped[List["VehicleDriverAssignment"]] = relationship("VehicleDriverAssignment", back_populates="vehicle")
    dispatches: Mapped[List["Dispatch"]] = relationship("Dispatch", back_populates="vehicle")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="vehicle")
    maintenance_records: Mapped[List["VehicleMaintenance"]] = relationship("VehicleMaintenance", back_populates="vehicle")


class VehicleDriverAssignment(Base, TimestampMixin):
    __tablename__ = "vehicle_driver_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    driver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    unassigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    assigned_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="driver_assignments")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="vehicles")


class VehicleMaintenance(Base, TimestampMixin):
    __tablename__ = "vehicle_maintenance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    maintenance_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_date: Mapped[Optional[date]] = mapped_column(Date)
    cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    status: Mapped[MaintenanceStatus] = mapped_column(SAEnum(MaintenanceStatus), default=MaintenanceStatus.SCHEDULED)
    performed_by: Mapped[Optional[str]] = mapped_column(String(255))
    next_maintenance_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="maintenance_records")


# ─────────────────────────────────────────────
# LOCATION
# ─────────────────────────────────────────────

class Location(Base, TimestampMixin):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    pincode: Mapped[Optional[str]] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(100), default="India")
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    contact_person: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ─────────────────────────────────────────────
# FREIGHT ORDER
# ─────────────────────────────────────────────

class FreightOrder(Base, TimestampMixin):
    __tablename__ = "freight_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False)
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Status & Priority
    status: Mapped[OrderStatus] = mapped_column(SAEnum(OrderStatus), default=OrderStatus.PENDING, index=True)
    priority: Mapped[Priority] = mapped_column(SAEnum(Priority), default=Priority.NORMAL)

    # Cargo Details
    material_type: Mapped[str] = mapped_column(String(255), nullable=False)
    material_description: Mapped[Optional[str]] = mapped_column(Text)
    weight_tons: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    volume_cbm: Mapped[Optional[float]] = mapped_column(Numeric(10, 3))
    num_packages: Mapped[Optional[int]] = mapped_column(Integer)
    fragile: Mapped[bool] = mapped_column(Boolean, default=False)
    hazardous: Mapped[bool] = mapped_column(Boolean, default=False)

    # Dates
    pickup_date: Mapped[date] = mapped_column(Date, nullable=False)
    pickup_time: Mapped[Optional[str]] = mapped_column(String(10))
    delivery_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_pickup_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_delivery_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Financial
    freight_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    additional_charges: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    discount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    tax_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0)
    payment_status: Mapped[str] = mapped_column(String(30), default="unpaid")
    payment_mode: Mapped[Optional[str]] = mapped_column(String(50))
    invoice_number: Mapped[Optional[str]] = mapped_column(String(100))

    # References
    lr_number: Mapped[Optional[str]] = mapped_column(String(100))  # Lorry Receipt
    eway_bill_number: Mapped[Optional[str]] = mapped_column(String(100))
    qr_code_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Notes
    special_instructions: Mapped[Optional[str]] = mapped_column(Text)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    dispatches: Mapped[List["Dispatch"]] = relationship("Dispatch", back_populates="order")
    order_locations: Mapped[List["OrderLocation"]] = relationship("OrderLocation", back_populates="order", cascade="all, delete-orphan")
    documents: Mapped[List["Document"]] = relationship("Document", back_populates="order")

    __table_args__ = (
        Index("ix_freight_orders_status_created", "status", "created_at"),
        Index("ix_freight_orders_customer_status", "customer_id", "status"),
    )


class OrderLocation(Base):
    __tablename__ = "order_locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("freight_orders.id", ondelete="CASCADE"), nullable=False)
    location_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "pickup" or "delivery"
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(100))
    pincode: Mapped[Optional[str]] = mapped_column(String(20))
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    contact_person: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    order: Mapped["FreightOrder"] = relationship("FreightOrder", back_populates="order_locations")


# ─────────────────────────────────────────────
# DISPATCH
# ─────────────────────────────────────────────

class Dispatch(Base, TimestampMixin):
    __tablename__ = "dispatches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dispatch_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("freight_orders.id"), nullable=False)
    driver_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"), nullable=False)
    assigned_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    status: Mapped[DispatchStatus] = mapped_column(SAEnum(DispatchStatus), default=DispatchStatus.QUEUED, index=True)
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text)
    reschedule_reason: Mapped[Optional[str]] = mapped_column(Text)
    rescheduled_from: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("dispatches.id"))

    # Distance & ETA
    estimated_distance_km: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    actual_distance_km: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    estimated_duration_mins: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_arrival: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Tracking
    driver_notes: Mapped[Optional[str]] = mapped_column(Text)
    pod_received: Mapped[bool] = mapped_column(Boolean, default=False)
    pod_received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    order: Mapped["FreightOrder"] = relationship("FreightOrder", back_populates="dispatches")
    driver: Mapped["Driver"] = relationship("Driver", back_populates="dispatches")
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="dispatches")
    tracking_updates: Mapped[List["TrackingUpdate"]] = relationship("TrackingUpdate", back_populates="dispatch")


class TrackingUpdate(Base):
    __tablename__ = "tracking_updates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dispatches.id", ondelete="CASCADE"), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    speed_kmh: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dispatch: Mapped["Dispatch"] = relationship("Dispatch", back_populates="tracking_updates")


# ─────────────────────────────────────────────
# DOCUMENTS
# ─────────────────────────────────────────────

class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("freight_orders.id"))
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("drivers.id"))
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id"))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(SAEnum(DocumentType), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    order: Mapped[Optional["FreightOrder"]] = relationship("FreightOrder", back_populates="documents")
    driver: Mapped[Optional["Driver"]] = relationship("Driver", back_populates="documents")
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle", back_populates="documents")


# ─────────────────────────────────────────────
# NOTIFICATION
# ─────────────────────────────────────────────

class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    recipient_email: Mapped[Optional[str]] = mapped_column(String(255))
    recipient_phone: Mapped[Optional[str]] = mapped_column(String(20))
    notification_type: Mapped[NotificationType] = mapped_column(SAEnum(NotificationType), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(SAEnum(NotificationStatus), default=NotificationStatus.PENDING)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    reference_type: Mapped[Optional[str]] = mapped_column(String(50))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[Optional["User"]] = relationship("User", back_populates="notifications")


# ─────────────────────────────────────────────
# AUDIT LOG
# ─────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[AuditAction] = mapped_column(SAEnum(AuditAction), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255))
    old_values: Mapped[Optional[dict]] = mapped_column(JSON)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )


# ─────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────

class Setting(Base, TimestampMixin):
    __tablename__ = "settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text)
    value_json: Mapped[Optional[dict]] = mapped_column(JSON)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("company_id", "key", name="uq_settings_company_key"),
    )
