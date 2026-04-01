"""FastAPI router — exposes scheduling endpoints."""

import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.db.repository import MachineRepository, OrderRepository, ScheduleRepository
from src.models.schemas import (
    APIResponse,
    MachineSlot,
    ProductionOrder,
    ScheduleResult,
)
from src.optimization.scheduler import ProductionScheduler

logger = logging.getLogger(__name__)

router = APIRouter()

CSV_DB_PATH = os.getenv("CSV_DB_PATH", "data/schedules.csv")
ORDERS_CSV_PATH = os.getenv("ORDERS_CSV_PATH", "data/orders.csv")
MACHINES_CSV_PATH = os.getenv("MACHINES_CSV_PATH", "data/machines.csv")


def _get_schedule_repo() -> ScheduleRepository:
    return ScheduleRepository(csv_path=CSV_DB_PATH)


def _get_order_repo() -> OrderRepository:
    return OrderRepository(csv_path=ORDERS_CSV_PATH)


def _get_machine_repo() -> MachineRepository:
    return MachineRepository(csv_path=MACHINES_CSV_PATH)


def _run_optimizer(orders: list[ProductionOrder], slots: list[MachineSlot]) -> ScheduleResult:
    """Run the scheduler, persist the result, and return it."""
    result = ProductionScheduler(orders, slots).optimize()
    _get_schedule_repo().save(result)
    logger.info(
        "Schedule %s: %d assigned, %d conflicts",
        result.schedule_id,
        result.scheduled_count,
        result.conflict_count,
    )
    return result


# ---------------------------------------------------------------------------
# Data endpoints
# ---------------------------------------------------------------------------


@router.get("/health")
def health_check() -> APIResponse:
    """Liveness probe."""
    return APIResponse(success=True, data={"status": "healthy"})


@router.get("/orders")
def list_orders() -> APIResponse:
    """Return all production orders from the database."""
    orders = _get_order_repo().list_all()
    return APIResponse(success=True, data=[o.model_dump(mode="json") for o in orders])


@router.get("/orders/{order_id}")
def get_order(order_id: str) -> APIResponse:
    """Look up a single order by ID."""
    order = _get_order_repo().get_by_id(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return APIResponse(success=True, data=order.model_dump(mode="json"))


@router.get("/machines")
def list_machines() -> APIResponse:
    """Return all machine slots from the database."""
    slots = _get_machine_repo().list_all()
    return APIResponse(success=True, data=[s.model_dump(mode="json") for s in slots])


# ---------------------------------------------------------------------------
# Schedule optimization
# ---------------------------------------------------------------------------


class OptimizePayload(BaseModel):
    """POST body for /schedule/optimize."""

    orders: list[ProductionOrder]
    machine_slots: list[MachineSlot]


@router.post("/schedule/optimize")
def optimize_schedule(payload: OptimizePayload) -> APIResponse:
    """Run the scheduler on a custom set of orders and machine slots."""
    result = _run_optimizer(payload.orders, payload.machine_slots)
    return APIResponse(success=True, data=result.model_dump(mode="json"))


@router.post("/schedule/optimize-all")
def optimize_all() -> APIResponse:
    """Read all orders and machines from the CSV database and schedule them."""
    orders = _get_order_repo().list_all()
    slots = _get_machine_repo().list_all()
    result = _run_optimizer(orders, slots)
    return APIResponse(success=True, data=result.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Retrieve past schedules
# ---------------------------------------------------------------------------


@router.get("/schedule/{schedule_id}")
def get_schedule(schedule_id: str) -> APIResponse:
    """Look up a previously computed schedule by ID."""
    result = _get_schedule_repo().get_by_id(schedule_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    return APIResponse(success=True, data=result.model_dump(mode="json"))
