"""
feed_store.py
─────────────
Shared in-memory event bus for the real-time intelligence feed.

Usage:
  from app.feed_store import publish_event, get_recent_events, subscribe, unsubscribe

Every admin document upload emits an event here.
SSE clients subscribe with an asyncio.Queue and get events pushed instantly.
"""
import asyncio
import time
from collections import deque
from datetime import datetime
from typing import Set

# Last 50 events kept in memory (survives new SSE connections)
_event_log: deque = deque(maxlen=50)

# One asyncio.Queue per connected SSE client
_subscribers: Set[asyncio.Queue] = set()


# ── Public API ────────────────────────────────────────────────────────────────

def get_recent_events(n: int = 10) -> list:
    """Return the n most-recent events, newest first."""
    return list(reversed(list(_event_log)))[:n]


def make_event(text: str, event_type: str, filename: str = "", category: str = "") -> dict:
    now = datetime.now()
    return {
        "id": f"live_{int(time.time() * 1000)}",
        "text": text,
        "type": event_type,          # INDEX | ALERT | UPDATE | ANALYSIS | NODE
        "time": now.strftime("%H:%M:%S"),
        "timestamp": time.time(),
        "filename": filename,
        "category": category,
        "source": "live",            # lets frontend distinguish real vs synthetic
    }


async def publish_event(event: dict) -> None:
    """Add event to log and push to all connected SSE clients."""
    _event_log.append(event)
    dead = set()
    for q in list(_subscribers):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            dead.add(q)
    _subscribers.difference_update(dead)


def publish_event_sync(event: dict) -> None:
    """
    Thread-safe synchronous wrapper — use from non-async contexts.
    Schedules publish_event on the running event loop if available.
    """
    _event_log.append(event)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(publish_event(event))
            )
    except RuntimeError:
        pass  # No event loop — just store in log, no push needed


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    _subscribers.discard(q)
