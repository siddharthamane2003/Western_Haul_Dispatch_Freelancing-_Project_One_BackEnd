from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.deps import get_current_user, get_dispatcher_or_admin, get_admin_user
from app.models import User
from app.repositories.repositories import DriverRepository, VehicleRepository
from app.schemas.entities import (
    DriverCreate, DriverUpdate, DriverResponse, DriverLocationUpdate,
    VehicleCreate, VehicleUpdate, VehicleResponse, VehicleAssignDriver
)
from app.schemas.dispatch import PaginatedResponse

driver_router = APIRouter(prefix="/drivers", tags=["Drivers"])
vehicle_router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


# ─── DRIVERS ───

@driver_router.post("/", response_model=DriverResponse, status_code=201)
async def create_driver(
    driver_in: DriverCreate,
    current_user: User = Depends(get_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = DriverRepository(db)
    driver_code = await repo.get_next_code()
    data = driver_in.model_dump()
    data["driver_code"] = driver_code
    return await repo.create(data)


@driver_router.get("/", response_model=PaginatedResponse)
async def list_drivers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = DriverRepository(db)
    skip = (page - 1) * size
    from app.models import Driver
    from sqlalchemy import and_

    filters = [Driver.is_active == True]
    if status:
        filters.append(Driver.status == status)

    if q:
        items = await repo.search(q, skip, size)
        total = len(items)
    else:
        total = await repo.count(filters=filters)
        items = await repo.get_all(skip=skip, limit=size, filters=filters)

    return PaginatedResponse(
        items=[DriverResponse.model_validate(i) for i in items],
        total=total, page=page, size=size, pages=(total + size - 1) // size,
    )


@driver_router.get("/available", response_model=list[DriverResponse])
async def get_available_drivers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = DriverRepository(db)
    drivers = await repo.get_available_drivers()
    return [DriverResponse.model_validate(d) for d in drivers]


@driver_router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(
    driver_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = DriverRepository(db)
    driver = await repo.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver


@driver_router.put("/{driver_id}", response_model=DriverResponse)
async def update_driver(
    driver_id: UUID,
    driver_in: DriverUpdate,
    current_user: User = Depends(get_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = DriverRepository(db)
    driver = await repo.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return await repo.update(driver_id, driver_in.model_dump(exclude_none=True))


@driver_router.delete("/{driver_id}")
async def delete_driver(
    driver_id: UUID,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    repo = DriverRepository(db)
    if not await repo.get(driver_id):
        raise HTTPException(status_code=404, detail="Driver not found")
    await repo.soft_delete(driver_id)
    return {"message": "Driver deactivated successfully"}


@driver_router.patch("/{driver_id}/location")
async def update_driver_location(
    driver_id: UUID,
    location: DriverLocationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime
    repo = DriverRepository(db)
    await repo.update(driver_id, {
        "current_latitude": location.latitude,
        "current_longitude": location.longitude,
        "last_location_update": datetime.utcnow(),
    })
    return {"message": "Location updated"}


# ─── VEHICLES ───

@vehicle_router.post("/", response_model=VehicleResponse, status_code=201)
async def create_vehicle(
    vehicle_in: VehicleCreate,
    current_user: User = Depends(get_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    existing = await repo.get_by_registration(vehicle_in.registration_number)
    if existing:
        raise HTTPException(status_code=409, detail="Vehicle with this registration already exists")
    return await repo.create(vehicle_in.model_dump())


@vehicle_router.get("/", response_model=PaginatedResponse)
async def list_vehicles(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    skip = (page - 1) * size
    from app.models import Vehicle

    filters = [Vehicle.is_active == True]
    if status:
        filters.append(Vehicle.status == status)

    if q:
        items = await repo.search(q, skip, size)
        total = len(items)
    else:
        total = await repo.count(filters=filters)
        items = await repo.get_all(skip=skip, limit=size, filters=filters)

    return PaginatedResponse(
        items=[VehicleResponse.model_validate(i) for i in items],
        total=total, page=page, size=size, pages=(total + size - 1) // size,
    )


@vehicle_router.get("/available", response_model=list[VehicleResponse])
async def get_available_vehicles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    vehicles = await repo.get_available_vehicles()
    return [VehicleResponse.model_validate(v) for v in vehicles]


@vehicle_router.get("/{vehicle_id}", response_model=VehicleResponse)
async def get_vehicle(
    vehicle_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    vehicle = await repo.get(vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle


@vehicle_router.put("/{vehicle_id}", response_model=VehicleResponse)
async def update_vehicle(
    vehicle_id: UUID,
    vehicle_in: VehicleUpdate,
    current_user: User = Depends(get_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    vehicle = await repo.get(vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return await repo.update(vehicle_id, vehicle_in.model_dump(exclude_none=True))


@vehicle_router.delete("/{vehicle_id}")
async def delete_vehicle(
    vehicle_id: UUID,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    if not await repo.get(vehicle_id):
        raise HTTPException(status_code=404, detail="Vehicle not found")
    await repo.soft_delete(vehicle_id)
    return {"message": "Vehicle deactivated successfully"}


@vehicle_router.post("/{vehicle_id}/assign-driver")
async def assign_driver_to_vehicle(
    vehicle_id: UUID,
    body: VehicleAssignDriver,
    current_user: User = Depends(get_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.models import VehicleDriverAssignment
    from datetime import datetime

    assignment = VehicleDriverAssignment(
        vehicle_id=vehicle_id,
        driver_id=body.driver_id,
        is_primary=body.is_primary,
        assigned_by=current_user.id,
    )
    db.add(assignment)
    await db.flush()
    return {"message": "Driver assigned to vehicle successfully"}
