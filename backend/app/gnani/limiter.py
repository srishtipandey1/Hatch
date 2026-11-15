from __future__ import annotations

import asyncio
import heapq
import itertools
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass(order=True)
class _Waiter:
    priority: int
    sequence: int
    future: asyncio.Future[None] = field(compare=False)


class PriorityLimiter:
    LIVE = 0
    PREVIEW = 10
    SMOKE = 20

    def __init__(self, limit: int = 1) -> None:
        if limit < 1:
            raise ValueError("limit must be at least one")
        self._limit = limit
        self._active = 0
        self._waiters: list[_Waiter] = []
        self._sequence = itertools.count()
        self._lock = asyncio.Lock()

    async def acquire(self, priority: int = PREVIEW) -> None:
        async with self._lock:
            if self._active < self._limit and not self._waiters:
                self._active += 1
                return
            future = asyncio.get_running_loop().create_future()
            heapq.heappush(self._waiters, _Waiter(priority, next(self._sequence), future))
        try:
            await future
        except BaseException:
            async with self._lock:
                if future.done() and not future.cancelled():
                    self._release_locked()
                else:
                    future.cancel()
            raise

    async def release(self) -> None:
        async with self._lock:
            self._release_locked()

    def _release_locked(self) -> None:
        while self._waiters:
            waiter = heapq.heappop(self._waiters)
            if not waiter.future.cancelled():
                waiter.future.set_result(None)
                return
        self._active -= 1

    @asynccontextmanager
    async def slot(self, priority: int = PREVIEW) -> AsyncIterator[None]:
        await self.acquire(priority)
        try:
            yield
        finally:
            await self.release()
