#    Mutiny - Unofficial Midjourney integration SDK
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Utilities for managing the asyncio event loop within a Tkinter threaded environment.
"""

import asyncio
import threading
from typing import Any, Callable, Coroutine, Optional, TypeVar

T = TypeVar("T")


class AsyncTaskHandler:
    """Runs the asyncio loop in a background thread."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.running = False

    def start(self) -> None:
        self.running = True
        self.thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self) -> None:
        if self.running:
            try:
                future = asyncio.run_coroutine_threadsafe(self._shutdown_loop(), self.loop)
                future.result(timeout=3.0)
            except Exception as e:
                print(f"Error during loop shutdown: {e}")

            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=1.0)
            self.running = False

    async def _shutdown_loop(self) -> None:
        tasks = [t for t in asyncio.all_tasks(self.loop) if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def run_coro(
        self,
        coro: Coroutine[Any, Any, T],
        callback: Optional[Callable[[Optional[T], Optional[Exception]], None]] = None,
    ) -> asyncio.Future[Any]:
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        if callback:

            def done_callback(fut: asyncio.Future[Any]) -> None:
                try:
                    res = fut.result()
                    callback(res, None)
                except Exception as e:
                    callback(None, e)

            future.add_done_callback(done_callback)
        return future
