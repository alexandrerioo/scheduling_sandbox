"""Pydantic models for production scheduling domain objects."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class OrderPriority(StrEnum):
    """Priority levels for production orders."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OrderStatus(StrEnum):
    """Lifecycle status of a production order."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ProductionOrder(BaseModel):
    """A single production order ingested from the client ERP system."""

    order_id: str = Field(..., description="Unique identifier from the ERP system")
    product_name: str = Field(..., description="Name of the product to manufacture")
    quantity: int = Field(..., gt=0, description="Number of units to produce")
    deadline: datetime = Field(..., description="Latest acceptable completion time")
    priority: OrderPriority = Field(default=OrderPriority.MEDIUM)
    estimated_hours: float = Field(..., gt=0, description="Estimated machine-hours to complete")
    required_machine_type: str = Field(..., description="Machine type needed (e.g. 'CNC', 'assembly')")


class MachineSlot(BaseModel):
    """An available time slot on a specific machine."""

    machine_id: str = Field(..., description="Unique machine identifier")
    machine_type: str = Field(..., description="Category of machine (e.g. 'CNC', 'assembly')")
    available_from: datetime
    available_until: datetime
    capacity_hours: float = Field(..., gt=0, description="Usable hours in this slot")


class Assignment(BaseModel):
    """A single order-to-machine assignment produced by the scheduler."""

    order_id: str
    machine_id: str
    start_time: datetime
    end_time: datetime
    status: OrderStatus = OrderStatus.SCHEDULED


class Conflict(BaseModel):
    """Describes why an order could not be scheduled."""

    order_id: str
    reason: str


class ScheduleResult(BaseModel):
    """Complete output of an optimization run."""

    schedule_id: str = Field(..., description="Unique identifier for this schedule run")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    assignments: list[Assignment] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    total_orders: int = 0
    scheduled_count: int = 0
    conflict_count: int = 0


class APIResponse(BaseModel):
    """Standard wrapper for all API responses."""

    success: bool
    data: dict | list | None = None
    error: str | None = None
