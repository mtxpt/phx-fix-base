from collections import deque
from datetime import datetime, timedelta
from typing import List, Tuple, Union

import pandas as pd
import numpy as np


class Limiter:
    def __init__(self, limit: int, period: Union[str, timedelta]):
        self.limit = limit
        self.period = period if isinstance(period, timedelta) else pd.Timedelta(period).to_pytimedelta()
        self.queue = deque()

    def purge(self, cutoff):
        while len(self.queue) > 0 and self.queue[0] <= cutoff:
            self.queue.popleft()

    def check_limit(self, timestamp: datetime) -> bool:
        self.purge(timestamp - self.period)
        return len(self.queue) < self.limit

    def has_capacity(self, timestamp: datetime, count: int) -> bool:
        return self.free_capacity(timestamp) >= count

    def free_capacity(self, timestamp: datetime) -> int:
        self.purge(timestamp - self.period)
        return max(self.limit - len(self.queue), 0)

    def consume(self, timestamp: datetime, count: int = None):
        if count is None or count == 1:
            self.queue.append(timestamp)
        else:
            assert count > 0
            self.queue.extend([timestamp]*count)


class MultiPeriodLimiter:
    def __init__(self, limits: List[Tuple[int, Union[str, timedelta]]]):
        self.limiters = [Limiter(limit, period) for limit, period in limits]

    def check_limit(self, timestamp: datetime) -> bool:
        return all([limiter.check_limit(timestamp) for limiter in self.limiters])

    def has_capacity(self, timestamp: datetime, count: int) -> bool:
        return self.free_capacity(timestamp) >= count

    def free_capacity(self, timestamp: datetime) -> int:
        capacities = [limiter.free_capacity(timestamp) for limiter in self.limiters]
        return np.min(capacities)

    def consume(self, timestamp: datetime, count: int = None):
        for limiter in self.limiters:
            limiter.consume(timestamp, count)
