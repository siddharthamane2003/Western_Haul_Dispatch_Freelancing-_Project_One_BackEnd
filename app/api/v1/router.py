from fastapi import APIRouter
from app.api.v1.endpoints import auth, customers, fleet, orders, dashboard, reports, uploads
from app.websockets.manager import router as ws_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(customers.router)
api_router.include_router(fleet.driver_router)
api_router.include_router(fleet.vehicle_router)
api_router.include_router(orders.order_router)
api_router.include_router(orders.dispatch_router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(uploads.router)
api_router.include_router(ws_router)
