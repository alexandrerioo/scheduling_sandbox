"""Core scheduling engine — assigns production orders to machine slots.

Uses a greedy earliest-deadline-first (EDF) algorithm:
  1. Sort orders by deadline (earliest first), breaking ties by priority.
  2. For each order, find the best compatible machine slot (earliest available
     slot that has enough capacity and matches the required machine type).
  3. Assign the order to that slot, consuming capacity.
  4. If no compatible slot exists, record a scheduling conflict.
"""

import uuid
from datetime import datetime, timedelta

from src.models.schemas import (
    Assignment,
    Conflict,
    MachineSlot,
    OrderPriority,
    OrderStatus,
    ProductionOrder,
    ScheduleResult,
)

PRIORITY_WEIGHT: dict[OrderPriority, int] = {
    OrderPriority.CRITICAL: 0,
    OrderPriority.HIGH: 1,
    OrderPriority.MEDIUM: 2,
    OrderPriority.LOW: 3,
}


class ProductionScheduler:
    """Greedy earliest-deadline-first production scheduler.

    Accepts a list of production orders and a pool of machine slots, then
    produces a `ScheduleResult` containing assignments and conflicts.
    """

    def __init__(self, orders: list[ProductionOrder], slots: list[MachineSlot]) -> None:
        self.orders = orders
        self.slots = slots

    def _sort_orders(self) -> list[ProductionOrder]:
        """Sort orders by deadline ASC, then by priority weight ASC (critical first)."""
        return sorted(
            self.orders,
            key=lambda o: (o.deadline, PRIORITY_WEIGHT.get(o.priority, 2)),
        )

    def _find_best_slot(self, order: ProductionOrder) -> MachineSlot | None:
        """Return the earliest compatible slot with enough remaining capacity.

        A slot is compatible when:
        - Its machine_type matches the order's required_machine_type.
        - It has at least `order.estimated_hours` of remaining capacity.
        - The order can finish before its deadline within this slot.
        """
        compatible = [
            s
            for s in self.slots
            if s.machine_type == order.required_machine_type
            and s.capacity_hours >= order.estimated_hours
        ]

        compatible.sort(key=lambda s: s.available_from)

        for slot in compatible:
            finish_time = slot.available_from + timedelta(hours=order.estimated_hours)
            if finish_time <= order.deadline and finish_time <= slot.available_until:
                return slot

        return None

    def _consume_slot_capacity(self, slot: MachineSlot, hours: float) -> None:
        """Shrink the slot's available window after assigning work to it."""
        slot.available_from = slot.available_from + timedelta(hours=hours)
        slot.capacity_hours -= hours

    def optimize(self) -> ScheduleResult:
        """Run the scheduling algorithm and return the result."""
        schedule_id = str(uuid.uuid4())
        assignments: list[Assignment] = []
        conflicts: list[Conflict] = []

        sorted_orders = self._sort_orders()

        for order in sorted_orders:
            best_slot = self._find_best_slot(order)

            if best_slot is None:
                conflicts.append(
                    Conflict(
                        order_id=order.order_id,
                        reason=(
                            f"No available {order.required_machine_type} slot with "
                            f"{order.estimated_hours}h capacity before deadline "
                            f"{order.deadline.isoformat()}"
                        ),
                    )
                )
                continue

            start_time = best_slot.available_from
            end_time = start_time + timedelta(hours=order.estimated_hours)

            assignments.append(
                Assignment(
                    order_id=order.order_id,
                    machine_id=best_slot.machine_id,
                    start_time=start_time,
                    end_time=end_time,
                    status=OrderStatus.SCHEDULED,
                )
            )

            self._consume_slot_capacity(best_slot, order.estimated_hours)

        return ScheduleResult(
            schedule_id=schedule_id,
            assignments=assignments,
            conflicts=conflicts,
            total_orders=len(sorted_orders),
            scheduled_count=len(assignments),
            conflict_count=len(conflicts),
        )
