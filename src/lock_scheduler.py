"""
lock_scheduler.py
=================
Background asyncio daemon that expires LOCKED bookings after 24 hours.
Runs as an asyncio task inside app.py's event loop — no separate process needed.
"""
from __future__ import annotations

import asyncio

from src.database import expire_stale_locks

_CHECK_INTERVAL_SECONDS = 60  # poll every minute


async def lock_expiry_daemon() -> None:
    """
    Infinite loop that checks for expired locks every 60 seconds.
    Call via asyncio.create_task(lock_expiry_daemon()) inside a startup handler.
    """
    print("[LockScheduler] 24-hour lock expiry daemon started.", flush=True)
    while True:
        try:
            expired_count = expire_stale_locks()
            if expired_count > 0:
                print(
                    f"[LockScheduler] Released {expired_count} expired lock(s) back to inventory.",
                    flush=True,
                )
        except Exception as exc:
            print(f"[LockScheduler] Error during expiry sweep: {exc}", flush=True)

        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
