import numpy as np
import numpy.typing as npt
from sortedcontainers import SortedDict
from typing import Optional, Tuple, List
from tabulate import tabulate

from phx.fix.model.message import Message


def price_impact(prices: npt.ArrayLike, cum_vols: npt.ArrayLike,
                 impact_volumes: List) -> Tuple[List[float], List[float]]:
    max_vol = cum_vols[-1]
    impact_prices = [
        prices[np.searchsorted(cum_vols, v, side="right"), 0] if np.isfinite(v) and v < max_vol else np.nan for v in
        impact_volumes
    ]
    ref_price = prices[0, 0]
    impact_pips = [
        abs(ref_price - p) / ref_price * 10000 if not np.isnan(p) else np.nan for p in impact_prices
    ]
    return impact_prices, impact_pips


class TopOfBook(Message):
    __slots__ = "bid_price", "bid_volume", "ask_price", "ask_volume"

    def __init__(self, bid_price, bid_volume, ask_price, ask_volume):
        Message.__init__(self)
        self.bid_price = bid_price
        self.bid_volume = bid_volume
        self.ask_price = ask_price
        self.ask_volume = ask_volume

    def __str__(self):
        return (f"TopOfBook["
                f"bid_price={self.bid_price}, "
                f"bid_volume={self.bid_volume}, "
                f"ask_price={self.ask_price}, "
                f"ask_volume={self.ask_volume}"
                f"]")


class OrderBookSnapshot(Message):

    def __init__(self, exchange, symbol, exchange_ts, local_ts, bids, asks):
        Message.__init__(self)
        self.exchange = exchange
        self.symbol = symbol
        self.exchange_ts = exchange_ts
        self.local_ts = local_ts
        self.bids = bids
        self.asks = asks

    def key(self) -> Tuple[str, str]:
        return self.exchange, self.symbol

    def __str__(self) -> str:
        return (
            f"OrderBookSnapshot["
            f"exchange={self.exchange}, "
            f"symbol={self.symbol}, "
            f"exchange_ts={self.exchange_ts}, "
            f"local_ts={self.local_ts}, "
            f"bids={self.bids}, "
            f"asks={self.asks}"
            f"]"
        )


class OrderBookUpdate(Message):

    def __init__(self, exchange, symbol, exchange_ts, local_ts, updates: List[Tuple[float, float, bool]] = []):
        Message.__init__(self)
        self.exchange = exchange
        self.symbol = symbol
        self.exchange_ts = exchange_ts
        self.local_ts = local_ts
        self.updates = updates

    def key(self) -> Tuple[str, str]:
        return self.exchange, self.symbol

    def add(self, price, size, is_bid):
        self.updates.append((price, size, is_bid))

    def __str__(self):
        return (f"OrderBookUpdate["
                f"exchange={self.exchange}, "
                f"symbol={self.symbol}, "
                f"exchange_ts={self.exchange_ts}, "
                f"local_ts={self.local_ts}, "
                f"bids={self.updates}"
                f"]")


class OrderBook:
    """
        L2 book in Python, serves as a reference implementation.
        Improve: implement a proper C++ accelerated version via nanobind
    """

    def __init__(self, exchange, symbol, bids=None, asks=None, exchange_ts=None, local_ts=None):
        self.exchange = exchange
        self.symbol = symbol
        bids = bids if bids is not None else SortedDict()
        asks = asks if asks is not None else SortedDict()
        self.bids = bids if isinstance(bids, SortedDict) else SortedDict(bids)
        self.asks = asks if isinstance(asks, SortedDict) else SortedDict(asks)
        self.cum_bids = None
        self.cum_asks = None
        self.exchange_ts = exchange_ts
        self.local_ts = local_ts

    def key(self) -> Tuple[str, str]:
        return self.exchange, self.symbol

    def __str__(self):
        return (f'exchange={self.exchange}, '
                f'symbol={self.symbol}, '
                f'exchange_ts={self.exchange_ts}, '
                f'local_ts={self.local_ts}, '
                f'top_bid={self.top_bid}, '
                f'top_ask={self.top_ask}, '
                f'spread={self.spread}')

    def snapshot(self, bids, asks):
        self.bids = SortedDict(bids)
        self.asks = SortedDict(asks)

    def timestamp(self, exchange_ts, local_ts):
        self.exchange_ts = exchange_ts
        self.local_ts = local_ts

    def update(self, price, amount, is_bid):
        if is_bid:
            if amount == 0:
                self.bids.pop(price, None)
            else:
                self.bids[price] = amount
        else:
            if amount == 0:
                self.asks.pop(price, None)
            else:
                self.asks[price] = amount

    @property
    def spread(self) -> Optional[float]:
        if self.bids and self.asks:
            return self.asks.peekitem(0)[0] - self.bids.peekitem(-1)[0]
        else:
            return None

    @property
    def mid_price(self) -> Optional[float]:
        if self.bids and self.asks:
            return (self.bids.peekitem(-1)[0] + self.asks.peekitem(0)[0])/2.0
        else:
            return None

    @property
    def top_of_book(self) -> Optional[TopOfBook]:
        bid = self.top_bid
        ask = self.top_ask
        if bid is None or ask is None:
            return None
        return TopOfBook(bid[0], bid[1], ask[0], ask[1])

    @property
    def top_of_book_price(self) -> Optional[Tuple[float, float]]:
        bid = self.top_bid_price
        ask = self.top_ask_price
        return (bid, ask) if (bid is not None and ask is not None) else None

    @property
    def top_bid(self) -> Optional[Tuple[float, float]]:
        """
        Price and volume at best bid.
        """
        if self.bids:
            return self.bids.peekitem(-1)
        else:
            return None

    @property
    def top_bid_price(self) -> Optional[float]:
        if self.bids:
            return self.bids.peekitem(-1)[0]
        else:
            return None

    @property
    def top_ask(self) -> Optional[Tuple[float, float]]:
        """
        Price and volume at best ask.
        """
        if self.asks:
            return self.asks.peekitem(0)
        else:
            return None

    @property
    def top_ask_price(self) -> Optional[float]:
        if self.asks:
            return self.asks.peekitem(0)[0]
        else:
            return None

    def levels(self, levels=None) -> Tuple[npt.NDArray, npt.NDArray]:
        """
        Get the levels as np arrays. May be costly as it
        returns full book.
        """
        bid_levels = np.flip(np.asarray(self.bids.items()), 0)
        ask_levels = np.asarray(self.asks.items())
        if levels is not None:
            bid_levels = bid_levels[0:levels, :]
            ask_levels = ask_levels[0:levels, :]
        return bid_levels, ask_levels

    def cumulative_levels(self, levels=None):
        b, a = self.levels(levels)
        cum_b = np.cumsum(b[:, 1])
        cum_a = np.cumsum(a[:, 1])
        return cum_b, cum_a

    def update_cumulative_levels(self, levels=None):
        self.cum_bids, self.cum_asks = self.cumulative_levels(levels)

    def tabulate_spread_lob(self, levels=None, float_fmt=".2f", table_fmt="psql"):
        n = min(len(self.bids), len(self.asks)) if levels is None else levels
        bid_levels, ask_levels = self.levels(n)
        data = np.hstack(np.fliplr(bid_levels), ask_levels)
        headers = ["vol", "bid", "ask", "vol"]
        return tabulate(data, headers=headers, tablefmt=table_fmt, floatfmt=float_fmt)
