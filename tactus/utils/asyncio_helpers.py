"""
Asyncio helper utilities.

These helpers protect synchronous codepaths from inheriting a closed event loop.
"""

from __future__ import annotations

import asyncio


def clear_closed_event_loop() -> None:
    """
    Ensure the current thread does not hold a closed event loop.

    Pytest-asyncio and other frameworks can leave a closed loop set as the
    current event loop after async tests complete. Synchronous code that uses
    asyncio.run() or creates its own event loop should not inherit a closed
    loop reference. This helper resets the current loop to None when needed.
    """
    try:
        current_loop = asyncio.get_event_loop()
    except RuntimeError:
        return

    if getattr(current_loop, "is_closed", lambda: False)():
        asyncio.set_event_loop(None)
