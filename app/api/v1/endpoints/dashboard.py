from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models import User, FreightOrder, Driver, Vehicle, Customer, Dispatch, AuditLog, OrderStatus, DispatchStatus

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get real-time dashboard statistics."""
    company_id = current_user.company_id
    today = date.today()
    this_month_start = today.replace(day=1)

    # Orders stats
    async def count_orders(filters):
        r = await db.execute(select(func.count(FreightOrder.id)).where(*filters))
        return r.scalar_one()

    total_orders = await count_orders([FreightOrder.company_id == company_id])
    today_orders = await count_orders([FreightOrder.company_id == company_id, FreightOrder.pickup_date == today])
    pending_orders = await count_orders([FreightOrder.company_id == company_id, FreightOrder.status == OrderStatus.PENDING])
    in_transit = await count_orders([FreightOrder.company_id == company_id, FreightOrder.status == OrderStatus.IN_TRANSIT])
    completed_orders = await count_orders([FreightOrder.company_id == company_id, FreightOrder.status == OrderStatus.DELIVERED])
    cancelled_orders = await count_orders([FreightOrder.company_id == company_id, FreightOrder.status == OrderStatus.CANCELLED])

    # Revenue
    rev_q = await db.execute(
        select(func.sum(FreightOrder.total_amount)).where(
            and_(FreightOrder.company_id == company_id, FreightOrder.status == OrderStatus.DELIVERED)
        )
    )
    total_revenue = float(rev_q.scalar_one() or 0)

    month_rev_q = await db.execute(
        select(func.sum(FreightOrder.total_amount)).where(
            and_(
                FreightOrder.company_id == company_id,
                FreightOrder.status == OrderStatus.DELIVERED,
                FreightOrder.created_at >= this_month_start,
            )
        )
    )
    month_revenue = float(month_rev_q.scalar_one() or 0)

    # Drivers & Vehicles
    drivers_online = await db.execute(
        select(func.count(Driver.id)).where(Driver.status == "on_trip", Driver.is_active == True)
    )
    vehicles_available = await db.execute(
        select(func.count(Vehicle.id)).where(Vehicle.status == "available", Vehicle.is_active == True)
    )
    total_customers = await db.execute(
        select(func.count(Customer.id)).where(Customer.company_id == company_id, Customer.is_active == True)
    )

    return {
        "orders": {
            "total": total_orders,
            "today": today_orders,
            "pending": pending_orders,
            "in_transit": in_transit,
            "completed": completed_orders,
            "cancelled": cancelled_orders,
        },
        "revenue": {
            "total": total_revenue,
            "this_month": month_revenue,
        },
        "fleet": {
            "drivers_online": drivers_online.scalar_one(),
            "vehicles_available": vehicles_available.scalar_one(),
        },
        "customers": total_customers.scalar_one(),
    }


@router.get("/monthly-analytics")
async def get_monthly_analytics(
    year: int = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get monthly orders and revenue analytics."""
    if not year:
        year = date.today().year

    repo_cls = FreightOrder
    result = await db.execute(
        select(
            func.extract("month", FreightOrder.created_at).label("month"),
            func.count(FreightOrder.id).label("orders"),
            func.sum(FreightOrder.total_amount).label("revenue"),
        )
        .where(
            and_(
                FreightOrder.company_id == current_user.company_id,
                func.extract("year", FreightOrder.created_at) == year,
            )
        )
        .group_by("month")
        .order_by("month")
    )
    rows = result.fetchall()

    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    monthly = {i+1: {"month": months[i], "orders": 0, "revenue": 0.0} for i in range(12)}
    for row in rows:
        m = int(row.month)
        monthly[m]["orders"] = int(row.orders)
        monthly[m]["revenue"] = float(row.revenue or 0)

    return {"year": year, "data": list(monthly.values())}


@router.get("/top-customers")
async def get_top_customers(
    limit: int = Query(10, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get top customers by revenue."""
    result = await db.execute(
        select(
            Customer.id,
            Customer.company_name,
            func.count(FreightOrder.id).label("total_orders"),
            func.sum(FreightOrder.total_amount).label("total_revenue"),
        )
        .join(FreightOrder, FreightOrder.customer_id == Customer.id)
        .where(
            and_(
                Customer.company_id == current_user.company_id,
                FreightOrder.status == OrderStatus.DELIVERED,
            )
        )
        .group_by(Customer.id, Customer.company_name)
        .order_by(desc("total_revenue"))
        .limit(limit)
    )
    return [
        {
            "customer_id": str(r.id),
            "company_name": r.company_name,
            "total_orders": int(r.total_orders),
            "total_revenue": float(r.total_revenue or 0),
        }
        for r in result.fetchall()
    ]


@router.get("/top-drivers")
async def get_top_drivers(
    limit: int = Query(10, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get top drivers by completed trips."""
    result = await db.execute(
        select(
            Driver.id,
            Driver.full_name,
            Driver.total_trips,
            Driver.total_km,
            Driver.rating,
        )
        .where(Driver.is_active == True)
        .order_by(desc(Driver.total_trips))
        .limit(limit)
    )
    return [
        {
            "driver_id": str(r.id),
            "full_name": r.full_name,
            "total_trips": r.total_trips,
            "total_km": float(r.total_km),
            "rating": float(r.rating),
        }
        for r in result.fetchall()
    ]


@router.get("/recent-dispatches")
async def get_recent_dispatches(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent dispatch activity."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Dispatch)
        .join(FreightOrder, Dispatch.order_id == FreightOrder.id)
        .where(FreightOrder.company_id == current_user.company_id)
        .options(
            selectinload(Dispatch.driver),
            selectinload(Dispatch.vehicle),
            selectinload(Dispatch.order),
        )
        .order_by(desc(Dispatch.created_at))
        .limit(limit)
    )
    dispatches = result.scalars().all()

    return [
        {
            "id": str(d.id),
            "dispatch_number": d.dispatch_number,
            "order_number": d.order.order_number if d.order else None,
            "driver_name": d.driver.full_name if d.driver else None,
            "vehicle_reg": d.vehicle.registration_number if d.vehicle else None,
            "status": str(d.status),
            "created_at": d.created_at.isoformat(),
        }
        for d in dispatches
    ]
