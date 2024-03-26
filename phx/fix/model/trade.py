from typing import List

from phx.fix.utils import side_to_string
from phx.fix.model.message import Message


class Trade:
    def __init__(self, exchange, symbol, exchange_ts, local_ts, side, price, quantity):
        self.exchange = exchange
        self.symbol = symbol
        self.exchange_ts = exchange_ts
        self.local_ts = local_ts
        self.side = side
        self.price = price
        self.quantity = quantity

    def key(self):
        return self.exchange, self.symbol

    def __str__(self):
        return (f'exchange={self.exchange}, '
                f'symbol={self.symbol}, '
                f'exchange_ts={self.exchange_ts}, '
                f'local_ts={self.local_ts}, '
                f'side={side_to_string(self.side)}, '
                f'price={self.price}, '
                f'quantity={self.quantity}')


class Trades(Message):

    def __init__(self, trades: List[Trade]):
        self.trades = trades
