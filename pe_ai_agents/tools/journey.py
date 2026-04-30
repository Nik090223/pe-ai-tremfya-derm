"""Patient-journey adapter -- reads ``events_patient_journey_<brand>``.

Real adapter delegates to ``database_utility`` + the canonical view.
The harness ``FakeJourneyLog`` synthesises a small deterministic event
log so Cohort Builder, EDA, and Quick Analyst agents can run end-to-end
with no infrastructure.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class JourneyEvent:
    patient_id: str
    event_type: str
    event_date: str  # ISO date string (YYYY-MM-DD)
    indication: str


class FakeJourneyLog:
    """Deterministic synthetic event log keyed on a seed."""

    EVENT_TYPES = ("referral", "shipment", "hub_call", "fulfillment", "discontinuation")

    def __init__(self, *, n_patients: int = 200, seed: int = 7) -> None:
        self._n = n_patients
        self._seed = seed

    def load(self, *, brand: str, indication: str) -> list[JourneyEvent]:
        rng = random.Random(self._seed)
        events: list[JourneyEvent] = []
        for i in range(self._n):
            pid = f"{brand[:3].upper()}-{i:05d}"
            n_events = rng.randint(2, 6)
            for _ in range(n_events):
                day = rng.randint(1, 365)
                events.append(
                    JourneyEvent(
                        patient_id=pid,
                        event_type=rng.choice(self.EVENT_TYPES),
                        event_date=f"2026-{(day % 12) + 1:02d}-{(day % 28) + 1:02d}",
                        indication=indication,
                    )
                )
        return events
