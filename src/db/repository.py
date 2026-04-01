"""CSV-backed repository for persisting and querying schedule results.

Uses a simple CSV file as the storage backend — good enough for prototyping
and avoids the overhead of a full database setup.
"""

import csv
import os
from datetime import datetime
from pathlib import Path

from src.models.schemas import (
    Assignment,
    Conflict,
    MachineSlot,
    OrderPriority,
    OrderStatus,
    ProductionOrder,
    ScheduleResult,
)


CSV_HEADERS = [
    "schedule_id",
    "created_at",
    "order_id",
    "machine_id",
    "start_time",
    "end_time",
    "status",
    "conflict_reason",
]


class ScheduleRepository:
    """Reads and writes schedule results to a CSV file."""

    def __init__(self, csv_path: str = "data/schedules.csv") -> None:
        self.csv_path = Path(csv_path)
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Create the CSV file with headers if it does not exist."""
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
                writer.writeheader()

    def save(self, result: ScheduleResult) -> None:
        """Append a schedule result (assignments + conflicts) to the CSV."""
        rows: list[dict] = []

        for assignment in result.assignments:
            rows.append(
                {
                    "schedule_id": result.schedule_id,
                    "created_at": result.created_at.isoformat(),
                    "order_id": assignment.order_id,
                    "machine_id": assignment.machine_id,
                    "start_time": assignment.start_time.isoformat(),
                    "end_time": assignment.end_time.isoformat(),
                    "status": assignment.status.value,
                    "conflict_reason": "",
                }
            )

        for conflict in result.conflicts:
            rows.append(
                {
                    "schedule_id": result.schedule_id,
                    "created_at": result.created_at.isoformat(),
                    "order_id": conflict.order_id,
                    "machine_id": "",
                    "start_time": "",
                    "end_time": "",
                    "status": OrderStatus.FAILED.value,
                    "conflict_reason": conflict.reason,
                }
            )

        with open(self.csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writerows(rows)

    def get_by_id(self, schedule_id: str) -> ScheduleResult | None:
        """Load a schedule result by its ID. Returns None if not found."""
        assignments: list[Assignment] = []
        conflicts: list[Conflict] = []
        created_at: datetime | None = None

        with open(self.csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["schedule_id"] != schedule_id:
                    continue

                if created_at is None:
                    created_at = datetime.fromisoformat(row["created_at"])

                if row["conflict_reason"]:
                    conflicts.append(
                        Conflict(order_id=row["order_id"], reason=row["conflict_reason"])
                    )
                else:
                    assignments.append(
                        Assignment(
                            order_id=row["order_id"],
                            machine_id=row["machine_id"],
                            start_time=datetime.fromisoformat(row["start_time"]),
                            end_time=datetime.fromisoformat(row["end_time"]),
                            status=OrderStatus(row["status"]),
                        )
                    )

        if created_at is None:
            return None

        return ScheduleResult(
            schedule_id=schedule_id,
            created_at=created_at,
            assignments=assignments,
            conflicts=conflicts,
            total_orders=len(assignments) + len(conflicts),
            scheduled_count=len(assignments),
            conflict_count=len(conflicts),
        )

    def list_schedule_ids(self) -> list[str]:
        """Return all distinct schedule IDs stored in the CSV."""
        seen: set[str] = set()
        ids: list[str] = []

        with open(self.csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sid = row["schedule_id"]
                if sid not in seen:
                    seen.add(sid)
                    ids.append(sid)

        return ids


class OrderRepository:
    """Reads production orders from a CSV file."""

    def __init__(self, csv_path: str = "data/orders.csv") -> None:
        self.csv_path = Path(csv_path)

    def list_all(self) -> list[ProductionOrder]:
        """Load every order in the CSV."""
        orders: list[ProductionOrder] = []

        with open(self.csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                orders.append(
                    ProductionOrder(
                        order_id=row["order_id"],
                        product_name=row["product_name"],
                        quantity=int(row["quantity"]),
                        deadline=datetime.fromisoformat(row["deadline"]),
                        priority=OrderPriority(row["priority"]),
                        estimated_hours=float(row["estimated_hours"]),
                        required_machine_type=row["required_machine_type"],
                    )
                )

        return orders

    def get_by_id(self, order_id: str) -> ProductionOrder | None:
        """Look up a single order by its ID."""
        for order in self.list_all():
            if order.order_id == order_id:
                return order
        return None


class MachineRepository:
    """Reads machine slot availability from a CSV file."""

    def __init__(self, csv_path: str = "data/machines.csv") -> None:
        self.csv_path = Path(csv_path)

    def list_all(self) -> list[MachineSlot]:
        """Load every machine slot in the CSV."""
        slots: list[MachineSlot] = []

        with open(self.csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                slots.append(
                    MachineSlot(
                        machine_id=row["machine_id"],
                        machine_type=row["machine_type"],
                        available_from=datetime.fromisoformat(row["available_from"]),
                        available_until=datetime.fromisoformat(row["available_until"]),
                        capacity_hours=float(row["capacity_hours"]),
                    )
                )

        return slots
