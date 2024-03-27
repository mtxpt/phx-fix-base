import copy
import pandas as pd
import quickfix as fix
from tabulate import tabulate
from datetime import datetime
from typing import Dict, Tuple, List, Final

from phx.fix.model.position_report import PositionReport
from phx.fix.utils import signed_value


class PositionTracker(object):
    """
    Tracking positions from snapshots and or order fills.

    Note that currently we net the positions if both long_qty and short_qty are provided.
    """

    POSITION_UPDATE_FIELDS: Final = ["exchange", "symbol", "account", "update_time", "position_quantity"]
    NO_EXCHANGE: Final = "FUNDS"

    def __init__(self, name, netting: bool, logger):
        self.name = name
        self.netting = netting

        # open net position for (exchange, symbol, account) value (last update time, signed quantity)
        self.open_net_positions: Dict[Tuple[str, str, str], Tuple[datetime, float]] = {}

        # position update history (exchange, symbol, account, last update time, signed position)
        self.position_updates: List[Tuple[str, str, str, datetime, float]] = []

        self.snapshots_obtained = False
        self.last_update_time = None
        self.logger = logger

    def purge_history(self):
        self.position_updates = []

    def get_positions(self) -> dict:
        return {
            "open_net_positions": copy.deepcopy(self.open_net_positions),
            "position_updates": copy.deepcopy(self.position_updates),
        }

    def get_position(self, exchange, symbol, account) -> Tuple[datetime, float]:
        return self.open_net_positions.get((exchange, symbol, account), None)

    def compare_snapshot(self, other) -> dict:
        diff = {}
        if isinstance(other, PositionTracker):
            keys = set(self.open_net_positions.keys()).union(set(other.open_net_positions.keys()))
            for key in keys:
                if key not in self.open_net_positions:
                    diff[key] = (None, None), other.open_net_positions[key]
                elif key not in other.open_net_positions:
                    diff[key] = self.open_net_positions[key], (None, None)
                elif self.open_net_positions[key][1] != other.open_net_positions[key][1]:
                    diff[key] = self.open_net_positions[key], other.open_net_positions[key]
        return diff

    def set_snapshots(self, reports: List[PositionReport], last_update_time, overwrite=False):
        if self.snapshots_obtained and not overwrite:
            return

        self.last_update_time = last_update_time

        for report in reports:
            positions = report.positions
            if positions is not None and isinstance(positions, list):
                for pos in positions:
                    exchange = self.NO_EXCHANGE if report.exchange is None or len(report.exchange) == 0 \
                        else report.exchange

                    transact_time = last_update_time
                    # transact_time = report.clearing_business_date  # datetime.now(tz=datetime.timezone.utc) ???

                    if pos.long_qty > 0 and pos.short_qty > 0:
                        if self.netting:
                            total_quantity = pos.long_qty - pos.short_qty
                            if total_quantity >= 0:
                                qty = total_quantity
                                side = fix.Side_SELL
                            else:
                                qty = abs(total_quantity)
                                side = fix.Side_SELL
                        else:
                            self.logger.error(
                                f"simultaneous long-short positions on the same exchange",
                                f"{report.exchange}",
                                f"{report.pos_req_id}",
                                f"{report.pos_maint_rpt_id}",
                                f"{pos.account}",
                                f"{pos.symbol}",
                                f"{pos.long_qty}",
                                f"{pos.short_qty}"
                            )
                            continue
                    elif pos.long_qty == 0 and pos.short_qty == 0:
                        qty = 0
                        side = fix.Side_BUY
                    elif pos.long_qty > 0 and pos.short_qty == 0:
                        qty = pos.long_qty
                        side = fix.Side_BUY
                    elif pos.short_qty > 0 and pos.long_qty == 0:
                        qty = pos.short_qty
                        side = fix.Side_SELL
                    else:
                        self.logger.error(
                            f"invalid long or short position quantities"
                            f"{report.exchange}",
                            f"{report.pos_req_id}",
                            f"{report.pos_maint_rpt_id}",
                            f"{pos.account}",
                            f"{pos.symbol}",
                            f"{pos.long_qty}",
                            f"{pos.short_qty}"
                        )
                        continue

                    self.set_position(exchange, pos.symbol, pos.account, side, qty, transact_time)

        self.snapshots_obtained = True

    def set_position(self, exchange, symbol, account, side, qty, transact_time: datetime):
        signed_qty = signed_value(side, qty)
        if signed_qty is not None:
            key = (exchange, symbol, account)
            _, previous_qty = self.open_net_positions.get(key, (None, 0))
            signed_delta = signed_qty - previous_qty
            self.open_net_positions[key] = (transact_time, signed_qty)
            if signed_delta != 0:
                self.position_updates.append((exchange, symbol, account, transact_time, signed_delta))

    def add_position(self, exchange, symbol, account, side, fill_qty, transact_time: datetime):
        signed_fill_qty = signed_value(side, fill_qty)
        if signed_fill_qty is not None:
            key = (exchange, symbol, account)
            _, prev_qty = self.open_net_positions.get(key, (None, 0))
            self.open_net_positions[key] = (transact_time, prev_qty + signed_fill_qty)
            self.position_updates.append((exchange, symbol, account, transact_time, signed_fill_qty))

    def tabulate(self, exchange, symbol, account, pos_name=None, float_fmt=".2f", table_fmt="psql"):
        key = (exchange, symbol, account)
        data = [list(key) + list(self.open_net_positions[key])]
        if pos_name is None:
            headers = PositionTracker.POSITION_UPDATE_FIELDS
        else:
            headers = PositionTracker.POSITION_UPDATE_FIELDS[0:-1] + [pos_name]
        return tabulate(data, headers=headers, tablefmt=table_fmt, floatfmt=float_fmt)

    @staticmethod
    def tabulate_diff(diff: dict, tag1, tag2, float_fmt=".2f", table_fmt="psql"):
        def header(n, tag):
            return f"{PositionTracker.POSITION_UPDATE_FIELDS[n]}[{tag}]"
        data = []
        for key, pair in diff.items():
            row = list(key) + list(pair[0]) + list(pair[1])
            data.append(row)
        headers = PositionTracker.POSITION_UPDATE_FIELDS[0:3] + [
            header(3, tag1),
            header(4, tag1),
            header(3, tag2),
            header(4, tag2)
        ]
        return tabulate(data, headers=headers, tablefmt=table_fmt, floatfmt=float_fmt)

    def position_dfs(self):
        position_updates = copy.deepcopy(self.position_updates)
        open_net_positions = copy.deepcopy(self.open_net_positions)
        position_update_df = pd.DataFrame(
            position_updates,
            columns=PositionTracker.POSITION_UPDATE_FIELDS
        )
        open_net_position_df = pd.DataFrame(
            [list(p[0]) + list(p[1]) for p in open_net_positions.items()],
            columns=PositionTracker.POSITION_UPDATE_FIELDS
        )
        return {
            f"{self.name}_position_update": position_update_df,
            f"{self.name}_open_net_position": open_net_position_df,
        }
