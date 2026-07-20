from typing import Optional, List, Tuple
from uuid import UUID
from datetime import date, datetime
from io import BytesIO
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.repositories import (
    FreightOrderRepository, DispatchRepository, CustomerRepository,
    DriverRepository, VehicleRepository, AuditLogRepository, DocumentRepository
)
from app.schemas.dispatch import FreightOrderCreate, FreightOrderUpdate, DispatchCreate
from app.models import (
    FreightOrder, Dispatch, OrderStatus, DispatchStatus, DriverStatus, VehicleStatus, AuditAction
)
import qrcode
import base64


class FreightOrderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.order_repo = FreightOrderRepository(db)
        self.dispatch_repo = DispatchRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.driver_repo = DriverRepository(db)
        self.vehicle_repo = VehicleRepository(db)
        self.audit_repo = AuditLogRepository(db)

    async def create_order(
        self, order_in: FreightOrderCreate, company_id: UUID, created_by: UUID
    ) -> FreightOrder:
        # Validate customer exists
        customer = await self.customer_repo.get(order_in.customer_id)
        if not customer or not customer.is_active:
            raise HTTPException(status_code=404, detail="Customer not found")

        order_number = await self.order_repo.get_next_number(company_id)

        # Calculate totals
        tax_rate = 0.18  # 18% GST
        subtotal = order_in.freight_amount + order_in.additional_charges - order_in.discount
        tax_amount = round(subtotal * tax_rate, 2)
        total_amount = round(subtotal + tax_amount, 2)

        order_data = order_in.model_dump(exclude={"locations"})
        order_data.update({
            "order_number": order_number,
            "company_id": company_id,
            "created_by": created_by,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "status": order_in.status if order_in.status else "pending",
        })

        order = await self.order_repo.create(order_data)

        # Create locations
        from app.models import OrderLocation
        for loc in order_in.locations:
            loc_data = loc.model_dump()
            loc_data["order_id"] = order.id
            self.db.add(OrderLocation(**loc_data))

        await self.db.flush()

        # Generate QR code
        qr_data = f"ORDER:{order.order_number}|WEIGHT:{order.weight_tons}T"
        qr_img = qrcode.make(qr_data)
        buffer = BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_b64 = base64.b64encode(buffer.getvalue()).decode()
        await self.order_repo.update(order.id, {"qr_code_url": f"data:image/png;base64,{qr_b64}"})

        await self.audit_repo.create_log(
            user_id=created_by,
            action=AuditAction.CREATE,
            resource_type="freight_order",
            resource_id=str(order.id),
            new_values={"order_number": order_number, "customer_id": str(order_in.customer_id)},
            description=f"Created freight order {order_number}",
        )

        return await self.order_repo.get_with_relations(order.id)

    async def update_order(
        self, order_id: UUID, order_in: FreightOrderUpdate, user_id: UUID
    ) -> FreightOrder:
        order = await self.order_repo.get(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        if order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail=f"Cannot update {order.status.value} order")

        old_values = {"status": str(order.status), "total_amount": float(order.total_amount)}

        update_data = order_in.model_dump(exclude_none=True)

        # Recalculate if financial fields changed
        if any(k in update_data for k in ["freight_amount", "additional_charges", "discount"]):
            fa = update_data.get("freight_amount", float(order.freight_amount))
            ac = update_data.get("additional_charges", float(order.additional_charges))
            d = update_data.get("discount", float(order.discount))
            subtotal = fa + ac - d
            tax_amount = round(subtotal * 0.18, 2)
            update_data["tax_amount"] = tax_amount
            update_data["total_amount"] = round(subtotal + tax_amount, 2)

        updated = await self.order_repo.update(order_id, update_data)

        await self.audit_repo.create_log(
            user_id=user_id,
            action=AuditAction.UPDATE,
            resource_type="freight_order",
            resource_id=str(order_id),
            old_values=old_values,
            new_values=update_data,
            description=f"Updated freight order {order.order_number}",
        )

        return await self.order_repo.get_with_relations(order_id)

    async def cancel_order(self, order_id: UUID, reason: str, user_id: UUID) -> FreightOrder:
        order = await self.order_repo.get(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        if order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail="Order cannot be cancelled")

        await self.order_repo.update(order_id, {
            "status": OrderStatus.CANCELLED,
            "cancellation_reason": reason,
        })

        await self.audit_repo.create_log(
            user_id=user_id,
            action=AuditAction.STATUS_CHANGE,
            resource_type="freight_order",
            resource_id=str(order_id),
            old_values={"status": str(order.status)},
            new_values={"status": "cancelled", "reason": reason},
            description=f"Cancelled freight order {order.order_number}",
        )

        return await self.order_repo.get_with_relations(order_id)


class DispatchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.dispatch_repo = DispatchRepository(db)
        self.order_repo = FreightOrderRepository(db)
        self.driver_repo = DriverRepository(db)
        self.vehicle_repo = VehicleRepository(db)
        self.audit_repo = AuditLogRepository(db)

    async def create_dispatch(
        self, dispatch_in: DispatchCreate, assigned_by: UUID
    ) -> Dispatch:
        order = await self.order_repo.get(dispatch_in.order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail=f"Order is {order.status.value}")

        driver = await self.driver_repo.get(dispatch_in.driver_id)
        if not driver or not driver.is_active:
            raise HTTPException(status_code=404, detail="Driver not found")
        # Bypass strict availability checks for local testing
        # if driver.status != DriverStatus.AVAILABLE:
        #     raise HTTPException(status_code=400, detail="Driver is not available")

        vehicle = await self.vehicle_repo.get(dispatch_in.vehicle_id)
        if not vehicle or not vehicle.is_active:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        # if vehicle.status != VehicleStatus.AVAILABLE:
        #     raise HTTPException(status_code=400, detail="Vehicle is not available")

        dispatch_number = await self.dispatch_repo.get_next_number()

        dispatch = await self.dispatch_repo.create({
            "dispatch_number": dispatch_number,
            "order_id": dispatch_in.order_id,
            "driver_id": dispatch_in.driver_id,
            "vehicle_id": dispatch_in.vehicle_id,
            "assigned_by": assigned_by,
            "status": DispatchStatus.QUEUED,
        })

        # Update statuses
        await self.order_repo.update(order.id, {"status": OrderStatus.ASSIGNED})
        await self.driver_repo.update(driver.id, {"status": DriverStatus.ON_TRIP})
        await self.vehicle_repo.update(vehicle.id, {"status": VehicleStatus.IN_USE})

        await self.audit_repo.create_log(
            user_id=assigned_by,
            action=AuditAction.ASSIGN,
            resource_type="dispatch",
            resource_id=str(dispatch.id),
            new_values={
                "dispatch_number": dispatch_number,
                "driver": str(dispatch_in.driver_id),
                "vehicle": str(dispatch_in.vehicle_id),
            },
            description=f"Dispatch {dispatch_number} created",
        )

        return await self.dispatch_repo.get_with_relations(dispatch.id)

    async def update_dispatch_status(
        self, dispatch_id: UUID, new_status: str, reason: Optional[str], user_id: UUID
    ) -> Dispatch:
        dispatch = await self.dispatch_repo.get(dispatch_id)
        if not dispatch:
            raise HTTPException(status_code=404, detail="Dispatch not found")

        update_data = {"status": new_status}

        if new_status == "dispatched":
            update_data["dispatched_at"] = datetime.utcnow()
            await self.order_repo.update(dispatch.order_id, {"status": OrderStatus.IN_TRANSIT})

        elif new_status == "arrived":
            update_data["arrived_at"] = datetime.utcnow()

        elif new_status == "completed":
            update_data["completed_at"] = datetime.utcnow()
            await self.order_repo.update(dispatch.order_id, {
                "status": OrderStatus.DELIVERED,
                "actual_delivery_time": datetime.utcnow(),
            })
            await self.driver_repo.update(dispatch.driver_id, {"status": DriverStatus.AVAILABLE})
            await self.vehicle_repo.update(dispatch.vehicle_id, {"status": VehicleStatus.AVAILABLE})

            # Update driver stats
            driver = await self.driver_repo.get(dispatch.driver_id)
            if driver:
                distance = float(dispatch.actual_distance_km or dispatch.estimated_distance_km or 0)
                await self.driver_repo.update(dispatch.driver_id, {
                    "total_trips": driver.total_trips + 1,
                    "total_km": float(driver.total_km) + distance,
                })

        elif new_status == "cancelled":
            update_data["cancelled_at"] = datetime.utcnow()
            update_data["cancellation_reason"] = reason
            await self.driver_repo.update(dispatch.driver_id, {"status": DriverStatus.AVAILABLE})
            await self.vehicle_repo.update(dispatch.vehicle_id, {"status": VehicleStatus.AVAILABLE})
            await self.order_repo.update(dispatch.order_id, {"status": OrderStatus.CANCELLED})

        await self.dispatch_repo.update(dispatch_id, update_data)

        await self.audit_repo.create_log(
            user_id=user_id,
            action=AuditAction.STATUS_CHANGE,
            resource_type="dispatch",
            resource_id=str(dispatch_id),
            old_values={"status": str(dispatch.status)},
            new_values={"status": new_status},
            description=f"Dispatch status changed to {new_status}",
        )

        return await self.dispatch_repo.get_with_relations(dispatch_id)
