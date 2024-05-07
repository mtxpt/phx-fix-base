from collections import deque
from datetime import datetime, timedelta
from typing import Tuple

from phx.fix_base.model.trade import Trade
from phx.fix_base.utils import TO_PIPS


class StreamingMovingAverageByCount(object):
    def __init__(self, window_size):
        self.window_size = window_size
        self.values = []
        self.sum = 0

    def append(self, value):
        self.values.append(value)
        self.sum += value
        if len(self.values) > self.window_size:
            self.sum -= self.values.pop(0)
        return float(self.sum) / len(self.values)


class StreamingMovingAverageByTime(object):
    def __init__(self, window_duration: timedelta):
        self.window_duration = window_duration
        self.values = deque()
        self.sum = 0

    def purge(self, timestamp=None):
        timestamp = timestamp or datetime.utcnow()
        threshold = timestamp - self.window_duration
        while len(self.values) > 0 and self.values[0][0] <= threshold:
            self.sum -= self.values[0][1]
            self.values.popleft()

    def append_without_purge(self, value, timestamp=None):
        timestamp = timestamp or datetime.utcnow()
        self.values.append((timestamp, value))
        self.sum += value
        return float(self.sum) / len(self.values)

    def append(self, value, timestamp=None):
        timestamp = timestamp or datetime.utcnow()
        self.values.append((timestamp, value))
        self.sum += value
        self.purge(timestamp)
        return float(self.sum) / len(self.values)


class BookStats(object):
    def __init__(self, window_duration):
        self.bid_vol_av = StreamingMovingAverageByTime(window_duration)
        self.ask_vol_av = StreamingMovingAverageByTime(window_duration)
        self.spread_av = StreamingMovingAverageByTime(window_duration)
        self.update_time_av = StreamingMovingAverageByTime(window_duration)
        self.update_time = None

    def update(
        self, timestamp: datetime, bid: Tuple[float, float], ask: Tuple[float, float]
    ):
        if self.update_time is not None:
            dt = (timestamp - self.update_time).total_seconds()
            self.update_time_av.append(dt, timestamp)
        self.bid_vol_av.append(bid[1], timestamp)
        self.ask_vol_av.append(ask[1], timestamp)
        mid = (ask[0] + bid[0]) / 2
        spread = (ask[0] - bid[0]) / mid * TO_PIPS
        self.spread_av.append(spread, timestamp)


class TradeStats(object):
    def __init__(self, window_duration):
        self.trade_quantity_price = StreamingMovingAverageByTime(window_duration)
        self.update_time_av = StreamingMovingAverageByTime(window_duration)
        self.update_time = None

    def update(self, timestamp: datetime, trade: Trade):
        if self.update_time is not None:
            dt = (timestamp - self.update_time).total_seconds()
            self.update_time_av.append(dt, timestamp)
        self.trade_quantity_price.append(trade.price, timestamp)