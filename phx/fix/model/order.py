import pandas as pd
import quickfix as fix
from typing import List, Dict, Any
from tabulate import tabulate

from phx.fix.utils import order_type_to_string, side_to_string, order_status_to_string, time_in_force_to_string


class Order:
    def __init__(
            self, exchange, symbol, account, cl_ord_id, side, ord_type, order_qty,
            price=None, ord_status=None, min_qty=0, tif=None, ord_id=None,
            open_time=None, text=None, error=False, _dict=None
    ):
        if _dict is None:
            assert cl_ord_id is not None
            self.cl_ord_id = cl_ord_id
            self.cl_ord_ids = []
            if cl_ord_id is not None:
                self.cl_ord_ids.append(cl_ord_id)
            self.exchange = exchange
            self.symbol = symbol
            self.account = account
            self.side = side
            self.ord_type = ord_type
            self.order_qty = order_qty
            self.price = price
            self.ord_status = ord_status
            self.min_qty = min_qty
            self.tif = tif
            self.ord_id = ord_id
            self.open_time = open_time
            self.leaves_qty = order_qty
            self.cum_qty = 0
            self.last_qty = 0
            self.avg_px = 0
            self.last_px = 0
            self.transact_time = open_time
            self.error = error
            self.text = text
        else:
            self.__dict__.update(_dict)

    def key(self):
        return self.exchange, self.symbol

    def __eq__(self, other):
        if not isinstance(other, Order):
            return False

        return (self.cl_ord_id == other.cl_ord_id and
                self.exchange == other.exchange and
                self.symbol == other.symbol and
                self.account == other.account and
                self.side == other.side and
                self.ord_type == other.ord_type and
                self.order_qty == other.order_qty and
                self.price == other.price and
                self.ord_status == other.ord_status and
                self.min_qty == other.min_qty and
                self.tif == other.tif and
                self.ord_id == other.ord_id and
                self.open_time == other.open_time and
                self.leaves_qty == other.leaves_qty and
                self.cum_qty == other.cum_qty and
                self.last_qty == other.last_qty and
                self.avg_px == other.avg_px and
                self.last_px == other.last_px and
                self.transact_time == other.transact_time and
                self.error == other.error)

    def update(self, cl_ord_id=None, ord_id=None, ord_status=None, order_qty=None, price=None,
               leaves_qty=None, cum_qty=None, last_qty=None, avg_px=None, last_px=None, transact_time=None, tif=None,
               ord_type=None):
        if cl_ord_id is not None:
            self.cl_ord_ids.append(self.cl_ord_id)
            self.cl_ord_id = cl_ord_id
        if ord_id is not None:
            self.ord_id = ord_id
        if ord_status is not None:
            self.ord_status = ord_status
        if order_qty is not None:
            self.order_qty = order_qty
        if price is not None:
            self.price = price
        if last_qty is not None:
            self.last_qty = last_qty
        if leaves_qty is not None:
            if last_qty is None:
                self.last_qty = self.leaves_qty - leaves_qty
                if self.last_qty < 0:
                    raise ValueError(f"last_qty < 0 : "
                                     f"last leaves_qty {self.leaves_qty} "
                                     f"new leaves_qty {self.leaves_qty}")
            self.leaves_qty = leaves_qty
        if cum_qty is not None:
            self.cum_qty = cum_qty
        if avg_px is not None:
            self.avg_px = avg_px
        if last_px is not None:
            self.last_px = last_px
        if transact_time is not None:
            self.transact_time = transact_time
        if tif is not None:
            self.tif = tif
        if ord_type is not None:
            self.ord_type = ord_type

    def is_working_order(self) -> bool:
        return (self.ord_status == fix.OrdStatus_PARTIALLY_FILLED or
                self.ord_status == fix.OrdStatus_NEW or
                self.ord_status == fix.OrdStatus_PENDING_NEW or
                self.ord_status == fix.OrdStatus_PENDING_CANCEL or
                self.ord_status == fix.OrdStatus_PENDING_CANCEL_REPLACE)

    def is_done(self) -> bool:
        return (self.ord_status == fix.OrdStatus_FILLED or
                self.ord_status == fix.OrdStatus_CANCELED or
                self.ord_status == fix.OrdStatus_DONE_FOR_DAY or
                self.ord_status == fix.OrdStatus_REJECTED)

    def __str__(self):
        return (f'exchange={self.exchange}, '
                f'symbol={self.symbol}, '
                f'account={self.account}, '
                f'ord_id={self.ord_id}, '
                f'cl_ord_id={self.cl_ord_id}, '
                f'ord_status={order_status_to_string(self.ord_status)}, '
                f'ord_type={order_type_to_string(self.ord_type)}, '
                f'side={side_to_string(self.side)}, '
                f'order_qty={self.order_qty}, '
                f'price={self.price}, '
                f'tif={time_in_force_to_string(self.tif)}, '
                f'min_qty={self.min_qty}, '
                f'leaves_qty={self.leaves_qty}, '
                f'cum_qty={self.cum_qty}, '
                f'last_qty={self.last_qty}, '
                f'avg_px={self.avg_px}, '
                f'last_px={self.last_px}, '
                f'open_time={self.open_time}, '
                f'transact_time={self.transact_time}, '
                f'text={self.text}, '
                f'error={self.error}, '
                f'cl_ord_ids={self.cl_ord_ids}')

    def order_diff_str(self, other) -> str:
        if other is None:
            return "cannot compare as other is None"
        diffs = []
        if self.exchange != other.exchange:
            diffs.append(f'exchange: {self.exchange} != {other.exchange}')
        if self.symbol != other.symbol:
            diffs.append(f'symbol: {self.symbol} != {other.symbol}')
        if self.account != other.account:
            diffs.append(f'account: {self.account} != {other.account}')
        if self.ord_id != other.ord_id:
            diffs.append(f'ord_id: {self.ord_id} != {other.ord_id}')
        if self.cl_ord_id != other.cl_ord_id:
            diffs.append(f'cl_ord_id: {self.cl_ord_id} != {other.cl_ord_id}')
        if self.ord_status != other.ord_status:
            diffs.append(f'ord_status: {order_status_to_string(self.ord_status)} != '
                         f'{order_status_to_string(other.ord_status)}')
        if self.ord_type != other.ord_type:
            diffs.append(f'ord_type: {order_type_to_string(self.ord_type)} != {order_type_to_string(other.ord_type)}')
        if self.side != other.side:
            diffs.append(f'side: {side_to_string(self.side)} != {side_to_string(other.side)}')
        if self.order_qty != other.order_qty:
            diffs.append(f'order_qty: {self.order_qty} != {other.order_qty}')
        if self.price != other.price:
            diffs.append(f'price: {self.price} != {other.price}')
        if self.tif != other.tif:
            diffs.append(f'tif: {time_in_force_to_string(self.tif)} != {time_in_force_to_string(other.tif)}')
        if self.min_qty != other.min_qty:
            diffs.append(f'min_qty: {self.min_qty} != {other.min_qty}')
        if self.leaves_qty != other.leaves_qty:
            diffs.append(f'leaves_qty: {self.leaves_qty} != {other.leaves_qty}')
        if self.cum_qty != other.cum_qty:
            diffs.append(f'cum_qty: {self.cum_qty} != {other.cum_qty}')
        if self.last_qty != other.last_qty:
            diffs.append(f'last_qty: {self.last_qty} != {other.last_qty}')
        if self.avg_px != other.avg_px:
            diffs.append(f'avg_px: {self.avg_px} != {other.avg_px}')
        if self.last_px != other.last_px:
            diffs.append(f'last_px: {self.last_px} != {other.last_px}')
        return ', '.join(diffs)

    DETAILED_FIELDS = ["exchange", "account"]

    COMPACT_FIELDS = ["symbol", "cl_ord_id", "ord_id", "ord_status", "ord_type", "side", "order_qty", "price",
                      "tif", "open_time", "transact_time", "min_qty", "leaves_qty", "cum_qty", "last_qty",
                      "last_px", "avg_px"]

    @classmethod
    def field_names(cls, compact=True) -> List[str]:
        return cls.COMPACT_FIELDS if compact else cls.DETAILED_FIELDS + cls.COMPACT_FIELDS

    def field_str(self, compact=True) -> List[Any]:
        detailed_fields = [self.exchange, self.account] if not compact else []
        compact_fields = [
            self.symbol,
            self.cl_ord_id,
            self.ord_id,
            order_status_to_string(self.ord_status),
            order_type_to_string(self.ord_type),
            side_to_string(self.side),
            self.order_qty,
            self.price,
            time_in_force_to_string(self.tif),
            self.open_time,
            self.transact_time,
            self.min_qty,
            self.leaves_qty,
            self.cum_qty,
            self.last_qty,
            self.last_px,
            self.avg_px
        ]
        return detailed_fields + compact_fields

    @staticmethod
    def tabulate(
            orders: dict,
            float_fmt=".2f",
            table_fmt="psql",
            compact=True,
            by_cl_ord_id=True,
            reverse=True
    ):
        def key_func(o: Order):
            return o.cl_ord_id if o.cl_ord_id is not None else 0

        if orders:
            order_list = list(orders.values())
            order_list = sorted(order_list, key=key_func, reverse=reverse) if by_cl_ord_id else order_list
            data = [row.field_str(compact) for row in order_list]
            return tabulate(data, headers=Order.field_names(compact), tablefmt=table_fmt, floatfmt=float_fmt)
        else:
            return None

    @staticmethod
    def order_status_count(orders: list, convert_ord_status_to_string=False) -> Dict[str, int]:
        order_status_count = {}
        for order in orders:
            key = order_status_to_string(order.ord_status) if convert_ord_status_to_string else order.ord_status
            order_status_count[key] = order_status_count.get(key, 0) + 1
        return order_status_count

    @staticmethod
    def to_df(orders: list, compact=False):
        data = [order.field_str(compact=compact) for order in orders]
        return pd.DataFrame(data, columns=Order.field_names(compact=compact))

    @staticmethod
    def to_dfs(orders_dict: dict, compact=False):
        return {
            key: Order.to_df(orders.values(), compact=compact) for key, orders in orders_dict.items()
        }
