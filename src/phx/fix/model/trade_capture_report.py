import pandas as pd
from typing import List, Any
from tabulate import tabulate

from phx.fix.model.message import Message


class TradeReportParty(object):

    def __init__(self, party_id, party_id_source, party_role):
        self.party_id = party_id
        self.party_id_source = party_id_source
        self.party_role = party_role

    def __str__(self):
        return (f"party_id: {self.party_id}, "
                f"party_id_source: {self.party_id_source}, "
                f"party_role: {self.party_role}"
                )


class TradeReportSide(object):

    def __init__(self, side, order_id, account, parties: List[TradeReportParty]):
        self.side = side
        self.order_id = order_id
        self.account = account
        self.parties: List[TradeReportParty] = parties

    def __str__(self):
        return (f"side={self.side}, "
                f"order_id={self.order_id}, "
                f"account={self.account}, "
                f"parties={','.join([str(p) for p in self.parties])}, "
                )


class TradeReport(object):

    def __init__(
            self, exchange, symbol, trade_report_id, trade_req_id, previously_reported,
            exec_id, exec_type, last_px, last_qty, transact_time, trade_date, sides: List[TradeReportSide]
    ):
        self.exchange = exchange
        self.symbol = symbol
        self.trade_report_id = trade_report_id
        self.trade_req_id = trade_req_id
        self.previously_reported = previously_reported
        self.exec_id = exec_id
        self.exec_type = exec_type
        self.last_px = last_px
        self.last_qty = last_qty
        self.transact_time = transact_time
        self.trade_date = trade_date
        self.sides: List[TradeReportSide] = sides

    def __str__(self):
        return (f"exchange={self.exchange}, "
                f"symbol={self.symbol}, "
                f"trade_report_id={self.trade_report_id}, "
                f"trade_req_id={self.trade_req_id}, "
                f"previously_reported={self.previously_reported}, "
                f"exec_id={self.exec_id}, "
                f"exec_type={self.exec_type}, "
                f"last_px={self.last_px}, "
                f"last_qty={self.last_qty}, "
                f"transact_time={self.transact_time}, "
                f"trade_date={self.trade_date}, "
                f"sides={','.join([str(s) for s in self.sides])}"
                )

    DETAILED_FIELDS = ["exchange", "symbol", "account", "previously_reported"]

    COMPACT_FIELDS = [
        "trade_report_id", "trade_req_id", "exec_id", "exec_type", "last_px", "last_qty", "transact_time", "trade_date",
        "side", "order_id", "party_id", "party_id_source", "party_role"
    ]

    @classmethod
    def field_names(cls, compact=True) -> List[str]:
        return cls.COMPACT_FIELDS if compact else cls.DETAILED_FIELDS + cls.COMPACT_FIELDS

    def field_str(self, compact=True) -> List[Any]:
        account = self.sides[0].account if self.sides else "None"
        side = self.sides[0].side if self.sides else "None"
        order_id = self.sides[0].order_id if self.sides else "None"
        party_id = self.sides[0].parties[0].party_id if self.sides and self.sides[0].parties else "None"
        party_id_source = self.sides[0].parties[0].party_id_source if self.sides and self.sides[0].parties else "None"
        party_role = self.sides[0].parties[0].party_role if self.sides and self.sides[0].parties else "None"
        detailed_fields = [
            self.exchange,
            self.symbol,
            account,
            self.previously_reported
        ] if not compact else []
        compact_fields = [
            self.trade_report_id,
            self.trade_req_id,
            self.exec_id,
            self.exec_type,
            self.last_px,
            self.last_qty,
            self.transact_time,
            self.trade_date,
            side,
            order_id,
            party_id,
            party_id_source,
            party_role,
        ]
        return detailed_fields + compact_fields


class TradeCaptureReport(Message):

    def __init__(self, reports: List[TradeReport]):
        self.reports = reports

    def tabulate(self, float_fmt=".2f", table_fmt="psql", compact=True):
        if self.reports:
            headers = TradeReport.field_names(compact)
            data = []
            for report in self.reports:
                row = report.field_str(compact)
                data.append(row)
            return tabulate(data, headers=headers, tablefmt=table_fmt, floatfmt=float_fmt)
        else:
            return None

    def to_df(self, compact=False):
        data = [rep.field_str(compact=compact) for rep in self.reports]
        return pd.DataFrame(data, columns=TradeReport.field_names(compact=compact))
