"""Read cancellation keys without letting Nuclei consume the terminal input."""

from __future__ import annotations

import asyncio
import sys
from contextlib import ExitStack


class ScanCancelled(Exception):
    """The user cancelled an active child process; partial output may exist."""


async def cancellable_scan(operation, *, cancel_event: asyncio.Event | None = None):
    event = cancel_event or asyncio.Event()
    with ExitStack() as stack:
        if cancel_event is None and sys.stdin.isatty():
            from prompt_toolkit.input import create_input
            from prompt_toolkit.keys import Keys

            terminal = create_input()
            stack.callback(terminal.close)
            loop = asyncio.get_running_loop()
            flush = None

            def process_keys(keys):
                for key in keys:
                    if key.key in {Keys.Escape, Keys.ControlC}:
                        event.set()

            def keys_ready():
                nonlocal flush
                process_keys(terminal.read_keys())
                if flush is not None:
                    flush.cancel()
                flush = loop.call_later(0.15, lambda: process_keys(terminal.flush_keys()))

            stack.callback(lambda: flush.cancel() if flush is not None else None)

            stack.enter_context(terminal.raw_mode())
            stack.enter_context(terminal.attach(keys_ready))
        task = asyncio.create_task(operation)
        stopping = asyncio.create_task(event.wait())
        try:
            done, _ = await asyncio.wait({task, stopping}, return_when=asyncio.FIRST_COMPLETED)
            if task in done:
                return await task
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise ScanCancelled("User cancelled the scan")
        finally:
            for pending in (task, stopping):
                if not pending.done():
                    pending.cancel()
            await asyncio.gather(task, stopping, return_exceptions=True)
