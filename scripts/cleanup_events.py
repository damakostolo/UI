#!/usr/bin/env python3
"""Delete expired interaction events according to the local prototype TTL."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import InteractionEvent, SessionLocal  # noqa: E402


def main():
    days = max(1, int(os.getenv("EVENT_TTL_DAYS", "30")))
    with SessionLocal() as db:
        result = db.execute(delete(InteractionEvent).where(InteractionEvent.occurred_at < datetime.now(timezone.utc) - timedelta(days=days)))
        db.commit()
    print(f"Expired interaction events deleted: {result.rowcount}")


if __name__ == "__main__": main()
