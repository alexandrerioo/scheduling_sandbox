"""HTTP client for fetching production orders from a client's ERP API."""

import logging
import os
from datetime import datetime

import httpx

from src.models.schemas import MachineSlot, ProductionOrder

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = os.getenv("SCHEDULE_API_URL", "https://api.client-erp.example.com/v1")
DEFAULT_API_KEY = os.getenv("SCHEDULE_API_KEY", "")

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1.5
REQUEST_TIMEOUT = 30.0


class ScheduleClient:
    """Fetches production orders and machine availability from the client ERP system.

    Includes automatic retries with exponential back-off and bearer-token auth.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = DEFAULT_API_KEY,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=REQUEST_TIMEOUT,
        )

    def _request_with_retry(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Execute an HTTP request with exponential back-off retry logic."""
        import time

        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._client.request(method, path, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    wait = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "Request %s %s failed (attempt %d/%d): %s — retrying in %.1fs",
                        method,
                        path,
                        attempt,
                        self.max_retries,
                        exc,
                        wait,
                    )
                    time.sleep(wait)

        raise RuntimeError(
            f"Request {method} {path} failed after {self.max_retries} attempts"
        ) from last_exc

    def fetch_orders(self) -> list[ProductionOrder]:
        """Retrieve all pending production orders from the ERP system."""
        response = self._request_with_retry("GET", "/orders")
        payload = response.json()

        orders = [ProductionOrder(**item) for item in payload["orders"]]
        logger.info("Fetched %d production orders from ERP", len(orders))
        return orders

    def fetch_machine_slots(self) -> list[MachineSlot]:
        """Retrieve current machine availability windows."""
        response = self._request_with_retry("GET", "/machines/availability")
        payload = response.json()

        slots = [MachineSlot(**item) for item in payload["slots"]]
        logger.info("Fetched %d machine slots from ERP", len(slots))
        return slots

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
