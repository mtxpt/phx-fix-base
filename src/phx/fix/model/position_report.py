from typing import List, Any
from tabulate import tabulate

from phx.fix.model.message import Message


class Position:

    def __init__(self, symbol, account, long_qty, short_qty, pos_type=None):
        self.symbol = symbol
        self.account = account
        self.long_qty = long_qty
        self.short_qty = short_qty
        self.pos_type = pos_type

    def __str__(self):
        return (f'symbol: {self.symbol}, '
                f'account: {self.account}, '
                f'long_qty: {self.long_qty}, '
                f'short_qty: {self.short_qty}, '
                f'pos_type: {self.pos_type}'
                )

    DETAILED_FIELDS = ["exchange", "account"]

    COMPACT_FIELDS = ["symbol", "long_qty", "short_qty", "pos_type"]

    @classmethod
    def field_names(cls, compact=True) -> List[str]:
        return cls.COMPACT_FIELDS if compact else cls.DETAILED_FIELDS + cls.COMPACT_FIELDS

    def field_str(self, exchange=None, compact=True) -> List[Any]:
        detailed_fields = [exchange, self.account] if not compact else []
        compact_fields = [
            self.symbol,
            self.long_qty,
            self.short_qty,
            self.pos_type
        ]
        return detailed_fields + compact_fields


class PositionReport(object):

    def __init__(self, exchange, pos_maint_rpt_id, pos_req_id, pos_req_type,
                 settle_price, clearing_business_date,
                 positions: List[Position], text="", part_of_many=1):
        self.exchange = exchange
        self.pos_maint_rpt_id = pos_maint_rpt_id
        self.pos_req_id = pos_req_id
        self.pos_req_type = pos_req_type
        self.settle_price = settle_price
        self.clearing_business_date = clearing_business_date
        self.positions = positions
        self.text = text
        self.part_of_many = part_of_many

    def __str__(self):
        tmp_positions_str = ""
        for pos in self.positions:
            tmp_positions_str += f"{pos}\n"
            return (f'exchange={self.exchange}, '
                    f'pos_maint_rpt_id={self.pos_maint_rpt_id}, '
                    f'pos_req_id={self.pos_req_id}, '
                    f'pos_req_type={self.pos_req_type}, '
                    f'settle_price={self.settle_price}, '
                    f'clearing_business_date={self.clearing_business_date}, '
                    f'text={self.text}, '
                    f'part_of_many={self.part_of_many}, '
                    f'\npositions_list={tmp_positions_str}'
                    )

    DETAILED_FIELDS = ["pos_maint_rpt_id", "pos_req_id"]

    COMPACT_FIELDS = ["symbol", "long_qty", "short_qty"]

    @classmethod
    def field_names(cls, compact=True) -> List[str]:
        return Position.field_names(compact) if compact else cls.DETAILED_FIELDS + Position.field_names(compact)

    def field_str(self, compact=True) -> List[Any]:
        detailed_fields = [self.pos_maint_rpt_id, self.pos_req_id] if not compact else []
        result = []
        for position in self.positions:
            fields = detailed_fields + position.field_str(self.exchange, compact)
            result.append(fields)
        return result


class PositionReports(Message):

    def __init__(self, reports: List[PositionReport]):
        self.reports = reports

    def tabulate(self, float_fmt=".2f", table_fmt="psql", compact=True):
        if self.reports:
            headers = PositionReport.field_names(compact)
            data = []
            for report in self.reports:
                rows = report.field_str(compact)
                for row in rows:
                    data.append(row)
            return tabulate(data, headers=headers, tablefmt=table_fmt, floatfmt=float_fmt)
        else:
            return None
