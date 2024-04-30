import abc
import queue
import threading
from enum import Enum
from logging import Logger
from typing import Any, Callable, List, Set, Dict, Tuple, Union, Optional

import pandas as pd
import quickfix as fix
import eventkit as ev

from phx.api import ApiInterface, Ticker
from phx.fix.app.app_runner import AppRunner
from phx.fix.app.interface import FixInterface
from phx.fix.model import ExecReport, PositionReports, Security, SecurityReport, TradeCaptureReport
from phx.fix.model import Logon, Create, Logout, Heartbeat, NotConnected, GatewayNotReady
from phx.fix.model import Order, OrderBookSnapshot, OrderBookUpdate, Trades
from phx.fix.model import OrderMassCancelReport, MassStatusExecReport, MassStatusExecReportNoOrders
from phx.fix.model import PositionRequestAck, TradeCaptureReportRequestAck
from phx.fix.model import Reject, OrderCancelReject, BusinessMessageReject, MarketDataRequestReject
from phx.fix.model.order_book import OrderBook
from phx.fix.tracker import OrderTracker, PositionTracker
from phx.fix.utils import fix_message_string
from phx.utils import CHECK_MARK, CROSS_MARK
from phx.utils.limiter import MultiPeriodLimiter
from phx.utils.thread import AlignedRepeatingTimer
from phx.utils.time import utcnow, dt_now_utc


# from phx.utils.price_utils import RoundingDirection, price_round, price_round_down, price_round_up


def single_task(key, target_dict, current_dict, pre="  ") -> List[str]:
    rows = []
    if key in target_dict.keys():
        if key in current_dict.keys():
            rows.append(f"{pre}{CROSS_MARK} {key}")
        else:
            rows.append(f"{pre}{CHECK_MARK} {key} ")
    return rows


def set_task(key, target_dict, current_dict, pre="  ") -> List[str]:
    rows = []
    target_set = target_dict.get(key, None)
    if target_set is not None:
        remaining_set = current_dict.get(key, {})
        for task in target_set:
            mark = CROSS_MARK if task in remaining_set else CHECK_MARK
            rows.append(f"{pre}{mark} {key}[{task}]")
    return rows


class DependencyAction(str, Enum):
    ORDERBOOK_SNAPSHOTS = "orderbook_snapshots"  # per instrument
    POSITION_SNAPSHOTS = "position_snapshots"  # single action
    WORKING_ORDERS = "working_orders"  # per instrument
    SECURITY_REPORTS = "security_reports"  # single action
    CANCEL_OPEN_ORDERS = "cancel_open_orders"   # single action


class PhxApi(ApiInterface, abc.ABC):

    def __init__(
            self,
            app_runner: AppRunner,
            config: dict,
            exchange: str,
            mkt_symbols: List[str],
            trading_symbols: List[str],
            logger: Logger = None,
            callbacks: Optional[Dict[str, Callable]] = None,
    ):
        # initialize variables from the parameters
        self.logger: Logger = logger if logger is not None else app_runner.logger
        self.app_runner = app_runner
        self.fix_interface: FixInterface = app_runner.app
        self.message_queue: queue.Queue = app_runner.app.message_queue
        self.config: dict = config or {}
        self.mkt_symbols: Set[Ticker] = set([(exchange, symbol) for symbol in mkt_symbols])
        self.trading_symbols: Set[Ticker] = set([(exchange, symbol) for symbol in trading_symbols])
        self.exchange = exchange

        # algo callbacks to be called when object of specific class arrives from FIX queue
        self.callbacks: Dict[str, Callable] = callbacks or {}
        self.logger.info(
            f"PhxApi callbacks for events: {list(self.callbacks.keys())}"
        )

        # parameters from configuration
        self.queue_timeout = pd.Timedelta(self.config.get("queue_timeout", "00:00:10"))

        # rate limiter setup
        rate_limit_config = self.config.get("rate_limit_for_period", [(1, "1s")])
        self.rate_limiter = MultiPeriodLimiter(rate_limit_config, self.logger)
        self.logger.info(f"PhxApi Rate Limits:\n{self.rate_limiter}")

        # state variables used by algo to determine readiness for starting and stopping trading and next actions
        self.dependency_actions = PhxApi.get_init_dependency_actions()
        self.logged_in = False  # True if API logged into Phoenix FIX Bridge
        self.subscribed = False  # indicates if API sent subscriptions to all data
        self.to_stop = False  # When set to true - API stops and disconnects

        # subscription flags set from configuration
        self.subscribe_for_position_updates = self.config.get("subscribe_for_position_updates", True)
        self.subscribe_for_trade_capture_reports = self.config.get("subscribe_for_trade_capture_reports", True)
        self.cancel_orders_on_exit = self.config.get("cancel_orders_on_exit", True)
        self.use_mass_cancel_request = False  # Not ready yet
        self.cancel_timeout_seconds = self.config.get("cancel_timeout_seconds", 5)
        self.print_reports = self.config.get("print_reports", True)

        # tracking position, orders, reports etc
        self.position_tracker = PositionTracker("local", True, self.logger)
        self.order_tracker = OrderTracker("local", self.logger, self.position_tracker, self.print_reports)
        self.position_report_counter: Dict[Ticker, int] = dict()
        self.mass_status_exec_reports = []

        # event for keeping track of updates in orders and orderbooks
        self.on_event = ev.Event()

        # order books
        self.order_books: Dict[Ticker, OrderBook] = {}

        # security list
        self.security_list: Dict[Ticker, Security] = {}

        # timers and threads
        self.timers_started = False
        self.timer_interval = pd.Timedelta(self.config.get("timer_interval", "01:00:00"))
        self.timer_alignment_freq = self.config.get("timer_alignment_freq", "1h")
        self.recurring_timer = AlignedRepeatingTimer(
            self.timer_interval,
            self.on_timer,
            name="strategy_timer",
            alignment_freq=self.timer_alignment_freq
        )
        self.run_thread = threading.Thread(name='RunApi', target=self.run, args=())

        # start the internal threads
        self.exception = None
        self.start_threads()

    @staticmethod
    def get_init_dependency_actions() -> dict:
        # initializes tracker for all actions that API keeps track of
        return {
            DependencyAction.WORKING_ORDERS: [],
            DependencyAction.ORDERBOOK_SNAPSHOTS: [],
            DependencyAction.POSITION_SNAPSHOTS: [],
            DependencyAction.SECURITY_REPORTS: [],
        }

    def register_callback(self, msg_type: str, callback: Callable):
        self.callbacks[msg_type] = callback
        self.logger.info(f"register_callback {msg_type=}:{callback=}")

    def run(self):
        self.app_runner.start()
        self.dispatch()

    def dispatch(self):
        while not self.is_finished():
            try:
                # blocking here and wait for next message until timeout
                msg = self.message_queue.get(timeout=self.queue_timeout.total_seconds())

                # first check if to call client's callback
                msg_class_name = type(msg).__name__
                if msg_class_name in self.callbacks:
                    self.callbacks[msg_class_name](msg, self.logger)

                # call internal handler
                match msg:
                    case OrderBookUpdate():
                        self.on_order_book_update(msg)
                    case Trades():
                        self.on_trades(msg)
                    case ExecReport():
                        self.on_exec_report(msg)
                    case TradeCaptureReport():
                        self.on_trade_capture_report(msg)
                    case PositionReports():
                        self.on_position_reports(msg)
                    case Heartbeat():
                        self.on_heartbeat(msg)
                    case OrderMassCancelReport():
                        self.on_order_mass_cancel_report(msg)
                    case Reject():
                        self.on_reject(msg)
                    case BusinessMessageReject():
                        self.on_business_message_reject(msg)
                    case MarketDataRequestReject():
                        self.on_market_data_request_reject(msg)
                    case OrderCancelReject():
                        self.on_order_cancel_reject(msg)
                    case OrderBookSnapshot():
                        self.on_order_book_snapshot(msg)
                    case SecurityReport():
                        self.on_security_report(msg)
                    case PositionRequestAck():
                        self.on_position_request_ack(msg)
                    case TradeCaptureReportRequestAck():
                        self.on_trade_capture_report_request_ack(msg)
                    case NotConnected():
                        self.on_connection_error(msg)
                    case GatewayNotReady():
                        self.on_connection_error(msg)
                    case Logon():
                        self.on_logon(msg)
                    case Logout():
                        self.on_logout(msg)
                    case Create():
                        self.on_create(msg)
                    case _:
                        self.logger.warning(f"unknown message type:{type(msg).__name__} {msg=}")
            except queue.Empty:
                self.exception = TimeoutError(
                    f"queue empty after waiting {self.queue_timeout.total_seconds()}s"
                )
                self.logger.info(
                    f"queue empty after waiting {self.queue_timeout.total_seconds()}s"
                )
            except Exception as e:
                self.exception = e
                self.logger.exception(
                    f"dispatch: exception {e}"
                )
            finally:
                self.exec_state_evaluation()
        self.logger.info("dispatch loop terminated")
        try:
            self.stop_timer_thread()
            self.fix_interface.save_fix_message_history(pre=self.file_name_prefix())
        except Exception as e:
            self.logger.exception(f"failed to save fix message history: {e}")

    def exec_state_evaluation(self):
        fn = self.exec_state_evaluation.__name__
        if self.to_stop and not self.is_ready_to_disconnect():
            # algo set to_stop=True but still open orders
            self.logger.info(f"{fn}: {self.to_stop=} and {self.is_ready_to_disconnect()=}. Stopping...")
            self.teardown_open_orders()
        elif self.is_ready_to_disconnect() and not self.is_finished():
            self.logger.info(
                f"{fn}: {self.is_ready_to_disconnect()=} and "
                f"{self.is_finished()=} and {self.app_runner.is_fix_session_up=}."
            )
            if self.app_runner.is_fix_session_up:
                self.logger.info("Stop app_runner...")
                self.app_runner.stop()
            else:
                self.logger.info("Wait for app_runner to stop...")
        elif self.logged_in and not self.subscribed:
            self.logger.info(f"{fn}: {self.logged_in=} and {self.subscribed:=}. Subscribe...")
            self.subscribe()

    def subscribe(self):
        self.request_security_data()
        self.subscribe_market_data()
        self.request_working_orders()
        self.request_position_snapshot()
        if self.subscribe_for_position_updates:
            self.subscribe_position_updates()
        if self.subscribe_for_trade_capture_reports:
            self.subscribe_trade_capture_reports()
        self.subscribed = True

    def teardown_open_orders(self) -> None:
        fn = self.teardown_open_orders.__name__
        if self.logged_in and self.cancel_orders_on_exit:
            self.logger.info(
                f"{fn} cancelling {len(self.order_tracker.open_orders)} orders on exit")
            if self.use_mass_cancel_request:
                for (exchange, symbol) in self.trading_symbols:
                    if self.rate_limiter.has_capacity(dt_now_utc(), 1):
                        self.rate_limiter.consume(dt_now_utc())
                        msg = self.fix_interface.order_mass_cancel_request(exchange, symbol)
                        self.logger.info(f"{fn} order mass cancel request {msg}")
                    else:
                        self.logger.info(
                            f"{fn} no rate limit capacity. Try again later."
                        )
            else:
                for (ord_id, order) in self.order_tracker.open_orders.items():
                    if self.rate_limiter.has_capacity(dt_now_utc(), 1):
                        self.rate_limiter.consume(dt_now_utc())
                        order, msg = self.fix_interface.order_cancel_request(order)
                        self.logger.info(f"{fn} order cancel request {fix_message_string(msg)}")
                    else:
                        self.logger.info(
                            f"{fn} no rate limit capacity. Try again later."
                        )
                        break
        else:
            self.logger.info(f"{fn} keep orders alive on exit")

    def is_ready_to_disconnect(self) -> bool:
        """
        Checks if API is ready to be disconnected, which is if API to_stop flag is True
        and no open orders exist.
        """
        return self.to_stop and (
            not self.cancel_orders_on_exit or
            not self.order_tracker.open_orders
        )

    def is_finished(self) -> bool:
        # returns True if API stopped, cancelled open orders and logged out
        # means algo can exit now
        return self.is_ready_to_disconnect() and not self.logged_in

    def request_security_data(self):
        self.logger.info(f"====> requesting security list...")
        self.fix_interface.security_list_request()

        # TODO check if this gives back something
        # self.logger.info(
        #     f"====> requesting security definitions for symbols {self.trading_symbols}..."
        # )
        # for (exchange, symbol) in self.trading_symbols:
        #     self.countdown_to_ready += 1
        #     self.fix_interface.security_definition_request(exchange, symbol)

    def subscribe_market_data(self):
        self.logger.info(f"====> subscribing to market data for {self.mkt_symbols}...")
        for exchange_symbol in self.mkt_symbols:
            self.fix_interface.market_data_request([exchange_symbol], 0, content="book")
            self.fix_interface.market_data_request([exchange_symbol], 0, content="trade")

    def request_working_orders(self):
        self.logger.info(f"====> requesting working order status for {self.trading_symbols}...")
        for (exchange, symbol) in self.trading_symbols:
            msg = self.fix_interface.order_mass_status_request(
                exchange,
                symbol,
                account=None,
                mass_status_req_id=f"ms_{self.fix_interface.generate_msg_id()}",
                mass_status_req_type=fix.MassStatusReqType_STATUS_FOR_ALL_ORDERS
            )
            self.logger.info(f"{fix_message_string(msg)}")

    def request_position_snapshot(self):
        # note that the same account alias has to be used for all the connected exchanges
        account = self.fix_interface.get_account()
        self.logger.info(f"====> requesting position snapshot for account {account} on {self.exchange}...")
        msg = self.fix_interface.request_for_positions(
            self.exchange,
            account=account,
            pos_req_id=f"pos_{self.fix_interface.generate_msg_id()}",
            subscription_type=fix.SubscriptionRequestType_SNAPSHOT
        )
        self.logger.info(f"{fix_message_string(msg)}")

    def subscribe_position_updates(self):
        # note that the same account alias has to be used for all the connected exchanges
        account = self.fix_interface.get_account()
        for (exchange, symbol) in self.trading_symbols:
            self.logger.info(f"====> subscribing position updates for symbol {symbol} on {exchange}...")
            msg = self.fix_interface.request_for_positions(
                exchange,
                account=account,
                symbol=symbol,
                pos_req_id=f"pos_{self.fix_interface.generate_msg_id()}",
                subscription_type=fix.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES
            )
            self.logger.debug(f"{fix_message_string(msg)}")

    def subscribe_trade_capture_reports(self):
        self.logger.info(f"====> requesting trade capture reports...")
        msg = self.fix_interface.trade_capture_report_request(
            trade_req_id=f"trade_capt_{self.fix_interface.generate_msg_id()}",
            trade_request_type=fix.TradeRequestType_ALL_TRADES,
            subscription_type=fix.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES
        )
        self.logger.debug(f"{fix_message_string(msg)}")

    def start_threads(self):
        self.logger.info(f"start_threads...")
        self.recurring_timer.start()
        self.run_thread.start()
        self.timers_started = True

    def stop_timer_thread(self):
        if self.timers_started:
            self.logger.info(f"stopping threads...")
            if self.recurring_timer.is_alive():
                self.recurring_timer.cancel()
                self.recurring_timer.join()
            self.logger.info(f"timers stopped")

    # Callback function for pulling queue messages
    def on_timer(self):
        self.logger.info(f"saving dataframes and purging history")
        self.fix_interface.save_fix_message_history(pre=self.file_name_prefix(), purge_history=True)
        self.logger.info(f"   \u2705 saved and purged fix message history")

    def on_logon(self, msg: Logon):
        self.logged_in = True

    def on_create(self, msg: Create):
        pass

    def on_logout(self, msg: Logout):
        if not self.logged_in:
            error = (
                f"on_logout {msg=} before successful login."
                " Most likely caused by a connection problem or invalid credentials"
            )
            self.exception = Exception(error)
            self.logger.error(error)
        else:
            self.logger.info(f"on_logout {msg=}")
            self.logged_in = False

    def on_heartbeat(self, msg: Heartbeat):
        pass

    def on_connection_error(self, msg: Union[NotConnected, GatewayNotReady]):
        self.logger.error(f"on_connection_error: {msg=}")
        self.logged_in = False
        self.exception = Exception(f"Connection error {msg}")
        raise self.exception

    def on_reject(self, msg: Reject):
        # TODO - need to implement update of orders that are rejected
        # of cancel rejected
        self.logger.error(f"on_reject: {msg}")

    def on_business_message_reject(self, msg: BusinessMessageReject):
        self.logger.error(f"on_business_message_reject: {msg}")

    def on_market_data_request_reject(self, msg: MarketDataRequestReject):
        self.logger.error(f"on_market_data_request_reject: {msg}")

    def on_order_cancel_reject(self, msg: OrderCancelReject):
        fn = "on_order_cancel_reject"
        self.logger.info(f"{fn} {str(msg)=}")
        if (
            "not_found" in msg.text
            or "NOT FOUND" in msg.text
            or "Too late to cancel" in msg.reason
        ):
            self.logger.warning(f"{fn} Order Cancel Rejected with {msg=}. Remove order.")
            success = self.order_tracker.remove_order(msg.ord_id, msg.orig_cl_ord_id)
            self.logger.info(f"{fn} remove order results:{success}")

    def on_security_report(self, msg: SecurityReport):
        exchanges = set([security.exchange for security in msg.securities.values()])
        for security in msg.securities.values():
            self.security_list[(security.exchange, security.symbol)] = security
            self.logger.info(f"{security}")
        # indicate that API received security reports
        # TODO - allow for adding new exchanges to the list
        self.dependency_actions[DependencyAction.SECURITY_REPORTS] = list(exchanges)
        self.logger.info(f"<==== security list completed")

    def on_position_request_ack(self, msg: PositionRequestAck):
        self.logger.info(f"on_position_request_ack: {msg}")

    def on_position_reports(self, msg: PositionReports):
        # indicate that API received positions snapshot
        for report in msg.reports:
            if not report.exchange:
                report.exchange = self.exchange
        self.position_tracker.set_snapshots(
            reports=msg.reports,
            last_update_time=utcnow(),
            overwrite=True,
            default_exchange=self.exchange,
        )
        for report in msg.reports:
            if (
                report.exchange
                and report.exchange not in self.dependency_actions[DependencyAction.POSITION_SNAPSHOTS]
            ):
                self.dependency_actions[DependencyAction.POSITION_SNAPSHOTS].append(report.exchange)
        self.logger.info(
            f"<==== on_position_reports completed \n"
            f"{msg.tabulate(compact=False)}"
        )

    def on_trade_capture_report_request_ack(self, msg: TradeCaptureReportRequestAck):
        self.logger.info(f"on_trade_capture_report_request_ack: {msg}")

    def on_trade_capture_report(self, msg: TradeCaptureReport):
        if self.print_reports:
            self.logger.info(
                f"<==== trade reports completed \n"
                f"{msg.tabulate(compact=False)}"
            )

    def on_exec_report(self, msg: ExecReport):
        fn = "on_exec_report"
        self.logger.info(
            f"{fn} msg:\n{msg}"
        )
        if msg.exec_type == "I":
            if msg.ord_status == fix.OrdStatus_REJECTED:
                self.on_mass_status_exec_report(MassStatusExecReportNoOrders(msg.exchange, msg.symbol, msg.text))
            elif msg.is_mass_status:
                if msg.tot_num_reports is None:
                    self.logger.error(
                        f"{fn} invalid tot_num_reports in {msg=}"
                    )
                    return
                self.mass_status_exec_reports.append(msg)
                if len(self.mass_status_exec_reports) == msg.tot_num_reports and msg.last_rpt_requested:
                    self.on_mass_status_exec_report(MassStatusExecReport(self.mass_status_exec_reports))
                    self.mass_status_exec_reports = []
            else:
                self.on_status_exec_report(msg)
        elif msg.exec_type == fix.ExecType_REJECTED:
            self.on_reject_exec_report(msg)
        else:
            num_open_orders_before = len(self.order_tracker.open_orders)
            order, error = self.order_tracker.process(msg, utcnow())
            self.on_event.emit(order)
            # if we canceled all open orders -> store the fix message history
            if (
                self.to_stop
                and num_open_orders_before
                and not self.order_tracker.open_orders
                and self.config.get("save_before_exit", True)
            ):
                self.logger.info(f"{fn} <==== all open orders cancelled")
                self.fix_interface.save_fix_message_history(pre=self.file_name_prefix())
                self.logger.info(f"{fn} <==== FIX message history saved")

    def on_status_exec_report(self, msg: ExecReport):
        if self.print_reports:
            self.logger.info(
                f"on_status_exec_report: "
                f"execution report of order status response:\n"
                f"{ExecReport.tabulate([msg])}"
            )

    def on_mass_status_exec_report(self, msg: Union[MassStatusExecReport, MassStatusExecReportNoOrders]):
        if isinstance(msg, MassStatusExecReport):
            # TODO: verify if can arrive multiple MassStatusExecReports - one per symbol
            self.order_tracker.set_snapshots(msg.reports, utcnow(), overwrite=True)
            self.logger.info(
                f"on_mass_status_exec_report: initial mass order status response:"
                f"\nexec reports:"
                f"\n{ExecReport.tabulate(msg.reports)}"
                f"\npending orders:"
                f"\n{Order.tabulate(self.order_tracker.pending_orders)}"
                f"\nopen orders:"
                f"\n{Order.tabulate(self.order_tracker.open_orders)}"
                f"\nhistorical orders:"
                f"\n{Order.tabulate(self.order_tracker.history_orders)}"
            )
            for ticker in self.trading_symbols:
                if ticker not in self.dependency_actions[DependencyAction.WORKING_ORDERS]:
                    self.dependency_actions[DependencyAction.WORKING_ORDERS].append(ticker)
        elif isinstance(msg, MassStatusExecReportNoOrders):
            if msg.text != "NO ORDERS":
                self.logger.warning(f"unexpected text message {msg.text}")
            self.logger.info(
                f"on_mass_status_exec_report: initial mass order status response: "
                f"no orders for {msg.exchange} {msg.symbol}"
                f" {msg=}"
            )
            ticker = (msg.exchange, msg.symbol)
            if ticker not in self.dependency_actions[DependencyAction.WORKING_ORDERS]:
                self.dependency_actions[DependencyAction.WORKING_ORDERS].append(ticker)

    def on_reject_exec_report(self, msg: ExecReport):
        self.logger.error(f"on_reject_exec_report: {msg}")

    def on_order_mass_cancel_report(self, msg: OrderMassCancelReport):
        # TODO: check why in log the msg is BTC balance
        # |9=230|35=AP|34=18|49=phoenix-prime|52=20240410-10:29:48.909|56=test|1=T1|
        # 15=BTC|55=BTC|58=FUNDS|263=0|581=1|702=1|703=TQ|704=99.999380540000|
        # 705=0.000000000000|710=pos_00003|715=20240410|721=roq-362|724=0|727=11|728=0|730=0|731=2|734=0|10=01
        self.logger.info(f"on_order_mass_cancel_report: {msg}")

    def on_order_book_snapshot(self, msg: OrderBookSnapshot):
        ticker = msg.key()
        self.logger.info(f"on_order_book_snapshot: {ticker} \n{str(msg)}")
        if ticker not in self.dependency_actions[DependencyAction.ORDERBOOK_SNAPSHOTS]:
            self.dependency_actions[DependencyAction.ORDERBOOK_SNAPSHOTS].append(ticker)
        book = OrderBook(
            msg.exchange, msg.symbol, msg.bids, msg.asks, msg.exchange_ts, msg.local_ts
        )
        self.order_books[ticker] = book
        self.on_event.emit(book)

    def on_order_book_update(self, msg: OrderBookUpdate):
        self.logger.debug(
            f"on_order_book_update: ticker:{msg.key()}"
            f" updates:{msg.updates}"
        )
        book = self.order_books.get(msg.key(), None)
        if book is not None:
            for price, quantity, is_bid in msg.updates:
                book.update(price, quantity, is_bid)
            self.on_event.emit(book)

    def on_trades(self, msg: Trades):
        pass

    def get_security(self, ticker: Ticker) -> Optional[Security]:
        return self.security_list.get(ticker)

    def get_security_attribute(self, ticker: Ticker, attribute_name: str) -> Optional[Any]:
        ret_val = None
        security = self.get_security(ticker)
        if security and isinstance(security, Security):
            if attribute_name in security.__dict__:
                ret_val = security.__dict__[attribute_name]
        return ret_val

    def file_name_prefix(self) -> str:
        timestamp = pd.Timestamp.utcnow().strftime("%Y_%m_%d_%H%M%S")
        # noinspection PyBroadException
        try:
            username = self.fix_interface.get_username()
            account = self.fix_interface.get_account()
            return f"{timestamp}_{username}_{account}"
        except Exception:
            return f"{timestamp}"
