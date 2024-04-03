import pandas as pd
import quickfix as fix
from typing import List, Any, Optional, Set, Tuple
from tabulate import tabulate
from datetime import datetime

from phx.fix.model.message import Message
from phx.fix.model.order import Order
from phx.fix.utils import extract_message_field_value, side_to_string, order_status_to_string
from phx.fix.utils import exec_type_to_string, order_type_to_string, time_in_force_to_string
from phx.utils import str_to_datetime


class ExecReport(Message):
    def __init__(
            self,
            exchange,
            symbol,
            account,
            tx_time,
            exec_id,
            exec_type,
            cl_ord_id,
            ord_id,
            side,
            price,
            avg_px,
            last_px,
            ord_type,
            ord_status,
            order_qty,
            min_qty,
            cum_qty,
            leaves_qty,
            last_qty,
            tif=None,
            status_req_id=None,
            text="",
            is_mass_status=None,
            tot_num_reports=None,
            last_rpt_requested=None
    ):
        Message.__init__(self)
        self.exchange = exchange
        self.symbol = symbol
        self.account = account
        self.tx_time = tx_time
        self.exec_id = exec_id
        self.exec_type = exec_type
        self.cl_ord_id = cl_ord_id
        self.ord_id = ord_id
        self.side = side
        self.price = price
        self.avg_px = avg_px
        self.last_px = last_px
        self.ord_type = ord_type
        self.ord_status = ord_status
        self.order_qty = order_qty
        self.min_qty = min_qty
        self.cum_qty = cum_qty
        self.leaves_qty = leaves_qty
        self.last_qty = last_qty
        self.tif = tif
        self.status_req_id = status_req_id
        self.text = text
        self.is_mass_status = is_mass_status
        self.tot_num_reports = tot_num_reports
        self.last_rpt_requested = last_rpt_requested

    @classmethod
    def from_message(cls, message):
        """
        Parse execution report
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_8_8.html
            - https://docs.deribit.com/test/#order-mass-status-request-af

        Returns either a
          - Tuple in case it is an execution report from an order status change
          - ExecReport or a List[ExecReport] if it is a reply for a status request type I
              - ExecReport for single order status request
              - List[ExecReport] for order mass status request

        Notes:
            leaves_qty is the quantity open for further execution:
             - 0 if 'Canceled', 'DoneForTheDay', 'Expired', 'Calculated', or' Rejected'
             - leaves_qty = order_qty - cum_qty otherwise

        """
        exec_id = extract_message_field_value(fix.ExecID(), message, "str")
        ord_id = extract_message_field_value(fix.OrderID(), message, "str")
        cl_ord_id = extract_message_field_value(fix.ClOrdID(), message, "str")
        ord_status = extract_message_field_value(fix.OrdStatus(), message, "str")
        exec_type = extract_message_field_value(fix.ExecType(), message, "")
        ord_type = extract_message_field_value(fix.OrdType(), message, "str")
        price = extract_message_field_value(fix.Price(), message, "float")
        side = extract_message_field_value(fix.Side(), message, "str")
        symbol = extract_message_field_value(fix.Symbol(), message, "str")
        exchange = extract_message_field_value(fix.SecurityExchange(), message, "str")
        account = extract_message_field_value(fix.Account(), message, "str")
        tif = extract_message_field_value(fix.TimeInForce(), message, "str")
        order_qty = extract_message_field_value(fix.OrderQty(), message, "float")
        min_qty = extract_message_field_value(fix.MinQty(), message, "float")
        leaves_qty = extract_message_field_value(fix.LeavesQty(), message, "float")
        cum_qty = extract_message_field_value(fix.CumQty(), message, "float")
        last_qty = extract_message_field_value(fix.LastQty(), message, "float")
        last_qty = 0 if last_qty is None else last_qty
        avg_px = extract_message_field_value(fix.AvgPx(), message, "float")
        last_px = extract_message_field_value(fix.LastPx(), message, "float")
        tx_time = extract_message_field_value(fix.StringField(60), message, "str")  # bug in QuickFix
        tx_time = str_to_datetime(tx_time)
        text = extract_message_field_value(fix.Text(), message, "str")

        is_mass_status = None
        status_req_id = None
        tot_num_reports = None
        last_rpt_requested = None
        if exec_type == "I":
            is_mass_status = message.isSetField(fix.MassStatusReqID().getField())
            if is_mass_status:
                status_req_id = extract_message_field_value(fix.MassStatusReqID(), message, "str")
                tot_num_reports = extract_message_field_value(fix.TotNumReports(), message, "int")
                last_rpt_requested = extract_message_field_value(fix.LastRptRequested(), message, "bool")
            else:
                status_req_id = extract_message_field_value(fix.OrdStatusReqID(), message, "str")

        return ExecReport(
            exchange=exchange,
            symbol=symbol,
            account=account,
            tx_time=tx_time,
            exec_id=exec_id,
            exec_type=exec_type,
            cl_ord_id=cl_ord_id,
            ord_id=ord_id,
            side=side,
            price=price,
            avg_px=avg_px,
            last_px=last_px,
            ord_type=ord_type,
            ord_status=ord_status,
            order_qty=order_qty,
            min_qty=min_qty,
            cum_qty=cum_qty,
            leaves_qty=leaves_qty,
            last_qty=last_qty,
            tif=tif,
            text=text,
            status_req_id=status_req_id,
            is_mass_status=is_mass_status,
            tot_num_reports=tot_num_reports,
            last_rpt_requested=last_rpt_requested,
        )

    def key(self):
        return self.exchange, self.symbol

    def convertable_to_order(self):
        return (self.ord_status != fix.OrdStatus_REJECTED and
                self.cl_ord_id is not None and
                self.account is not None)

    def to_order(self, log_handler) -> Optional[Order]:
        if self.ord_status == fix.OrdStatus_REJECTED:
            log_handler(
                f"error in {self.__class__.__name__}: converting a rejected order status request's "
                f"report to an order [{self}]"
            )
            return None
        elif self.cl_ord_id is None:
            log_handler(
                f"error in {self.__class__.__name__}: converting an order status request's report to "
                f"an order without cl_ord_id [{self}]"
            )
            return None
        elif self.account is None:
            log_handler(
                f"error in {self.__class__.__name__}: converting an order status request's report to "
                f"an order without account [[{self}]]"
            )
            return None
        else:
            return Order(
                self.exchange,
                self.symbol,
                self.account,
                self.cl_ord_id,
                self.side,
                self.ord_type,
                self.order_qty,
                self.price,
                self.ord_status,
                self.min_qty,
                self.tif,
                self.ord_id,
                self.tx_time,
                text=self.text
            )

    def __str__(self):
        return (f"exchange={self.exchange}, "
                f"symbol={self.symbol}, "
                f"account={self.account}, "
                f"exec_id={self.exec_id}, "
                f"exec_type={exec_type_to_string(self.exec_type)}, "
                f"tx_time={self.tx_time}, "
                f"cl_ord_id={self.cl_ord_id}, "
                f"ord_id={self.ord_id}, "
                f"ord_status={order_status_to_string(self.ord_status)}, "
                f"ord_type={order_type_to_string(self.ord_type)}, "
                f"side={side_to_string(self.side)}, "
                f"order_qty={self.order_qty}, "
                f"price={self.price}, "
                f"min_qty={self.min_qty}, "
                f"leaves_qty={self.leaves_qty}, "
                f"cum_qty={self.cum_qty}, "
                f"last_qty={self.last_qty}, "
                f"last_px={self.last_px}, "
                f"avg_px={self.avg_px}, "
                f"tif={time_in_force_to_string(self.tif)}, "
                f"status_req_id={self.status_req_id}, "
                f"text={self.text}")

    DETAILED_FIELDS = ["exchange", "symbol", "account"]

    COMPACT_FIELDS = ["exec_id", "exec_type", "tx_time", "cl_ord_id", "ord_id",
                      "ord_status", "ord_type", "side", "order_qty", "price",
                      "min_qty", "leaves_qty", "cum_qty", "last_qty",
                      "last_px", "avg_px", "tif", "status_req_id", "text"]

    @classmethod
    def field_names(cls, compact=True) -> List[str]:
        return cls.COMPACT_FIELDS if compact else cls.DETAILED_FIELDS + cls.COMPACT_FIELDS

    def field_str(self, compact=True) -> List[Any]:
        detailed_fields = [self.exchange, self.symbol, self.account] if not compact else []
        compact_fields = [
            self.exec_id,
            exec_type_to_string(self.exec_type),
            self.tx_time,
            self.cl_ord_id,
            self.ord_id,
            order_status_to_string(self.ord_status),
            order_type_to_string(self.ord_type),
            side_to_string(self.side),
            self.order_qty,
            self.price,
            self.min_qty,
            self.leaves_qty,
            self.cum_qty,
            self.last_qty,
            self.last_px,
            self.avg_px,
            time_in_force_to_string(self.tif),
            self.status_req_id,
            self.text
        ]
        return detailed_fields + compact_fields

    @staticmethod
    def tabulate(
            reports: list,
            float_fmt=".2f",
            table_fmt="psql",
            compact=True,
            by_tx_time=True,
            reverse=True
    ):
        def key_func(elem: ExecReport):
            return elem.tx_time if elem.tx_time is not None else datetime.min

        if reports:
            sorted_reports = sorted(reports, key=key_func, reverse=reverse) if by_tx_time else reports
            data = [row.field_str(compact) for row in sorted_reports]
            return tabulate(data, headers=ExecReport.field_names(compact), tablefmt=table_fmt, floatfmt=float_fmt)
        else:
            return None

    @staticmethod
    def to_df(reports: list, compact=False):
        data = [report.field_str(compact=compact) for report in reports]
        return pd.DataFrame(data, columns=ExecReport.field_names(compact=compact))


class MassStatusExecReport(Message):

    def __init__(self, reports: List[ExecReport]):
        Message.__init__(self)
        self.reports = reports

    def keys(self) -> Set[Tuple[str, str]]:
        return {(r.exchange, r.symbol) for r in self.reports}

    def __str__(self):
        return (f"MassStatusExecReport["
                f"reports={self.reports}"
                f"]")


class MassStatusExecReportNoOrders(Message):

    def __init__(self, exchange, symbol, text):
        Message.__init__(self)
        self.exchange = exchange
        self.symbol = symbol
        self.text = text

    def key(self) -> Tuple[str, str]:
        return self.exchange, self.symbol

    def __str__(self):
        return (f"MassStatusExecReportNoOrders["
                f"exchange={self.exchange}, "
                f"symbol={self.symbol}, "
                f"text={self.text}"
                f"]")


def exec_reports_filtered_by_type(exec_reports: List[ExecReport], report_type: fix.ExecType) -> List[ExecReport]:
    res = []
    for rep in exec_reports:
        if rep.exec_type == report_type:
            res.append(rep)
    return res


def exec_reports_to_orders(exec_reports: List[ExecReport]) -> List[Order]:
    res = []
    for rep in exec_reports:
        rep_order = rep.to_order(print)
        if rep_order is not None:
            res.append(rep_order)
    return res
