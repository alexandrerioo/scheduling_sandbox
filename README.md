# Oplit Production Scheduling Service

A lightweight backend service that ingests production orders from a client ERP system, runs a greedy optimization algorithm to assign orders to machine slots, and exposes the results through a REST API.

Built as a technical interview exercise for the **Forward Deployed Engineer** position at Oplit.

---

## Factory context

The client is **MetalWorks GmbH**, a mid-sized precision parts manufacturer based in Stuttgart. The factory produces metal components (housings, shafts, brackets, connectors) for automotive and industrial equipment customers.

### Shop floor layout

The factory operates **two production lines** with a total of **5 machines**:

| Machine ID | Type | Line | Description | Shift capacity |
|---|---|---|---|---|
| `CNC-01` | `CNC` | Machining | 5-axis CNC milling center — primary | 10 h/day |
| `CNC-02` | `CNC` | Machining | 3-axis CNC lathe — secondary | 10 h/day |
| `CNC-03` | `CNC` | Machining | 3-axis CNC lathe — overflow | 8 h/day |
| `ASM-01` | `assembly` | Assembly | Manual + semi-auto assembly station | 8 h/day |
| `ASM-02` | `assembly` | Assembly | Manual assembly station — small parts | 6 h/day |

Machines run a **single day shift** (06:00 – 18:00) with maintenance windows reducing usable capacity. CNC machines handle milling, turning, and boring operations. Assembly stations handle final part assembly, press-fitting, and quality checks.

### Production orders

Orders come from the client's SAP-based ERP system. Each order represents a batch of identical parts to manufacture.

| Field | Description | Example |
|---|---|---|
| `order_id` | ERP reference (format `ORD-XXXX`) | `ORD-1001` |
| `product_name` | Part being produced | `"Aluminum Housing Type-B"` |
| `quantity` | Number of units in the batch | `500` |
| `deadline` | Customer-committed delivery date/time | `2026-03-29T18:00:00` |
| `priority` | `low`, `medium`, `high`, or `critical` | `high` |
| `estimated_hours` | Machine-hours needed for the full batch | `3.5` |
| `required_machine_type` | `CNC` or `assembly` | `CNC` |

Typical daily volume is **4–8 orders** across both machine types. Peak weeks (automotive model changes) can reach 12+ orders/day.

### Optimization algorithm

The scheduler uses a **greedy earliest-deadline-first (EDF)** strategy:

1. Sort all orders by deadline (ascending), breaking ties by priority (critical > high > medium > low).
2. For each order, find the earliest compatible machine slot that has enough remaining capacity and can finish before the deadline.
3. Assign the order and consume that slot's capacity.
4. If no slot fits, record a **conflict** with the reason (no capacity, deadline miss, wrong machine type).

This is intentionally simple — a real deployment would use constraint programming or mixed-integer linear programming.

---

## Database

The storage layer uses **3 CSV files** in the `data/` directory — no database server needed, and every record is human-readable and easy to inspect.

### `data/orders.csv` — Production orders

The source of truth for all incoming work. Contains **18 orders** spanning 3 production days (2026-03-29 to 2026-03-31), covering 6 product families:

| Product | Machine type | Typical batch | Hours range |
|---|---|---|---|
| Aluminum Housing (Type-A/B/C) | CNC | 400–600 units | 3.0–4.0 h |
| Steel Shaft (S-100/S-200/S-300) | CNC | 250–350 units | 2.0–4.0 h |
| Precision Connector Ring | CNC | 450–900 units | 3.0–4.0 h |
| Titanium Valve Block | CNC | 150–200 units | 5.5–6.0 h |
| Bracket Assembly Kit | assembly | 1000–1500 units | 4.5–5.0 h |
| Motor Mount / Wiring Harness Sub-Assy | assembly | 550–800 units | 2.0–4.0 h |

**Schema:** `order_id, product_name, quantity, deadline, priority, estimated_hours, required_machine_type`

### `data/machines.csv` — Machine slot availability

Defines the daily capacity windows for all 5 machines across 3 days — **15 slots** total.

| Machine | Type | Shift window | Capacity |
|---|---|---|---|
| CNC-01 | CNC | 06:00–16:00 | 10 h |
| CNC-02 | CNC | 06:00–16:00 | 10 h |
| CNC-03 | CNC | 07:00–15:00 | 8 h |
| ASM-01 | assembly | 06:00–14:00 | 8 h |
| ASM-02 | assembly | 08:00–14:00 | 6 h |

Total daily capacity: **28 h CNC** + **14 h assembly** = **42 machine-hours/day**.

**Schema:** `machine_id, machine_type, available_from, available_until, capacity_hours`

### `data/schedules.csv` — Optimization results

Stores the output of each scheduling run. Each row is either an **assignment** (order placed on a machine) or a **conflict** (order that could not be placed). Rows sharing the same `schedule_id` belong to the same run.

| Column | Type | Description |
|---|---|---|
| `schedule_id` | UUID string | Groups all rows belonging to one optimization run |
| `created_at` | ISO 8601 datetime | When the optimization was executed |
| `order_id` | string | ERP order reference |
| `machine_id` | string | Assigned machine (empty for conflicts) |
| `start_time` | ISO 8601 datetime | Scheduled start (empty for conflicts) |
| `end_time` | ISO 8601 datetime | Scheduled end (empty for conflicts) |
| `status` | `scheduled` or `failed` | Whether the order was assigned or conflicted |
| `conflict_reason` | string | Human-readable reason (empty for assignments) |

### Seed data

The repository ships with two pre-computed schedule runs in `schedules.csv`:

- **Schedule 1** (`a1b2c3d4-...0001`) — 2026-03-28: 5 orders assigned across `CNC-01`, `CNC-02`, `ASM-01`; 1 conflict (CNC capacity exceeded before deadline).
- **Schedule 2** (`b2c3d4e5-...0002`) — 2026-03-29: 5 orders assigned; 1 conflict (no assembly slot available in time).

New optimization runs (`POST /schedule/optimize`) append to `schedules.csv`.

---

## Architecture

```
Client ERP API  ──►  ScheduleClient (ingestion)
                          │
                          ▼
                   ProductionScheduler (optimization)
                          │
                          ▼
                   ScheduleRepository (CSV storage)
                          │
                          ▼
                   FastAPI endpoints (api)
```

### Key components

| Module | Purpose |
|---|---|
| `src/models/schemas.py` | Pydantic models — `ProductionOrder`, `MachineSlot`, `ScheduleResult`, etc. |
| `src/ingestion/client.py` | HTTP client with retry logic for fetching orders from the ERP API |
| `src/optimization/scheduler.py` | Greedy earliest-deadline-first scheduling algorithm |
| `src/db/repository.py` | CSV-backed persistence — `OrderRepository`, `MachineRepository`, `ScheduleRepository` |
| `src/api/routes.py` | FastAPI router — `/health`, `/orders`, `/machines`, `/schedule/optimize`, `/schedule/optimize-all`, `/schedule/{id}` |

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

## Getting started

```bash
# Install dependencies
make dev

# Start the server (http://localhost:8000)
make run

# Run tests
make test

# Lint
make lint
```

## API endpoints

### `GET /health`

Returns service health status.

### `GET /orders`

List all production orders from the database.

### `GET /orders/{order_id}`

Look up a single order by its ID.

**Example:** `GET /orders/ORD-1001`

### `GET /machines`

List all machine slots and their availability windows.

### `POST /schedule/optimize-all`

Schedule **all** orders from the database onto all available machines in a single call. No request body needed.

```bash
curl -X POST http://localhost:8000/schedule/optimize-all
```

This reads `data/orders.csv` and `data/machines.csv`, runs the EDF optimizer, persists the result to `data/schedules.csv`, and returns the full schedule with assignments and conflicts.

### `POST /schedule/optimize`

Schedule a **custom** set of orders and machine slots (passed in the request body). Useful for running what-if scenarios without modifying the CSV files.

**Request body:**

```json
{
  "orders": [
    {
      "order_id": "ORD-3001",
      "product_name": "Aluminum Housing Type-C",
      "quantity": 600,
      "deadline": "2026-03-31T18:00:00",
      "priority": "high",
      "estimated_hours": 4.0,
      "required_machine_type": "CNC"
    }
  ],
  "machine_slots": [
    {
      "machine_id": "CNC-01",
      "machine_type": "CNC",
      "available_from": "2026-03-31T06:00:00",
      "available_until": "2026-03-31T16:00:00",
      "capacity_hours": 10.0
    }
  ]
}
```

### `GET /schedule/{schedule_id}`

Retrieve a previously computed schedule by its ID.

**Example:** `GET /schedule/a1b2c3d4-0001-4000-8000-000000000001`

## Configuration

Environment variables (see `.env`):

| Variable | Description | Default |
|---|---|---|
| `SCHEDULE_API_URL` | Base URL of the client ERP API | `https://api.client-erp.example.com/v1` |
| `SCHEDULE_API_KEY` | Bearer token for ERP authentication | — |
| `CSV_DB_PATH` | Path to the schedule results CSV | `data/schedules.csv` |
| `ORDERS_CSV_PATH` | Path to the orders CSV | `data/orders.csv` |
| `MACHINES_CSV_PATH` | Path to the machine slots CSV | `data/machines.csv` |
