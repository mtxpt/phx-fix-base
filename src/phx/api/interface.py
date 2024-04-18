import abc
from typing import Union

from phx.fix.model import (
    BusinessMessageReject, Create, ExecReport, GatewayNotReady, Heartbeat, Logon, Logout,
    MarketDataRequestReject, MassStatusExecReport, MassStatusExecReportNoOrders, NotConnected,
    OrderBookSnapshot, OrderBookUpdate, OrderMassCancelReport, PositionReports, PositionRequestAck,
    Reject, SecurityReport, TradeCaptureReport, TradeCaptureReportRequestAck, Trades
)


class ApiInterface(abc.ABC):

    @abc.abstractmethod
    def run(self) -> bool:
        pass

    @abc.abstractmethod
    def dispatch(self):
        pass

    @abc.abstractmethod
    def exec_state_evaluation(self):
        pass

    @abc.abstractmethod
    def subscribe(self):
        pass

    @abc.abstractmethod
    def teardown_open_orders(self):
        pass

    @abc.abstractmethod
    def is_ready_to_disconnect(self) -> bool:
        pass

    @abc.abstractmethod
    def request_security_data(self):
        pass

    @abc.abstractmethod
    def subscribe_market_data(self):
        pass

    @abc.abstractmethod
    def request_working_orders(self):
        pass

    @abc.abstractmethod
    def request_position_snapshot(self):
        pass

    @abc.abstractmethod
    def subscribe_position_updates(self):
        pass

    @abc.abstractmethod
    def subscribe_trade_capture_reports(self):
        pass

    @abc.abstractmethod
    def start_threads(self):
        pass

    @abc.abstractmethod
    def stop_timer_thread(self):
        pass

    @abc.abstractmethod
    def on_timer(self):
        pass

    @abc.abstractmethod
    def on_logon(self, msg: Logon):
        pass

    @abc.abstractmethod
    def on_create(self, msg: Create):
        pass

    @abc.abstractmethod
    def on_logout(self, msg: Logout):
        pass

    @abc.abstractmethod
    def on_heartbeat(self, msg: Heartbeat):
        pass

    @abc.abstractmethod
    def on_connection_error(self, msg: Union[NotConnected, GatewayNotReady]):
        pass

    @abc.abstractmethod
    def on_reject(self, msg: Reject):
        pass

    @abc.abstractmethod
    def on_business_message_reject(self, msg: BusinessMessageReject):
        pass

    @abc.abstractmethod
    def on_market_data_request_reject(self, msg: MarketDataRequestReject):
        pass

    @abc.abstractmethod
    def on_security_report(self, msg: SecurityReport):
        pass

    @abc.abstractmethod
    def on_position_request_ack(self, msg: PositionRequestAck):
        pass

    @abc.abstractmethod
    def on_position_reports(self, msg: PositionReports):
        pass

    @abc.abstractmethod
    def on_trade_capture_report_request_ack(self, msg: TradeCaptureReportRequestAck):
        pass

    @abc.abstractmethod
    def on_trade_capture_report(self, msg: TradeCaptureReport):
        pass

    @abc.abstractmethod
    def on_exec_report(self, msg: ExecReport):
        pass

    @abc.abstractmethod
    def on_status_exec_report(self, msg: ExecReport):
        pass

    @abc.abstractmethod
    def on_mass_status_exec_report(self, msg: Union[MassStatusExecReport, MassStatusExecReportNoOrders]):
        pass

    @abc.abstractmethod
    def on_reject_exec_report(self, msg: ExecReport):
        pass

    @abc.abstractmethod
    def on_order_mass_cancel_report(self, msg: OrderMassCancelReport):
        pass

    @abc.abstractmethod
    def on_order_book_snapshot(self, msg: OrderBookSnapshot):
        pass

    @abc.abstractmethod
    def on_order_book_update(self, msg: OrderBookUpdate):
        pass

    @abc.abstractmethod
    def on_trades(self, msg: Trades):
        pass

    # @abc.abstractmethod
    # def round(
    #         self,
    #         price: float,
    #         direction: RoundingDirection,
    #         ticker: Tuple[str, str],
    #         min_tick_size=None
    # ) -> Optional[float]:
    #     pass
    #
    # @abc.abstractmethod
    # def tick_round(
    #         self,
    #         price,
    #         ticker: Tuple[str, str],
    #         min_tick_size=None
    # ) -> float:
    #     pass
