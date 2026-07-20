from typing import Optional, List
from uuid import UUID
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc, cast, String
from sqlalchemy.orm import selectinload
from app.repositories.base import BaseRepository
from app.models import (
    User, Customer, Driver, Vehicle, FreightOrder, Dispatch,
    OrderLocation, TrackingUpdate, Document, Notification, AuditLog,
    RefreshToken, VehicleDriverAssignment, OrderStatus, DispatchStatus
)


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_active_users(self, company_id: UUID) -> List[User]:
        result = await self.db.execute(
            select(User).where(and_(User.company_id == company_id, User.status == "active"))
        )
        return result.scalars().all()


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    def __init__(self, db: AsyncSession):
        super().__init__(RefreshToken, db)

    async def get_by_token(self, token: str) -> Optional[RefreshToken]:
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token == token)
        )
        return result.scalar_one_or_none()

    async def revoke_all_for_user(self, user_id: UUID):
        from sqlalchemy import update
        await self.db.execute(
            update(RefreshToken).where(RefreshToken.user_id == user_id).values(is_revoked=True)
        )


class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, db: AsyncSession):
        super().__init__(Customer, db)

    async def search(self, company_id: UUID, query: str, skip: int, limit: int):
        q = select(Customer).where(
            and_(
                Customer.company_id == company_id,
                Customer.is_active == True,
                or_(
                    Customer.company_name.ilike(f"%{query}%"),
                    Customer.phone.ilike(f"%{query}%"),
                    Customer.contact_person.ilike(f"%{query}%"),
                    Customer.customer_code.ilike(f"%{query}%"),
                )
            )
        ).offset(skip).limit(limit)
        result = await self.db.execute(q)
        return result.scalars().all()

    async def get_next_code(self, company_id: UUID) -> str:
        result = await self.db.execute(
            select(func.count(Customer.id)).where(Customer.company_id == company_id)
        )
        count = result.scalar_one()
        return f"CUST-{count + 1:04d}"


class DriverRepository(BaseRepository[Driver]):
    def __init__(self, db: AsyncSession):
        super().__init__(Driver, db)

    async def get_available_drivers(self) -> List[Driver]:
        result = await self.db.execute(
            select(Driver).where(and_(Driver.status == "available", Driver.is_active == True))
        )
        return result.scalars().all()

    async def search(self, query: str, skip: int, limit: int) -> List[Driver]:
        q = select(Driver).where(
            and_(
                Driver.is_active == True,
                or_(
                    Driver.full_name.ilike(f"%{query}%"),
                    Driver.phone.ilike(f"%{query}%"),
                    Driver.license_number.ilike(f"%{query}%"),
                    Driver.driver_code.ilike(f"%{query}%"),
                )
            )
        ).offset(skip).limit(limit)
        result = await self.db.execute(q)
        return result.scalars().all()

    async def get_next_code(self) -> str:
        result = await self.db.execute(select(func.count(Driver.id)))
        count = result.scalar_one()
        return f"DRV-{count + 1:04d}"


class VehicleRepository(BaseRepository[Vehicle]):
    def __init__(self, db: AsyncSession):
        super().__init__(Vehicle, db)

    async def get_available_vehicles(self) -> List[Vehicle]:
        result = await self.db.execute(
            select(Vehicle).where(and_(Vehicle.status == "available", Vehicle.is_active == True))
        )
        return result.scalars().all()

    async def get_by_registration(self, reg_number: str) -> Optional[Vehicle]:
        result = await self.db.execute(
            select(Vehicle).where(Vehicle.registration_number == reg_number)
        )
        return result.scalar_one_or_none()

    async def search(self, query: str, skip: int, limit: int) -> List[Vehicle]:
        q = select(Vehicle).where(
            and_(
                Vehicle.is_active == True,
                or_(
                    Vehicle.registration_number.ilike(f"%{query}%"),
                    Vehicle.vehicle_type.ilike(f"%{query}%"),
                    Vehicle.make.ilike(f"%{query}%"),
                )
            )
        ).offset(skip).limit(limit)
        result = await self.db.execute(q)
        return result.scalars().all()


class FreightOrderRepository(BaseRepository[FreightOrder]):
    def __init__(self, db: AsyncSession):
        super().__init__(FreightOrder, db)

    async def get_with_relations(self, order_id: UUID) -> Optional[FreightOrder]:
        result = await self.db.execute(
            select(FreightOrder)
            .options(
                selectinload(FreightOrder.customer),
                selectinload(FreightOrder.order_locations),
                selectinload(FreightOrder.dispatches),
                selectinload(FreightOrder.documents),
            )
            .where(FreightOrder.id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_dashboard_stats(self, company_id: UUID) -> dict:
        today = date.today()
        results = {}

        total_q = await self.db.execute(
            select(func.count(FreightOrder.id)).where(FreightOrder.company_id == company_id)
        )
        results["total_orders"] = total_q.scalar_one()

        today_q = await self.db.execute(
            select(func.count(FreightOrder.id)).where(
                and_(FreightOrder.company_id == company_id, FreightOrder.pickup_date == today)
            )
        )
        results["today_orders"] = today_q.scalar_one()

        pending_q = await self.db.execute(
            select(func.count(FreightOrder.id)).where(
                and_(
                    FreightOrder.company_id == company_id,
                    FreightOrder.status == OrderStatus.PENDING
                )
            )
        )
        results["pending_orders"] = pending_q.scalar_one()

        completed_q = await self.db.execute(
            select(func.count(FreightOrder.id)).where(
                and_(
                    FreightOrder.company_id == company_id,
                    FreightOrder.status == OrderStatus.DELIVERED
                )
            )
        )
        results["completed_orders"] = completed_q.scalar_one()

        revenue_q = await self.db.execute(
            select(func.sum(FreightOrder.total_amount)).where(
                and_(
                    FreightOrder.company_id == company_id,
                    FreightOrder.status == OrderStatus.DELIVERED
                )
            )
        )
        results["total_revenue"] = float(revenue_q.scalar_one() or 0)

        return results

    async def advanced_filter(
        self,
        company_id: UUID,
        status: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        driver_id: Optional[UUID] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        query: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[List[FreightOrder], int]:
        filters = [FreightOrder.company_id == company_id]

        if status:
            filters.append(FreightOrder.status == status)
        if customer_id:
            filters.append(FreightOrder.customer_id == customer_id)
        if date_from:
            filters.append(FreightOrder.pickup_date >= date_from)
        if date_to:
            filters.append(FreightOrder.pickup_date <= date_to)
        if query:
            filters.append(
                or_(
                    FreightOrder.order_number.ilike(f"%{query}%"),
                    FreightOrder.material_type.ilike(f"%{query}%"),
                    FreightOrder.lr_number.ilike(f"%{query}%"),
                )
            )

        count = await self.count(filters)

        order_col = getattr(FreightOrder, sort_by, FreightOrder.created_at)
        order_dir = desc(order_col) if sort_order == "desc" else asc(order_col)

        items = await self.get_all(skip=skip, limit=limit, filters=filters, order_by=order_dir)
        return items, count

    async def get_revenue_by_month(self, company_id: UUID, year: int) -> List[dict]:
        result = await self.db.execute(
            select(
                func.extract("month", FreightOrder.created_at).label("month"),
                func.sum(FreightOrder.total_amount).label("revenue"),
                func.count(FreightOrder.id).label("count"),
            )
            .where(
                and_(
                    FreightOrder.company_id == company_id,
                    FreightOrder.status == OrderStatus.DELIVERED,
                    func.extract("year", FreightOrder.created_at) == year,
                )
            )
            .group_by("month")
            .order_by("month")
        )
        return [{"month": int(r.month), "revenue": float(r.revenue or 0), "count": int(r.count)} for r in result]

    async def get_next_number(self, company_id: UUID) -> str:
        result = await self.db.execute(
            select(func.count(FreightOrder.id)).where(FreightOrder.company_id == company_id)
        )
        count = result.scalar_one()
        return f"WH-{count + 1:06d}"


class DispatchRepository(BaseRepository[Dispatch]):
    def __init__(self, db: AsyncSession):
        super().__init__(Dispatch, db)

    async def get_with_relations(self, dispatch_id: UUID) -> Optional[Dispatch]:
        result = await self.db.execute(
            select(Dispatch)
            .options(
                selectinload(Dispatch.driver),
                selectinload(Dispatch.vehicle),
                selectinload(Dispatch.order).selectinload(FreightOrder.customer),
                selectinload(Dispatch.tracking_updates),
            )
            .where(Dispatch.id == dispatch_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_driver(self, driver_id: UUID) -> Optional[Dispatch]:
        result = await self.db.execute(
            select(Dispatch).where(
                and_(
                    Dispatch.driver_id == driver_id,
                    Dispatch.status.in_(["queued", "dispatched", "in_transit"]),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_dispatch_queue(self, company_id: UUID) -> List[Dispatch]:
        result = await self.db.execute(
            select(Dispatch)
            .join(FreightOrder, Dispatch.order_id == FreightOrder.id)
            .options(
                selectinload(Dispatch.driver),
                selectinload(Dispatch.vehicle),
                selectinload(Dispatch.order),
            )
            .where(
                and_(
                    FreightOrder.company_id == company_id,
                    Dispatch.status.in_(["queued", "dispatched", "in_transit"]),
                )
            )
            .order_by(asc(Dispatch.created_at))
        )
        return result.scalars().all()

    async def get_next_number(self) -> str:
        result = await self.db.execute(select(func.count(Dispatch.id)))
        count = result.scalar_one()
        return f"DSP-{count + 1:06d}"


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, db: AsyncSession):
        super().__init__(AuditLog, db)

    async def create_log(
        self,
        user_id: Optional[UUID],
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        description: Optional[str] = None,
    ) -> AuditLog:
        return await self.create({
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "old_values": old_values,
            "new_values": new_values,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "description": description,
        })


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, db: AsyncSession):
        super().__init__(Document, db)

    async def get_by_order(self, order_id: UUID) -> List[Document]:
        result = await self.db.execute(
            select(Document).where(and_(Document.order_id == order_id, Document.is_active == True))
        )
        return result.scalars().all()

    async def get_by_driver(self, driver_id: UUID) -> List[Document]:
        result = await self.db.execute(
            select(Document).where(and_(Document.driver_id == driver_id, Document.is_active == True))
        )
        return result.scalars().all()


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, db: AsyncSession):
        super().__init__(Notification, db)

    async def get_unread_for_user(self, user_id: UUID) -> List[Notification]:
        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.read_at == None,
                )
            ).order_by(desc(Notification.created_at)).limit(50)
        )
        return result.scalars().all()

    async def mark_all_read(self, user_id: UUID):
        from sqlalchemy import update
        await self.db.execute(
            update(Notification)
            .where(and_(Notification.user_id == user_id, Notification.read_at == None))
            .values(read_at=datetime.utcnow())
        )
