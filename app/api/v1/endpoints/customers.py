from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.deps import get_current_user, get_dispatcher_or_admin
from app.models import User
from app.repositories.repositories import CustomerRepository
from app.schemas.entities import CustomerCreate, CustomerUpdate, CustomerResponse
from app.schemas.dispatch import PaginatedResponse

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post("/", response_model=CustomerResponse, status_code=201)
async def create_customer(
    customer_in: CustomerCreate,
    current_user: User = Depends(get_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new customer."""
    repo = CustomerRepository(db)
    # Check company context
    company_id = current_user.company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="User must belong to a company")

    customer_code = await repo.get_next_code(company_id)
    data = customer_in.model_dump()
    data["customer_code"] = customer_code
    data["company_id"] = company_id
    return await repo.create(data)


@router.get("/", response_model=PaginatedResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: Optional[str] = None,
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List customers with pagination and search."""
    repo = CustomerRepository(db)
    company_id = current_user.company_id
    skip = (page - 1) * size

    from sqlalchemy import and_
    from app.models import Customer

    filters = [Customer.company_id == company_id]
    if active_only:
        filters.append(Customer.is_active == True)

    if q:
        items = await repo.search(company_id, q, skip, size)
        total = len(items)
    else:
        total = await repo.count(filters=filters)
        items = await repo.get_all(skip=skip, limit=size, filters=filters)

    return PaginatedResponse(
        items=[CustomerResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific customer by ID."""
    repo = CustomerRepository(db)
    customer = await repo.get(customer_id)
    if not customer or customer.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: UUID,
    customer_in: CustomerUpdate,
    current_user: User = Depends(get_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a customer record."""
    repo = CustomerRepository(db)
    customer = await repo.get(customer_id)
    if not customer or customer.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    updated = await repo.update(customer_id, customer_in.model_dump(exclude_none=True))
    return updated


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: UUID,
    current_user: User = Depends(get_dispatcher_or_admin),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a customer."""
    repo = CustomerRepository(db)
    customer = await repo.get(customer_id)
    if not customer or customer.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    await repo.soft_delete(customer_id)
    return {"message": "Customer deleted successfully"}


@router.get("/{customer_id}/orders")
async def get_customer_orders(
    customer_id: UUID,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all orders for a specific customer."""
    from app.repositories.repositories import FreightOrderRepository
    from app.models import FreightOrder

    repo = CustomerRepository(db)
    customer = await repo.get(customer_id)
    if not customer or customer.company_id != current_user.company_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    order_repo = FreightOrderRepository(db)
    filters = [FreightOrder.customer_id == customer_id]
    total = await order_repo.count(filters=filters)
    items = await order_repo.get_all(skip=(page - 1) * size, limit=size, filters=filters)

    from app.schemas.dispatch import FreightOrderResponse
    return PaginatedResponse(
        items=[FreightOrderResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )
