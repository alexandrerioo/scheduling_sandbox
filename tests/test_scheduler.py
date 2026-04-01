"""Unit tests for the ProductionScheduler."""

from datetime import datetime, timedelta

import pytest

from src.models.schemas import MachineSlot, OrderPriority, ProductionOrder
from src.optimization.scheduler import ProductionScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 1, 8, 0, 0)


def _make_order(
    order_id: str = "ORD-001",
    hours: float = 2.0,
    deadline_offset_h: float = 10.0,
    machine_type: str = "CNC",
    priority: OrderPriority = OrderPriority.MEDIUM,
) -> ProductionOrder:
    return ProductionOrder(
        order_id=order_id,
        product_name="Widget",
        quantity=100,
        deadline=NOW + timedelta(hours=deadline_offset_h),
        priority=priority,
        estimated_hours=hours,
        required_machine_type=machine_type,
    )


def _make_slot(
    machine_id: str = "M-01",
    machine_type: str = "CNC",
    capacity_hours: float = 8.0,
    start_offset_h: float = 0.0,
) -> MachineSlot:
    return MachineSlot(
        machine_id=machine_id,
        machine_type=machine_type,
        available_from=NOW + timedelta(hours=start_offset_h),
        available_until=NOW + timedelta(hours=start_offset_h + capacity_hours),
        capacity_hours=capacity_hours,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProductionScheduler:
    """Tests for the greedy EDF scheduler."""

    def test_single_order_assigned_successfully(self):
        """A single order that fits into one slot should be scheduled."""
        orders = [_make_order()]
        slots = [_make_slot()]

        result = ProductionScheduler(orders, slots).optimize()

        assert result.scheduled_count == 1
        assert result.conflict_count == 0
        assert result.assignments[0].order_id == "ORD-001"
        assert result.assignments[0].machine_id == "M-01"

    def test_order_with_no_compatible_slot_becomes_conflict(self):
        """An order requiring a machine type with no available slot should conflict."""
        orders = [_make_order(machine_type="assembly")]
        slots = [_make_slot(machine_type="CNC")]

        result = ProductionScheduler(orders, slots).optimize()

        assert result.scheduled_count == 0
        assert result.conflict_count == 1
        assert "assembly" in result.conflicts[0].reason

    def test_priority_breaks_deadline_tie(self):
        """When two orders share the same deadline, higher priority wins the slot."""
        shared_deadline = 6.0
        orders = [
            _make_order(order_id="LOW", priority=OrderPriority.LOW, deadline_offset_h=shared_deadline, hours=4.0),
            _make_order(order_id="CRIT", priority=OrderPriority.CRITICAL, deadline_offset_h=shared_deadline, hours=4.0),
        ]
        slots = [_make_slot(capacity_hours=4.0)]

        result = ProductionScheduler(orders, slots).optimize()

        assert result.scheduled_count == 1
        assert result.conflict_count == 1
        assert result.assignments[0].order_id == "CRIT"

    def test_multiple_orders_fill_slot_capacity(self):
        """Orders should be packed into a slot until capacity is exhausted."""
        orders = [
            _make_order(order_id="A", hours=3.0, deadline_offset_h=10.0),
            _make_order(order_id="B", hours=3.0, deadline_offset_h=12.0),
            _make_order(order_id="C", hours=3.0, deadline_offset_h=14.0),
        ]
        slots = [_make_slot(capacity_hours=8.0)]

        result = ProductionScheduler(orders, slots).optimize()

        assert result.scheduled_count == 2
        assert result.conflict_count == 1
        scheduled_ids = {a.order_id for a in result.assignments}
        assert scheduled_ids == {"A", "B"}
