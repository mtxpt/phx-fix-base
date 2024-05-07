import abc
import quickfix as fix
import copy
from typing import Optional, Tuple, Dict, List, Union
from more_itertools import partition

from phx.fix_base.fix.model.exec_report import ExecReport
from phx.fix_base.fix.model.order import Order
from phx.fix_base.fix.utils import order_status_to_string
from phx.fix_base.utils import dict_diff


class OrderTrackerBase(object):

    def __init__(self, name, logger):
        self.name = name
        self.logger = logger

        # pending new orders by cl_ord_id assigned when submitting a new order
        # can be used by client app to monitor execution timeout
        self.pending_orders: Dict[str, Order] = {}
        self.rejected_pending_orders: Dict[str, Order] = {}  # rejected order new

        # open working order by ord_id
        self.open_orders: Dict[str, Order] = {}
        self.rejected_open_orders: Dict[str, Order] = {}  # rejected order modifications

        # historical orders for canceled, filled, done orders by ord_id
        self.history_orders: Dict[str, Order] = {}

        # execution reports
        self.exec_reports: List[ExecReport] = []

        self.order_snapshots_obtained = False
        self.last_update_time = None
        self.snapshots_obtained = False

    @abc.abstractmethod
    def process(self, report: ExecReport, sending_time) -> Tuple[Optional[Order], Optional[str]]:
        pass

    def purge_history(self):
        # keep other dicts such as pending_orders, open_orders, rejected_open_orders
        self.exec_reports = []
        self.history_orders = {}

    def get_orders(self, with_history=True):
        orders = {
            "pending_orders": copy.deepcopy(self.pending_orders),
            "rejected_pending_orders": copy.deepcopy(self.rejected_pending_orders),
            "open_orders": copy.deepcopy(self.open_orders),
            "rejected_open_orders": copy.deepcopy(self.rejected_open_orders),
        }
        if with_history:
            orders["history_orders"] = copy.deepcopy(self.history_orders)
        return orders

    def get_exec_reports(self):
        return copy.deepcopy(self.exec_reports)

    def compare_open_orders(self, other: Dict[str, Order]) -> Dict[str, Tuple[Optional[Order], Optional[Order]]]:
        return dict_diff(self.open_orders, other)

    def compare_open_order(self, order: Order) -> Tuple[bool, Optional[Order]]:
        this = self.open_orders.get(order.ord_id, None)
        if this is None:
            return False, this
        else:
            return (True, this) if this == order else (False, this)

    def set_snapshots(self, reports: List[ExecReport], last_update_time, overwrite=False):
        if self.snapshots_obtained and not overwrite:
            return

        self.last_update_time = last_update_time
        orders = self.to_orders(reports)
        self.logger.info(
            f"set_snapshots {orders=}"
        )
        self.pending_orders = orders["pending"]
        self.open_orders = orders["working"]
        self.history_orders = orders["historical"]
        self.snapshots_obtained = True

    def set_order_state(self, order):
        if order.is_working_order():
            if order.ord_id is not None:
                self.open_orders[order.ord_id] = order
            elif order.cl_ord_id is not None:
                self.pending_orders[order.cl_ord_id] = order
            else:
                self.logger.error(
                    f"error in {self.__class__.__name__}: order with both ord_id=None and cl_ord_id=None not allowed"
                )
        else:
            self.history_orders[order.ord_id] = order

    def to_orders(self, reports: List[ExecReport]) -> dict:
        """
        Convert execution reports generated from order status and mass order status
        to orders and partition them into working and historical orders. Useful to
        initialize open orders or reconcile open orders with exchange order state.
        """
        pending = {}
        working = {}
        historical = {}
        non_convertable, convertable = partition(lambda r: r.convertable_to_order(), reports)
        for report in convertable:
            order = report.to_order(self.logger.error)
            assert order is not None and order.cl_ord_id is not None
            if order.ord_id is None:
                pending[order.cl_ord_id] = order
            elif order.is_working_order():
                working[order.ord_id] = order
            else:
                historical[order.ord_id] = order
        return {
            "non_convertable": list(non_convertable),
            "pending": pending,
            "working": working,
            "historical": historical
        }


class OrderTracker(OrderTrackerBase):

    def __init__(
            self,
            name,
            logger,
            position_tracker,
            print_reports=True
    ):
        OrderTrackerBase.__init__(self, name, logger)
        self.position_tracker = position_tracker
        self.print_reports = print_reports

    def process(self, report: ExecReport, sending_time) -> Tuple[Optional[Order], Optional[str]]:
        order = None
        error = None

        if report.exec_type == "I":
            error = f"{self.__class__.__name__}: execution report cannot be of type 'I'"

        elif report.cl_ord_id is None:
            error = f"{self.__class__.__name__}: cl_ord_id is None"

        elif report.exec_type == fix.ExecType_REJECTED:
            error = (
                f"{self.__class__.__name__}: ExecType_REJECTED {report.text} "
                f"exchange {report.exchange} "
                f"account {report.account} "
                f"symbol {report.symbol}"
            )

        # this is an order cancel replace
        elif report.exec_type == fix.ExecType_REPLACED:
            order = self.open_orders.get(report.ord_id, None)
            if order:
                order.update(
                    cl_ord_id=report.cl_ord_id,
                    ord_status=report.ord_status,
                    ord_type=report.ord_type,
                    tif=report.tif,
                    order_qty=report.order_qty,
                    leaves_qty=report.leaves_qty,
                    cum_qty=report.cum_qty,
                    last_qty=report.last_qty,
                    transact_time=report.tx_time,
                    price=report.price
                )

            if order is None:
                error = (
                    f"on_execution_report (Cancel Replace) : "
                    f"{report.ord_id} not found in open orders! "
                    f"order status {order_status_to_string(report.ord_status)}"
                )

        elif report.ord_status == fix.OrdStatus_REJECTED:
            self.logger.error(
                f"{self.__class__.__name__}: OrdStatus_REJECTED {report.text} "
                f"exchange {report.exchange} "
                f"account {report.account} "
                f"cl_ord_id {report.cl_ord_id} "
                f"ord_id {report.ord_id}"
            )

            if report.cl_ord_id in self.pending_orders:
                order = self.pending_orders[report.cl_ord_id]
                order.ord_status = report.ord_status
                self.rejected_pending_orders[report.cl_ord_id] = order
                del self.pending_orders[report.cl_ord_id]

            elif report.ord_id in self.open_orders:
                order = self.open_orders[report.ord_id]

                if order.cl_ord_id != report.cl_ord_id:
                    self.logger.error(
                        f"{self.__class__.__name__}: error cl_ord_id differ {order.cl_ord_id} != {report.cl_ord_id}"
                    )

                order.update(
                    ord_status=report.ord_status,
                    tif=report.tif,
                    ord_type=report.ord_type,
                    leaves_qty=report.leaves_qty,
                    cum_qty=report.cum_qty,
                    last_qty=report.last_qty,
                    avg_px=report.avg_px,
                    last_px=report.last_px,
                    transact_time=report.tx_time
                )

                # store it but do not remove it as it is still active but failed to be updated
                self.rejected_open_orders[report.ord_id] = order
                if order.ord_status == fix.OrdStatus_PENDING_NEW:
                    del self.open_orders[report.cl_ord_id]

            if order is None:
                error = (
                    f"{self.__class__.__name__}: OrdStatus_REJECTED "
                    f"{report.cl_ord_id} not found in pending orders and "
                    f"{report.ord_id} not found in open orders"
                )

        elif report.ord_status == fix.OrdStatus_PENDING_NEW:
            self.logger.info(
                f"{self.__class__.__name__}: process fix.OrdStatus_PENDING_NEW "
                f"{str(report)}"
            )
            pending = self.pending_orders.get(report.cl_ord_id, None)
            if pending:
                del self.pending_orders[report.cl_ord_id]

            order = report.to_order(self.logger.error)
            self.open_orders[report.ord_id] = order

        elif report.ord_status == fix.OrdStatus_NEW:
            order = self.open_orders.get(report.ord_id, None)
            if order:
                order.update(
                    ord_id=report.ord_id,
                    ord_status=report.ord_status,
                    leaves_qty=report.leaves_qty,
                    cum_qty=report.cum_qty,
                    last_qty=report.last_qty,
                    transact_time=report.tx_time
                )
                self.open_orders[order.ord_id] = order
            else:
                error = (
                    f"{self.__class__.__name__}: OrdStatus_NEW "
                    f"{report.ord_id} not found in open orders!"
                )

        elif (report.ord_status == fix.OrdStatus_PENDING_CANCEL
              or report.ord_status == fix.OrdStatus_PENDING_REPLACE
              or report.ord_status == fix.OrdStatus_PENDING_CANCEL_REPLACE):
            order = self.open_orders.get(report.ord_id, None)
            if order:
                order.update(
                    ord_status=report.ord_status,
                    leaves_qty=report.leaves_qty,
                    cum_qty=report.cum_qty,
                    last_qty=report.last_qty,
                    transact_time=report.tx_time
                )
            else:
                error = (
                    f"{self.__class__.__name__}: "
                    f"OrdStatus_PENDING_CANCEL | OrdStatus_PENDING_REPLACE | OrdStatus_PENDING_CANCEL_REPLACE "
                    f"{report.ord_id} not found in open orders! "
                    f"num open orders {len(self.open_orders)} "
                    f"order status {order_status_to_string(report.ord_status)}"
                )

        elif report.ord_status == fix.OrdStatus_CANCELED:
            order = self.open_orders.get(report.ord_id, None)
            if order:
                order.update(
                    ord_status=report.ord_status,
                    leaves_qty=report.leaves_qty,
                    cum_qty=report.cum_qty,
                    last_qty=report.last_qty,
                    avg_px=report.avg_px,
                    last_px=report.last_px,
                    transact_time=report.tx_time
                )
                self.history_orders[report.ord_id] = order
                del self.open_orders[report.ord_id]

            if order is None:
                error = (
                    f"{self.__class__.__name__}: OrdStatus_CANCELED "
                    f"{report.ord_id} not found in open orders! "
                    f"order status {order_status_to_string(report.ord_status)}"
                )

        elif report.ord_status == fix.OrdStatus_PARTIALLY_FILLED:
            order = self.open_orders.get(report.ord_id, None)
            if order:
                order.update(
                    ord_status=report.ord_status,
                    leaves_qty=report.leaves_qty,
                    cum_qty=report.cum_qty,
                    last_qty=report.last_qty,
                    avg_px=report.avg_px,
                    last_px=report.last_px,
                    transact_time=report.tx_time
                )
                report.last_qty = order.last_qty

                # last_qty is calculated in order.update
                self.position_tracker.add_position(
                    report.exchange, report.symbol, report.account, report.side, order.last_qty, report.tx_time
                )

                if self.print_reports:
                    table = self.position_tracker.tabulate(
                        report.exchange, report.symbol, report.account
                    )
                    self.logger.info(f"<==== position_tracker_calculated.add_position\n{table}")

            if order is None:
                error = (
                    f"{self.__class__.__name__}: OrdStatus_PARTIALLY_FILLED "
                    f"{report.ord_id} not found in open orders! "
                    f"order status {order_status_to_string(report.ord_status)}"
                )

        elif report.ord_status == fix.OrdStatus_FILLED:
            order = self.open_orders.get(report.ord_id, None)
            if order:
                order.update(
                    ord_status=report.ord_status,
                    leaves_qty=report.leaves_qty,
                    cum_qty=report.cum_qty,
                    last_qty=report.last_qty,
                    avg_px=report.avg_px,
                    last_px=report.last_px,
                    transact_time=report.tx_time
                )
                report.last_qty = order.last_qty

                self.history_orders[report.ord_id] = order
                del self.open_orders[report.ord_id]

                # last_qty is calculated in order.update
                self.position_tracker.add_position(
                    report.exchange, report.symbol, report.account, report.side, order.last_qty, report.tx_time
                )

                if self.print_reports:
                    table = self.position_tracker.tabulate(
                        report.exchange, report.symbol, report.account
                    )
                    self.logger.info(f"<==== position_tracker_calculated.add_position\n{table}")

            if order is None:
                error = (
                    f"{self.__class__.__name__}: OrdStatus_FILLED "
                    f"{report.ord_id} not found in open orders! "
                    f"order status {order_status_to_string(report.ord_status)}"
                )

        elif report.ord_status == fix.OrdStatus_DONE_FOR_DAY:
            order = self.open_orders.get(report.ord_id, None)
            if order:
                order.update(
                    ord_status=report.ord_status,
                    leaves_qty=report.leaves_qty,
                    cum_qty=report.cum_qty,
                    last_qty=report.last_qty,
                    avg_px=report.avg_px,
                    last_px=report.last_px,
                    transact_time=report.tx_time
                )
                self.history_orders[report.ord_id] = order
                del self.open_orders[report.ord_id]

            if order is None:
                error = (
                    f"{self.__class__.__name__}: OrdStatus_DONE_FOR_DAY "
                    f"{report.ord_id} not found in open orders! "
                    f"order status {order_status_to_string(report.ord_status)}"
                )

        else:
            self.exec_reports.append(report)

            error = (
                f"{self.__class__.__name__}: "
                f"unexpected exec type / order status combination {report}"
            )

        if error:
            self.logger.error(error)

        return order, error

    def remove_order(self, ord_id: str, cl_ord_id: str) -> bool:
        """Returns true if found and removed an order with those ids
        False if not found"""
        fn = "remove_order"
        order = self.open_orders.get(ord_id)
        if order:
            self.logger.info(
                f"{fn}: found open order with {ord_id=}. Move it to history"
            )
            self.history_orders[ord_id] = order
            del self.open_orders[ord_id]
        else:
            order = self.pending_orders.get(cl_ord_id)
            if order:
                del self.pending_orders[cl_ord_id]
        return order is not None
