from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import date
from typing import Optional
from uuid import UUID
import io

from app.db.database import get_db
from app.api.deps import get_current_user
from app.models import User, FreightOrder, Driver, Vehicle, Customer, Dispatch, OrderStatus

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/revenue")
async def revenue_report(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    customer_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revenue report with optional filters."""
    filters = [
        FreightOrder.company_id == current_user.company_id,
        FreightOrder.status == OrderStatus.DELIVERED,
    ]
    if date_from:
        filters.append(FreightOrder.pickup_date >= date_from)
    if date_to:
        filters.append(FreightOrder.pickup_date <= date_to)
    if customer_id:
        filters.append(FreightOrder.customer_id == customer_id)

    result = await db.execute(
        select(
            func.count(FreightOrder.id).label("total_orders"),
            func.sum(FreightOrder.freight_amount).label("total_freight"),
            func.sum(FreightOrder.additional_charges).label("total_additional"),
            func.sum(FreightOrder.discount).label("total_discount"),
            func.sum(FreightOrder.tax_amount).label("total_tax"),
            func.sum(FreightOrder.total_amount).label("total_revenue"),
            func.sum(FreightOrder.weight_tons).label("total_weight"),
        ).where(and_(*filters))
    )
    row = result.fetchone()
    return {
        "total_orders": int(row.total_orders or 0),
        "total_freight": float(row.total_freight or 0),
        "total_additional": float(row.total_additional or 0),
        "total_discount": float(row.total_discount or 0),
        "total_tax": float(row.total_tax or 0),
        "total_revenue": float(row.total_revenue or 0),
        "total_weight_tons": float(row.total_weight or 0),
        "filters": {
            "date_from": str(date_from) if date_from else None,
            "date_to": str(date_to) if date_to else None,
        },
    }


@router.get("/drivers")
async def driver_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Driver performance report."""
    result = await db.execute(
        select(
            Driver.id,
            Driver.full_name,
            Driver.driver_code,
            Driver.status,
            Driver.total_trips,
            Driver.total_km,
            Driver.rating,
            Driver.license_expiry,
        )
        .where(Driver.is_active == True)
        .order_by(desc(Driver.total_trips))
    )
    rows = result.fetchall()
    return [
        {
            "driver_id": str(r.id),
            "driver_code": r.driver_code,
            "full_name": r.full_name,
            "status": str(r.status),
            "total_trips": r.total_trips,
            "total_km": float(r.total_km),
            "rating": float(r.rating),
            "license_expiry": str(r.license_expiry) if r.license_expiry else None,
        }
        for r in rows
    ]


@router.get("/vehicles")
async def vehicle_report(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Vehicle status and compliance report."""
    today = date.today()
    result = await db.execute(
        select(Vehicle)
        .where(Vehicle.is_active == True)
        .order_by(Vehicle.registration_number)
    )
    vehicles = result.scalars().all()
    return [
        {
            "vehicle_id": str(v.id),
            "registration_number": v.registration_number,
            "vehicle_type": v.vehicle_type,
            "capacity_tons": float(v.capacity_tons),
            "status": str(v.status),
            "insurance_expiry": str(v.insurance_expiry) if v.insurance_expiry else None,
            "fitness_expiry": str(v.fitness_expiry) if v.fitness_expiry else None,
            "permit_expiry": str(v.permit_expiry) if v.permit_expiry else None,
            "puc_expiry": str(v.puc_expiry) if v.puc_expiry else None,
            "insurance_expired": v.insurance_expiry and v.insurance_expiry < today,
            "fitness_expired": v.fitness_expiry and v.fitness_expiry < today,
            "odometer_km": float(v.odometer_km),
        }
        for v in vehicles
    ]


@router.get("/dispatch-summary")
async def dispatch_summary_report(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dispatch summary with status breakdown."""
    filters = []
    if date_from:
        filters.append(Dispatch.created_at >= date_from)
    if date_to:
        filters.append(Dispatch.created_at <= date_to)

    result = await db.execute(
        select(
            Dispatch.status,
            func.count(Dispatch.id).label("count"),
        )
        .where(and_(*filters) if filters else True)
        .group_by(Dispatch.status)
    )
    by_status = {str(r.status): int(r.count) for r in result.fetchall()}

    total = await db.execute(select(func.count(Dispatch.id)).where(and_(*filters) if filters else True))

    return {
        "total_dispatches": int(total.scalar_one()),
        "by_status": by_status,
        "date_range": {
            "from": str(date_from) if date_from else None,
            "to": str(date_to) if date_to else None,
        },
    }


@router.get("/export/orders")
async def export_orders_csv(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export orders as CSV."""
    from fastapi.responses import StreamingResponse
    import csv

    filters = [FreightOrder.company_id == current_user.company_id]
    if status:
        filters.append(FreightOrder.status == status)
    if date_from:
        filters.append(FreightOrder.pickup_date >= date_from)
    if date_to:
        filters.append(FreightOrder.pickup_date <= date_to)

    result = await db.execute(
        select(FreightOrder).where(and_(*filters)).order_by(desc(FreightOrder.created_at))
    )
    orders = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Order Number", "Status", "Material Type", "Weight (T)",
        "Pickup Date", "Freight Amount", "Total Amount",
        "Payment Status", "LR Number", "Created At"
    ])

    for o in orders:
        writer.writerow([
            o.order_number, str(o.status), o.material_type, float(o.weight_tons),
            str(o.pickup_date), float(o.freight_amount), float(o.total_amount),
            o.payment_status, o.lr_number or "", o.created_at.strftime("%Y-%m-%d %H:%M")
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders_export.csv"},
    )


@router.get("/audit-logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get audit logs with filtering."""
    from app.models import AuditLog
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)

    total_q = await db.execute(
        select(func.count(AuditLog.id)).where(and_(*filters) if filters else True)
    )
    total = total_q.scalar_one()

    result = await db.execute(
        select(AuditLog)
        .where(and_(*filters) if filters else True)
        .order_by(desc(AuditLog.created_at))
        .offset((page - 1) * size)
        .limit(size)
    )
    logs = result.scalars().all()

    return {
        "items": [
            {
                "id": str(l.id),
                "user_id": str(l.user_id) if l.user_id else None,
                "action": str(l.action),
                "resource_type": l.resource_type,
                "resource_id": l.resource_id,
                "description": l.description,
                "ip_address": l.ip_address,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ],
        "total": total,
        "page": page,
        "size": size,
    }
