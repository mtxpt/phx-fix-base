import base64
import copy
import hashlib
import hmac
import os
import queue
import random
import ssl
import string
import time
from datetime import datetime
from logging import Logger
from typing import AnyStr, Dict, List, Tuple

import quickfix as fix
import quickfix44 as fix44

from phx.fix.app.config import FixAuthenticationMethod
from phx.fix.app.interface import FixInterface
from phx.fix.model.exec_report import ExecReport
from phx.fix.model.message import (
    BusinessMessageReject, Create, GatewayNotReady, Heartbeat, Logon, Logout,
    MarketDataRequestReject, Message, NotConnected, OrderCancelReject,
    OrderMassCancelReport, PositionRequestAck, Reject, TradeCaptureReportRequestAck
)
from phx.fix.model.order import Order
from phx.fix.model.order_book import OrderBookSnapshot, OrderBookUpdate
from phx.fix.model.position_report import Position, PositionReport, PositionReports
from phx.fix.model.security import Security, SecurityReport
from phx.fix.model.trade import Trade, Trades
from phx.fix.model.trade_capture_report import (
    TradeCaptureReport, TradeReport, TradeReportParty, TradeReportSide
)
from phx.fix.utils import (
    cxl_rej_reason_to_string, cxl_rej_response_to_to_string, entry_type_to_str,
    extract_message_field_value, fix_message_string, mass_cancel_reject_reason_to_string,
    mass_cancel_request_type_to_string, msg_type_to_string, session_reject_reason_to_string
)
from phx.utils import make_dirs_for_file
from phx.utils.utils import str_to_datetime

REJECT_TEXT_GATEWAY_NOT_READY = "GATEWAY_NOT_READY"

REJECT_TEXT_NOT_CONNECTED = "NOT CONNECTED"


class App(fix.Application, FixInterface):
    app_num = 0

    def __init__(
            self,
            message_queue: queue.Queue[Message],
            session_settings: fix.SessionSettings,
            logger: Logger,
            export_dir: str,
    ):
        fix.Application.__init__(self)
        self.session_settings = session_settings
        self.message_queue = message_queue
        self.logger = logger
        self.export_dir = export_dir
        self.log_mkt_data = False
        self.group_log_count = 5
        self.session_id = None
        self.sessions = set()
        self.connected = False
        self.msgID = 0
        self.execID = 0
        self.requestID = 0
        self.clOrdID = 0

        # market data, positions subscription by request id, request type - datetime, [exchange, symbol]
        self.market_data_subscriptions: Dict[Tuple[str, fix.MsgType], Tuple[datetime, List]] = {}
        self.position_subscriptions: Dict[Tuple[str, fix.MsgType], Tuple[datetime, List]] = {}
        self.trade_report_subscriptions: Dict[Tuple[str, fix.MsgType], Tuple[datetime, List]] = {}

        # plain message history
        self.received_admin_message_history: List[str] = []
        self.received_app_message_history: List[str] = []
        self.sent_admin_message_history: List[str] = []
        self.sent_app_message_history: List[str] = []

        # lists to accumulate messages before sending completed message - for convenience
        self.trade_reports = []
        self.position_reports = []

    def _reset_session_states(self):
        self.connected = False
        self.session_id = None
        if self.sessions is not None:
            self.sessions.clear()
        # TODO: Not sure whether those states need to be reset after session restart
        # self.msgID = 0
        # self.execID = 0
        # self.requestID = 0
        # self.clOrdID = 0

    def onCreate(self, session_id: fix.SessionID):
        try:
            self.logger.info(f"onCreate : Session {session_id.toString()}")
            self.message_queue.put(Create(session_id.toString()), block=False)
            self.connected = True
        except Exception as error:
            self.logger.error(f"session : {self.session_id} , exception in [onCreate] callback , might related to "
                              f"underlying c++ quickfix engine")
            self.logger.error(error, exc_info=True)

    def onLogon(self, session_id: fix.SessionID):
        try:
            self.logger.info(f"onLogon: session {session_id.toString()} logged in")
            self.message_queue.put(Logon(session_id.toString()), block=False)
            self.sessions.add(session_id)
            self.session_id = session_id
        except Exception as error:
            self.logger.error(f"exception under c++ engine : {error}")

    def onLogout(self, session_id: fix.SessionID):
        try:
            self.logger.info(f"onLogout: session {session_id.toString()} logged out")
            self.message_queue.put(Logout(session_id.toString()), block=False)
            self._reset_session_states()
        except Exception as error:
            self.logger.error(f"session : {self.session_id} , exception in [onLogout] callback , might related to "
                              f"underlying c++ quickfix engine")
            self.logger.error(error, exc_info=True)

        finally:
            self._reset_session_states()

    @staticmethod
    def get_random_string(length):
        letters = string.ascii_lowercase
        result_str = ''.join(random.choice(letters) for _ in range(length))
        return result_str

    def toAdmin(self, message: fix.Message, session_id: fix.SessionID):
        try:

            msg_type = fix.MsgType()
            message.getHeader().getField(msg_type)

            if msg_type.getValue() == fix.MsgType_Logon:
                username = self.session_settings.get(session_id).getString("Username")
                password = self.session_settings.get(session_id).getString("Password")
                auth_method = FixAuthenticationMethod(
                    self.session_settings.get(session_id).getString("FixAuthenticationMethod")
                )
                if auth_method in [
                    FixAuthenticationMethod.HMAC_SHA256,
                    FixAuthenticationMethod.HMAC_SHA256_TIMESTAMP
                ]:
                    self.logger.info(f"login with username={username} using authentication method {auth_method}")
                    random_str = App.get_random_string(8)
                    secret_key = password
                    if auth_method == FixAuthenticationMethod.HMAC_SHA256:
                        signature = hmac.new(
                            bytes(secret_key, "utf-8"),
                            bytes(random_str, "utf-8"),
                            digestmod=hashlib.sha256
                        ).digest()
                    elif auth_method == FixAuthenticationMethod.HMAC_SHA256_TIMESTAMP:
                        random_str = str(round(time.time() * 1000)) + '.' + str(ssl.RAND_bytes(64))
                        signature = hmac.new(
                            secret_key.encode('utf-8'),
                            random_str.encode('utf-8'),
                            digestmod=hashlib.sha256
                        ).digest()
                    else:
                        raise Exception(f"invalid authentication scheme {auth_method}")
                    encoded_signature = base64.b64encode(signature).decode('ascii')
                    self.logger.info(f"password signature={encoded_signature}, random_str={random_str}")
                    message.setField(fix.Username(username))
                    message.setField(fix.RawData(random_str))
                    message.setField(fix.RawDataLength(len(random_str)))
                    message.setField(fix.Password(encoded_signature))
                elif auth_method == FixAuthenticationMethod.PASSWORD:
                    self.logger.info(f"login with username={username}: using plain username/password authentication")
                    message.setField(fix.Username(username))
                    message.setField(fix.Password(password))
                else:
                    raise Exception(f"invalid authentication scheme {auth_method}")
                self.logger.info(f"[toAdmin] logon {session_id} with user and pwd")
            elif msg_type.getValue() == fix.MsgType_Logout:
                self.logger.debug(f"[toAdmin] {session_id} sending logout")
            elif msg_type.getValue() == fix.MsgType_Heartbeat:
                self.on_heart_beat(message, session_id)
            elif msg_type.getValue() == fix.MsgType_Reject:
                self.on_reject(message, session_id)
            else:
                self.logger.error(f"[toAdmin] {session_id} unhandled message | {fix_message_string(message)}")
            # need to record down the final modified to admin message
            msg = fix_message_string(message)
            self.sent_admin_message_history.append(msg)
            self.logger.debug(f"[toAdmin] {session_id} | {msg} ")
        except Exception as error:
            self.logger.error(f"session : {self.session_id} , exception in [toAdmin] callback , might related to "
                              f"underlying c++ quickfix engine")
            self.logger.error(error, exc_info=True)

    def fromAdmin(self, message: fix.Message, session_id: fix.SessionID):
        try:
            msg = fix_message_string(message)
            self.received_admin_message_history.append(
                msg)  # we cannot store a fix message for later usage - get seg fault
            self.logger.debug(f"[fromAdmin] {session_id} | {msg}")

            msg_type = fix.MsgType()
            message.getHeader().getField(msg_type)

            if msg_type.getValue() == fix.MsgType_Logon:
                pass
            elif msg_type.getValue() == fix.MsgType_Logout:
                pass
            elif msg_type.getValue() == fix.MsgType_Heartbeat:
                pass
        except Exception as error:
            self.logger.error(f"session : {self.session_id} , exception in [fromAdmin] callback , might related to "
                              f"underlying c++ quickfix engine")
            self.logger.error(error, exc_info=True)

    def toApp(self, message: fix.Message, session_id: fix.SessionID):
        try:
            msg = fix_message_string(message)
            self.sent_app_message_history.append(msg)
            self.logger.debug(f"[toApp] {session_id} | {msg}")
        except Exception as error:
            self.logger.error(f"session : {self.session_id} , exception in [toApp] callback , might related to "
                              f"underlying c++ quickfix engine")
            self.logger.error(error, exc_info=True)

    def fromApp(self, message: fix.Message, session_id: fix.SessionID):
        try:
            msg = fix_message_string(message)
            self.logger.debug(f"[fromApp] {session_id} | {msg}")
            self.received_app_message_history.append(msg)
            msg_type = fix.MsgType()
            message.getHeader().getField(msg_type)

            sending_time = extract_message_field_value(fix.SendingTime(), message, 'datetime')

            if msg_type.getValue() == fix.MsgType_MarketDataSnapshotFullRefresh:
                self.on_market_data_refresh_full(message, sending_time)
            elif msg_type.getValue() == fix.MsgType_MarketDataIncrementalRefresh:
                self.on_market_data_refresh_incremental(message, sending_time)
            elif msg_type.getValue() == fix.MsgType_ExecutionReport:
                self.on_exec_report(message, session_id, sending_time)
            elif msg_type.getValue() == fix.MsgType_PositionReport:
                self.on_position_report(message, session_id, sending_time)
            elif msg_type.getValue() == fix.MsgType_OrderCancelReject:
                self.on_order_cancel_reject(message, session_id, sending_time)
            elif msg_type.getValue() == fix.MsgType_MarketDataRequestReject:
                self.on_market_data_request_reject(message, session_id, sending_time)
            elif msg_type.getValue() == fix.MsgType_SecurityList:
                self.on_security_list(message, sending_time)
            elif msg_type.getValue() == fix.MsgType_SecurityDefinition:
                self.on_security_definition(message, sending_time)
            elif msg_type.getValue() == fix.MsgType_BusinessMessageReject:
                self.on_business_message_reject(message, sending_time)
            elif msg_type.getValue() == fix.MsgType_OrderMassCancelReport:
                self.on_order_mass_cancel_report(message, sending_time)
            elif msg_type.getValue() == fix.MsgType_RequestForPositionsAck:
                self.on_request_for_position_ack(message, session_id, sending_time)
            elif msg_type.getValue() == fix.MsgType_TradeCaptureReportRequestAck:
                self.on_trade_capture_report_request_ack(message, session_id, sending_time)
            elif msg_type.getValue() == fix.MsgType_TradeCaptureReport:
                self.on_trade_capture_report(message, session_id, sending_time)
            else:
                self.logger.error(
                    f"[fromApp] {session_id} unhandled message "
                    f"| {fix_message_string(message)}"
                )
        except Exception as error:
            self.logger.error(f"session : {self.session_id} , exception in [fromApp] callback , might related to "
                              f"underlying c++ quickfix engine")
            self.logger.error(error, exc_info=True)

    def send_message_to_session(self, message: fix.Message):
        try:
            self.logger.info(f'session_id {self.session_id} : send quick fix message {fix_message_string(message)}')
            fix.Session.sendToTarget(message, self.session_id)
        except Exception as error:
            self.logger.error(
                f"session : {self.session_id} , exception in [send_message_to_session] function , might related to "
                f"underlying c++ quickfix engine")
            self.logger.error(error, exc_info=True)

    def send_raw_message_to_session(self, message: bytes):
        try:
            self.logger.info(f'session_id {self.session_id} : send raw message in bytes {str(message)}')
            fix.Session.sendToTarget(message, self.session_id)
        except Exception as error:
            self.logger.error(
                f"session : {self.session_id} , exception in [send_raw_message_to_session] function , might related to "
                f"underlying c++ quickfix engine")
            self.logger.error(error, exc_info=True)

    def on_request_for_position_ack(self, message, session_id, sending_time):
        """
        Request for Positions Ack <AO> message
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_AO_6579.html
        """
        pos_req_status = extract_message_field_value(fix.PosReqStatus(), message)
        self.message_queue.put(PositionRequestAck(pos_req_status), block=False)
        if pos_req_status == fix.PosReqStatus_REJECTED:
            self.logger.error(
                f"request for position rejected "
                f"| {fix_message_string(message)}")
        else:
            self.logger.info(
                f"request for position acknowledged "
                f"| {fix_message_string(message)}")

    def on_trade_capture_report_request_ack(self, message, session_id, sending_time):
        """
        Trade Capture Report Request Ack <AQ> message
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_AQ_6581.html
        """
        result = extract_message_field_value(fix.TradeRequestResult(), message)
        status = extract_message_field_value(fix.TradeRequestStatus(), message)
        symbol = extract_message_field_value(fix.Symbol(), message)
        self.message_queue.put(TradeCaptureReportRequestAck(symbol, result, status), block=False)
        if result != fix.TradeRequestResult_SUCCESSFUL or status == fix.TradeRequestStatus_REJECTED:
            self.logger.error(
                f"trade capture report request rejected - Rejected "
                f"| {fix_message_string(message)}")
        else:
            self.logger.info(
                f"trade capture report request acknowledged "
                f"| {fix_message_string(message)}")

    def on_order_mass_cancel_report(self, message, sending_time):
        """
        Order Mass Cancel Report <r> message
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_r_114.html
            - https://docs.deribit.com/test/#order-mass-cancel-request-q
        """
        exchange = extract_message_field_value(fix.SecurityExchange(), message)
        symbol = extract_message_field_value(fix.Symbol(), message)
        response = extract_message_field_value(fix.MassCancelResponse(), message)
        request_type = extract_message_field_value(fix.MassCancelRequestType(), message)
        reject_reason = None
        text = None
        if response == fix.MassCancelResponse_CANCEL_REQUEST_REJECTED:
            reject_reason = extract_message_field_value(fix.MassCancelRejectReason(), message)
            text = extract_message_field_value(fix.Text(), message)
            self.logger.error(
                f"mass cancel request rejected: "
                f"type={mass_cancel_request_type_to_string(request_type)}, "
                f"reason={mass_cancel_reject_reason_to_string(reject_reason)}, "
                f"text={text} "
                f"| {fix_message_string(message)}")
        report = OrderMassCancelReport(exchange, symbol, response, request_type, reject_reason, text)
        self.message_queue.put(report, block=False)

    def on_heart_beat(self, message, session_id):
        receive_ts = extract_message_field_value(fix.SendingTime(), message, "datetime")
        self.message_queue.put(Heartbeat(receive_ts), block=False)

    def on_business_message_reject(self, message, session_id):
        ref_msg_seq_num = extract_message_field_value(fix.RefSeqNum(), message, "int")
        ref_msg_type = extract_message_field_value(fix.RefMsgType(), message, "str")
        reason = extract_message_field_value(fix.BusinessRejectReason(), message, "int")
        text = extract_message_field_value(fix.Text(), message, "str")
        self.message_queue.put(BusinessMessageReject(ref_msg_seq_num, ref_msg_type, reason, text), block=False)
        self.logger.error(
            f"on_business_reject {reason} : "
            f"ref msg seq {ref_msg_seq_num} "
            f"ref msg type {msg_type_to_string(ref_msg_type)} "
            f"{text} "
            f"| {fix_message_string(message)}"
        )

    def on_reject(self, message, session_id):
        """
        8=FIX.4.4|9=110|35=3|34=10|49=test|52=20230915-04:55:51.000|56=proxy|45=8
            |58=Tag specified without a value|371=37|372=8|373=4|10=24
        """
        ref_msg_seq_num = extract_message_field_value(fix.RefSeqNum(), message, "int")
        ref_msg_type = extract_message_field_value(fix.RefMsgType(), message, "str")
        ref_tag = extract_message_field_value(fix.RefTagID(), message, "int")
        reason = extract_message_field_value(fix.SessionRejectReason(), message, "int")
        text = extract_message_field_value(fix.Text(), message, "str")
        self.message_queue.put(Reject(ref_msg_seq_num, ref_msg_type, ref_tag, reason, text), block=False)
        self.logger.error(
            f"on_reject {session_reject_reason_to_string(reason)} : "
            f"ref_msg_seq_num={ref_msg_seq_num}, "
            f"ref_msg_type={msg_type_to_string(ref_msg_type)}, "
            f"ref_tag={ref_tag}, "
            f"{text} "
            f"| {fix_message_string(message)}"
        )

    def on_market_data_refresh_full(self, message, sending_time):
        """
        8=FIX.4.4|9=758|35=W|34=3|49=proxy|52=20230913-14:15:47.278|56=test|
            55=BTC-PERPETUAL|207=deribit|262=req_id_2|
                268=10|
                    269=0|270=25709.5|271=12998|272=20230913|273=14:15:47.102|336=deribit|
                    269=0|270=25708|271=1|272=20230913|273=14:15:47.102|336=deribit|
                    269=0|270=25707|271=1|272=20230913|273=14:15:47.102|336=deribit|
                    269=0|270=25676.5|271=1|272=20230913|273=14:15:47.102|336=deribit|
                    269=0|270=25627.5|271=1|272=20230913|273=14:15:47.102|336=deribit|
                    269=1|270=25710|271=10|272=20230913|273=14:15:47.102|336=deribit|
                    269=1|270=25768.5|271=100|272=20230913|273=14:15:47.102|336=deribit|
                    269=1|270=25849.5|271=1|272=20230913|273=14:15:47.102|336=deribit|
                    269=1|270=25972|271=3|272=20230913|273=14:15:47.102|336=deribit|
                    269=1|270=26008|271=3|272=20230913|273=14:15:47.102|336=deribit|
            10=20

        Should usually not get any trade updates but not sure.
        """
        receive_ts = extract_message_field_value(fix.SendingTime(), message, "datetime")
        exchange = extract_message_field_value(fix.SecurityExchange(), message, "str")
        symbol = extract_message_field_value(fix.Symbol(), message, "str")
        group = fix44.MarketDataSnapshotFullRefresh.NoMDEntries()
        group_size = extract_message_field_value(fix.NoMDEntries(), message, "int")
        md_req_id = extract_message_field_value(fix.MDReqID(), message, "str")

        self.logger.debug(
            f" ===> on_market_data_refresh_full [{group_size}] {exchange} {symbol} "
            f"{receive_ts} {md_req_id} | {fix_message_string(message)}"
        )

        timestamp = None
        bids = {}
        asks = {}
        for i in range(group_size):
            message.getGroup(i + 1, group)
            entry_type = extract_message_field_value(fix.MDEntryType(), group, "")
            price = extract_message_field_value(fix.MDEntryPx(), group, "float")
            size = extract_message_field_value(fix.MDEntrySize(), group, "float")
            date_str = extract_message_field_value(fix.StringField(272), group, "str")  # QuickFix bug
            time_str = extract_message_field_value(fix.StringField(273), group, "str")
            timestamp = str_to_datetime(f"{date_str}-{time_str}")

            if entry_type == fix.MDEntryType_BID:
                bids[price] = size
            elif entry_type == fix.MDEntryType_OFFER:
                asks[price] = size

            if i < self.group_log_count and self.log_mkt_data:
                self.logger.debug(
                    f"  [{i}] {entry_type_to_str(entry_type)} "
                    f"{price} {size} {timestamp}")

        # we have an issue with zero size books, most likely from a trade snapshot that is empty
        if group_size > 0:
            snapshot = OrderBookSnapshot(exchange, symbol, timestamp, receive_ts, bids, asks)
            self.message_queue.put(snapshot, block=False)
        else:
            self.logger.error(
                f"Market_data_refresh - empty book for exchange {exchange} symbol {symbol} "
                f"| {fix_message_string(message)}"
            )

    def on_market_data_refresh_incremental(self, message, sending_time):
        """
        8=FIX.4.4|9=176|35=X|34=9|49=proxy|52=20230913-14:15:48.277|56=test|262=req_id_2|
            268=1|
                279=1|269=0|55=BTC-PERPETUAL|207=deribit|270=25709.5|271=12987|272=20230913|273=14:15:48.108|336=deribit|
            10=00

        update action
            0 = New (fix.MDUpdateAction_NEW)
            1 = Change (fix.MDUpdateAction_CHANGE)
            2 = Delete (fix.MDUpdateAction_DELETE)

        entry type
            0 = Bid, (fix.MDEntryType_BID)
            1 = Ask, (fix.MDEntryType_OFFER)
            2 = Trade (fix.MDEntryType_TRADE)
        """
        fn = "on_market_data_refresh_incremental"
        receive_ts = extract_message_field_value(fix.SendingTime(), message, "datetime")
        group = fix44.MarketDataIncrementalRefresh.NoMDEntries()
        group_size = extract_message_field_value(fix.NoMDEntries(), message, "int")

        self.logger.debug(f"{fn} receive_ts={receive_ts} group_size={group_size}")

        book_key = None
        book_update = None
        book_updates: Dict[Tuple[str, str], OrderBookUpdate] = {}
        trades: List[Trade] = []
        timestamp = datetime.utcnow()

        for i in range(group_size):
            message.getGroup(i + 1, group)
            entry_type = extract_message_field_value(fix.MDEntryType(), group, "")
            # update_action = extract_message_field_value(fix.MDUpdateAction(), group, "")
            exchange = extract_message_field_value(fix.SecurityExchange(), group, "str")
            symbol = extract_message_field_value(fix.Symbol(), group, "str")
            price = extract_message_field_value(fix.MDEntryPx(), group, "float")
            size = extract_message_field_value(fix.MDEntrySize(), group, "float")
            side = None  # if we want to have the side of the trade we should get the trades via SBE
            date_str = extract_message_field_value(fix.StringField(272), group, "str")  # QuickFix bug
            time_str = extract_message_field_value(fix.StringField(273), group, "str")
            element_ts = str_to_datetime(f"{date_str}-{time_str}")  # TODO clarify diff between element_ts / receive_ts

            if entry_type == fix.MDEntryType_TRADE:
                trades.append(Trade(exchange, symbol, timestamp, receive_ts, side, price, size))
            else:
                self.logger.debug(
                    f"{fn} {exchange=} {symbol=} "
                    f" {price=} {size=} {entry_type=}"
                )
                if book_key != (exchange, symbol):
                    book_key = (exchange, symbol)
                    if book_key not in book_updates:
                        book_updates[book_key] = OrderBookUpdate(exchange, symbol, timestamp, receive_ts)
                    book_update = book_updates[book_key]
                    self.logger.debug(
                        f"{fn} set book_update {book_key=} update:{str(book_update)}"
                    )
                book_update.add(price, size, entry_type == fix.MDEntryType_BID)
                self.logger.debug(
                    f"{fn} added to book_update {book_key=} update:{str(book_update)}"
                )

        if book_updates:
            for book_key, book_update in book_updates.items():
                self.logger.debug(
                    f"{fn} enqueue book_update {book_key=} update:{str(book_update)}"
                )
                self.message_queue.put(book_update, block=False)

        if trades:
            self.message_queue.put(Trades(trades), block=False)

    def on_exec_report(self, message, session_id, sending_time):
        """
        parse execution report
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_8_8.html
            - https://docs.deribit.com/test/#order-mass-status-request-af
        """
        report = ExecReport.from_message(message)

        if report.exec_type == fix.ExecType_REJECTED and report.text == REJECT_TEXT_GATEWAY_NOT_READY:
            self.message_queue.put(GatewayNotReady(report), block=False)
        if report.exec_type == fix.ExecType_REJECTED and report.text == REJECT_TEXT_NOT_CONNECTED:
            self.message_queue.put(NotConnected(report), block=False)
        else:
            self.message_queue.put(report, block=False)

    def on_position_report(self, message, session_id, sending_time):
        """
        parse position report
            - https://www.onixs.biz/fix-dictionary/4.4/msgtype_ap_6580.html
            - https://docs.deribit.com/#position-report-ap
        """
        pos_req_id = extract_message_field_value(fix.PosReqID(), message, "str")
        pos_maint_rpt_id = extract_message_field_value(fix.PosMaintRptID(), message, "str")
        pos_req_type = extract_message_field_value(fix.PosReqType(), message, "int")
        tot_num_pos_reports = extract_message_field_value(fix.TotalNumPosReports(), message, "int")
        exchange = extract_message_field_value(fix.SecurityExchange(), message, "str")
        account = extract_message_field_value(fix.Account(), message, "str")
        symbol = extract_message_field_value(fix.Symbol(), message, "str")
        text = extract_message_field_value(fix.Text(), message, "str")
        settle_price = extract_message_field_value(fix.SettlPrice(), message, "float")
        clearing_business_date = extract_message_field_value(fix.ClearingBusinessDate(), message, "str")

        group = fix44.PositionReport.NoPositions()
        group_size = extract_message_field_value(fix.NoPositions(), message, "int")
        positions = []
        for i in range(group_size):
            message.getGroup(i + 1, group)
            post_type = extract_message_field_value(fix.PosType(), group, "str")
            long_qty = extract_message_field_value(fix.LongQty(), group, "float")
            short_qty = extract_message_field_value(fix.ShortQty(), group, "float")
            positions.append(Position(symbol, account, long_qty, short_qty, post_type))

        report = PositionReport(
            exchange, pos_maint_rpt_id, pos_req_id, pos_req_type, settle_price,
            clearing_business_date, positions, text, tot_num_pos_reports
        )

        self.position_reports.append(report)
        if len(self.position_reports) == tot_num_pos_reports:
            reports = self.position_reports
            self.position_reports = []
            self.message_queue.put(PositionReports(reports), block=False, timeout=None)  # TODO check

    def on_trade_capture_report(self, message, session_id, sending_time):
        """
        Trade Capture Report <AE> message
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_AE_6569.html
        """
        trade_report_id = extract_message_field_value(fix.TradeReportID(), message, "str")
        trade_req_id = extract_message_field_value(fix.TradeRequestID(), message, "str")
        last_requested = extract_message_field_value(fix.LastRptRequested(), message, "bool")
        tot_num_trade_reports = extract_message_field_value(fix.TotNumTradeReports(), message, "int")

        previously_reported = extract_message_field_value(fix.PreviouslyReported(), message, "bool")
        exec_id = extract_message_field_value(fix.ExecID(), message, "str")
        exec_type = extract_message_field_value(fix.ExecType(), message, "")
        last_px = extract_message_field_value(fix.LastPx(), message, "float")
        last_qty = extract_message_field_value(fix.LastQty(), message, "float")
        transact_time = extract_message_field_value(fix.StringField(60), message, "str")  # QuickFix bug
        transact_time = str_to_datetime(transact_time)
        trade_date = extract_message_field_value(fix.TradeDate(), message, "str")
        symbol = extract_message_field_value(fix.Symbol(), message, "str")
        exchange = extract_message_field_value(fix.SecurityExchange(), message, "str")

        sides_group = fix44.TradeCaptureReport.NoSides()
        num_sides = extract_message_field_value(fix.NoSides(), message, "int")
        sides = []
        for i in range(num_sides):
            message.getGroup(i + 1, sides_group)
            side = extract_message_field_value(fix.Side(), sides_group, "")
            order_id = extract_message_field_value(fix.OrderID(), sides_group, "str")
            account = extract_message_field_value(fix.Account(), sides_group, "str")
            num_parties = extract_message_field_value(fix.NoPartyIDs(), sides_group, "int")
            party_group = sides_group.NoPartyIDs()
            parties = []
            if num_parties is not None:
                for j in range(num_parties):
                    sides_group.getGroup(i + 1, party_group)
                    party_id = extract_message_field_value(fix.PartyID(), party_group, "str")
                    party_id_source = extract_message_field_value(fix.PartyIDSource(), party_group, "")
                    party_role = extract_message_field_value(fix.PartyRole(), party_group, "int")
                    parties.append(TradeReportParty(party_id, party_id_source, party_role))

            sides.append(TradeReportSide(side, order_id, account, parties))

        report = TradeReport(
            exchange, symbol, trade_report_id, trade_req_id, previously_reported,
            exec_id, exec_type, last_px, last_qty, transact_time, trade_date, sides
        )

        self.trade_reports.append(report)
        if len(self.trade_reports) == tot_num_trade_reports:
            reports = self.trade_reports
            self.trade_reports = []
            self.message_queue.put(TradeCaptureReport(reports), block=False)

    def on_security_list(self, message, sending_time):
        """
        8=FIX.4.4|9=1186|35=y|34=2|49=proxy|52=20230913-13:09:27.593|56=test|
            146=20|
                55=BTC-PERPETUAL|231=10|207=deribit|562=1|336=deribit|
                55=ETH-29MAR24|231=1|207=deribit|562=1|336=deribit|
                55=BTC-DERIBIT-INDEX|207=deribit|336=deribit|
                55=ETH-27OCT23|231=1|207=deribit|562=1|336=deribit|
                55=BTC-28JUN24|231=10|207=deribit|562=1|336=deribit|
                55=ETH-22SEP23|231=1|207=deribit|562=1|336=deribit|
                55=ETH_USDC-PERPETUAL|231=0.010000000000000004|207=deribit|562=1|336=deribit|
                55=ETH-PERPETUAL|231=1|207=deribit|562=1|336=deribit|
                55=BTC-29DEC23|231=10|207=deribit|562=1|336=deribit|
                55=ETH-28JUN24|231=1|207=deribit|562=1|336=deribit|
                55=ETH-29SEP23|231=1|207=deribit|562=1|336=deribit|
                55=ETH-29DEC23|231=1|207=deribit|562=1|336=deribit|
                55=BTC-29MAR24|231=10|207=deribit|562=1|336=deribit|
                55=ETH-DERIBIT-INDEX|207=deribit|336=deribit|
                55=BTC-29SEP23|231=10|207=deribit|562=1|336=deribit|
                55=BTC-27OCT23|231=10|207=deribit|562=1|336=deribit|
                55=BTC-15SEP23|231=10|207=deribit|562=1|336=deribit|
                55=BTC-22SEP23|231=10|207=deribit|562=1|336=deribit|
                55=BTC_USDC-PERPETUAL|231=0.0010000000000000005|207=deribit|562=1|336=deribit|
                55=ETH-15SEP23|231=1|207=deribit|562=1|336=deribit|
            320=seq_list_req_id|322=roq-1694610567593928000|560=0|10=05

        security_definition_request gives no further information
        """
        self.logger.info(f"on_security_list {fix_message_string(message)}")

        group = fix44.SecurityList.NoRelatedSym()
        group_size = extract_message_field_value(fix.NoRelatedSym(), message, "int")

        security_list = {}

        for i in range(group_size):
            message.getGroup(i + 1, group)
            exchange = extract_message_field_value(fix.SecurityExchange(), group, "str")
            symbol = extract_message_field_value(fix.Symbol(), group, "str")
            multiplier = extract_message_field_value(fix.ContractMultiplier(), group, "int")
            min_trade_vol = extract_message_field_value(fix.MinTradeVol(), group, "float")
            min_price_increment = extract_message_field_value(fix.MinPriceIncrement(), group, "float")
            trading_session_id = extract_message_field_value(fix.TradingSessionID(), group, "str")
            security_list[(exchange, symbol)] = Security(
                exchange, symbol, multiplier, min_trade_vol, min_price_increment
            )

        self.message_queue.put(SecurityReport(security_list), block=False, timeout=None)  # TODO check

    def on_security_definition(self, message: fix.Message, sending_time):
        self.logger.debug(f"on_security_definition {fix_message_string(message)}")
        # TODO

    def on_market_data_request_reject(self, message: fix.Message, session_id, sending_time):
        text = extract_message_field_value(fix.Text(), message, "str")
        reason = extract_message_field_value(fix.MDReqRejReason(), message, "str")
        self.message_queue.put(MarketDataRequestReject(reason, text), block=False)
        self.logger.error(f"on_market_data_request_reject {session_id} | {fix_message_string(message)}")

    def on_order_cancel_reject(self, message: fix.Message, session_id, sending_time):
        ord_id = extract_message_field_value(fix.OrderID(), message, "str")
        cl_ord_id = extract_message_field_value(fix.ClOrdID(), message, "str")
        orig_cl_ord_id = extract_message_field_value(fix.OrigClOrdID(), message, "str")
        cxl_rej_response_to = extract_message_field_value(fix.CxlRejResponseTo(), message, "str")
        cxl_rej_reason = extract_message_field_value(fix.CxlRejReason(), message, "int")
        text = extract_message_field_value(fix.Text(), message, "str")
        reason_str = cxl_rej_reason_to_string(cxl_rej_reason)
        self.logger.warning(
            f"order cancel reject: "
            f"ord_id {ord_id} "
            f"cl_ord_id {cl_ord_id} "
            f"orig_cl_ord_id {orig_cl_ord_id} "
            f"response_to:{cxl_rej_response_to_to_string(cxl_rej_response_to)} "
            f"reason:{reason_str} "
            f"text:{text} "
            f"| {fix_message_string(message)}"
        )
        self.message_queue.put(
            OrderCancelReject(ord_id, cl_ord_id, orig_cl_ord_id, reason_str, text),
            block=False,
        )
        # self.strategy.on_order_cancel_reject_completed(cxl_rej_reason, text)

    def generate_msg_id(self) -> AnyStr:
        self.msgID += 1
        return str(self.msgID).zfill(5)

    def generate_exec_id(self) -> AnyStr:
        self.execID += 1
        return str(self.execID).zfill(5)

    def generate_cl_ord_id(self) -> AnyStr:
        self.clOrdID += 1
        ts = int(datetime.now().timestamp())
        return f"{ts}_{self.clOrdID}"

    def next_request_id(self) -> int:
        self.requestID += 1
        return self.requestID

    def new_order_single(
            self, exchange, symbol, side, order_qty, price=None,
            ord_type=fix.OrdType_LIMIT,
            tif=fix.TimeInForce_GOOD_TILL_CANCEL,
            account=None, min_qty=0, text=""
    ) -> Tuple[Order, fix.Message]:
        """
        Send new order single request
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_D_68.html
        """
        message = fix.Message()
        header = message.getHeader()
        header.setField(fix.MsgType(fix.MsgType_NewOrderSingle))
        cl_ord_id = self.generate_cl_ord_id()
        message.setField(fix.ClOrdID(cl_ord_id))
        message.setField(fix.Side(side))
        message.setField(fix.SecurityExchange(exchange))
        message.setField(fix.Symbol(symbol))
        message.setField(fix.OrderQty(order_qty))
        if price is not None:
            message.setField(fix.Price(price))  # tick rounding has to be done in upper layer
        message.setField(fix.OrdType(ord_type))
        if ord_type != fix.OrdType_MARKET:
            message.setField(fix.TimeInForce(tif))
        if min_qty != 0:
            message.setField(fix.MinQty(min_qty))
        if text is not None:
            message.setField(fix.Text(text))
        if account is not None:
            message.setField(fix.Account(account))
        tx_time = fix.TransactTime()
        tx_time.setString(datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        message.setField(tx_time)
        order = Order(
            exchange, symbol, account, cl_ord_id, side, ord_type, order_qty, price,
            fix.OrdStatus_PENDING_NEW, min_qty, tif, ord_id=None, text=text
        )
        self.send_message_to_session(message)
        return order, message

    def order_cancel_request(self, order: Order) -> Tuple[Order, fix.Message]:
        """
        Send order cancel request
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_F_70.html
            - https://docs.deribit.com/test/#order-cancel-request-f
        """
        message = fix.Message()
        header = message.getHeader()
        header.setField(fix.MsgType(fix.MsgType_OrderCancelRequest))
        message.setField(fix.OrigClOrdID(order.cl_ord_id))
        cl_ord_id = self.generate_cl_ord_id()
        message.setField(fix.ClOrdID(cl_ord_id))
        message.setField(fix.SecurityExchange(order.exchange))
        message.setField(fix.Symbol(order.symbol))
        message.setField(fix.Side(order.side))
        message.setField(fix.OrderQty(order.order_qty))
        if order.account is not None:
            message.setField(fix.Account(order.account))

        tx_time = fix.TransactTime()
        tx_time.setString(datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        message.setField(tx_time)

        order.ord_status = fix.OrdStatus_PENDING_CANCEL  # do not update order.cl_ord_id yet as may be rejected

        self.send_message_to_session(message)
        return order, message

    def send_order_cancel_request(self, original_client_oid: str, exchange: str, order_quantity: float,
                                  account: str, client_oid: str, text: str, symbol: str, order_id: str,
                                  side: int) -> fix.Message:
        message = fix.Message()
        header = message.getHeader()
        header.setField(fix.MsgType(fix.MsgType_OrderCancelRequest))
        if original_client_oid is not None:
            message.setField(fix.OrigClOrdID(original_client_oid))
        if side is not None:
            message.setField(fix.Side(side))
        if order_quantity is not None:
            message.setField(fix.OrderQty(order_quantity))
        if account is not None:
            message.setField(fix.Account(account))
        if symbol is not None:
            message.setField(fix.Symbol(symbol))
        if exchange is not None:
            message.setField(fix.SecurityExchange(exchange))
        if text is not None:
            message.setField(fix.Text(text))
        if order_id is not None:
            message.setField(fix.OrderID(order_id))
        if client_oid is not None:
            message.setField(fix.ClOrdID(client_oid))

        tx_time = fix.TransactTime()
        tx_time.setString(datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        message.setField(tx_time)

        self.send_message_to_session(message)

        return message

    def order_cancel_replace_request(
            self, order: Order, order_qty: float, price: float = None, ord_type: int = None,
            exec_instr: str = None, account: str = None
    ) -> Tuple[Order, fix.Message]:
        """
        Send order cancel replace request
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_G_71.html
            - https://docs.deribit.com/test/#order-cancel-replace-request-g

        Side cannot be changed (however, some side modifications are allowed by FIX standard)
        """
        message = fix.Message()
        header = message.getHeader()
        header.setField(fix.MsgType(fix.MsgType_OrderCancelReplaceRequest))
        message.setField(fix.OrigClOrdID(order.cl_ord_id))
        cl_ord_id = self.generate_cl_ord_id()
        message.setField(fix.ClOrdID(cl_ord_id))
        message.setField(fix.SecurityExchange(order.exchange))
        message.setField(fix.Symbol(order.symbol))
        message.setField(fix.Side(order.side))
        if ord_type is not None:
            message.setField(fix.OrdType(ord_type))
        else:
            message.setField(fix.OrdType(order.ord_type))
        if order_qty is not None:
            message.setField(fix.OrderQty(order_qty))
        if price is not None:
            message.setField(fix.Price(price))  # tick rounding has to be done in upper layer
        if exec_instr is not None:
            message.setField(fix.ExecInst(exec_instr))
        if account is not None:
            message.setField(fix.Account(account))

        tx_time = fix.TransactTime()
        tx_time.setString(datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        message.setField(tx_time)

        order.ord_status = fix.OrdStatus_PENDING_CANCEL_REPLACE  # do not update order.cl_ord_id yet as may be rejected

        self.send_message_to_session(message)

        return order, message

    def order_mass_cancel_request(
            self,
            exchange: str = None,
            symbol: str = None,
            side: int = None,
            currency: str = None,
            security_type: str = None,
            account: str = None,
    ) -> fix.Message:
        """
        Send order mass cancel request
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_q_113.html
            - https://docs.deribit.com/test/#order-mass-cancel-request-q
        """
        message = fix.Message()
        header = message.getHeader()
        header.setField(fix.MsgType(fix.MsgType_OrderMassCancelRequest))
        cl_ord_id = self.generate_cl_ord_id()
        message.setField(fix.ClOrdID(cl_ord_id))

        if exchange is not None and symbol is not None:
            message.setField(fix.SecurityExchange(exchange))
            message.setField(fix.Symbol(symbol))
            message.setField(fix.MassCancelRequestType(fix.MassCancelRequestType_CANCEL_ORDERS_FOR_A_SECURITY))
        elif security_type is not None:
            message.setField(fix.SecurityType(security_type))
            message.setField(fix.MassCancelRequestType(fix.MassCancelRequestType_CANCEL_ORDERS_FOR_A_SECURITYTYPE))
        else:
            message.setField(fix.MassCancelRequestType(fix.MassCancelRequestType_CANCEL_ALL_ORDERS))
        if side is not None:
            message.setField(fix.Side(side))
        if currency is not None:
            message.setField(fix.Currency(currency))

        tx_time = fix.TransactTime()
        tx_time.setString(datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        message.setField(tx_time)
        self.send_message_to_session(message)
        return message

    def order_status_request(
            self,
            exchange: str,
            symbol: str,
            cl_ord_id: str,
            side: int,
            order_id=None,
            account=None
    ) -> fix.Message:
        """
        Send order status request.
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_H_72.html
        """
        message = fix.Message()
        header = message.getHeader()
        header.setField(fix.MsgType(fix.MsgType_OrderStatusRequest))
        message.setField(fix.OrdStatusReqID(self.generate_exec_id()))
        if exchange is not None:
            message.setField(fix.SecurityExchange(exchange))
        if symbol is not None:
            message.setField(fix.Symbol(symbol))
        message.setField(fix.ClOrdID(cl_ord_id))
        message.setField(fix.Side(side))
        if order_id is not None:
            message.setField(fix.OrderID(order_id))
        if account is not None:
            message.setField(fix.Account(account))
        self.send_message_to_session(message)
        return message

    def order_mass_status_request(
            self,
            exchange: str,
            symbol: str,
            account=None,
            mass_status_req_id="working_orders",
            mass_status_req_type=fix.MassStatusReqType_STATUS_FOR_ALL_ORDERS
    ) -> fix.Message:
        """
        Send order mass status request
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_AF_6570.html
            - https://docs.deribit.com/test/#order-mass-status-request-af
        """
        message = fix.Message()
        header = message.getHeader()
        header.setField(fix.MsgType(fix.MsgType_OrderMassStatusRequest))
        if symbol is not None:
            message.setField(fix.Symbol(symbol))
        if exchange is not None:
            message.setField(fix.SecurityExchange(exchange))
        if account is not None:
            message.setField(fix.Account(account))
        message.setField(fix.MassStatusReqID(mass_status_req_id))
        message.setField(fix.MassStatusReqType(mass_status_req_type))
        self.send_message_to_session(message)
        return message

    def request_for_positions(
            self,
            exchange: str,
            account: str,
            pos_req_id: str,
            symbol=None,
            currency=None,
            pos_req_type=fix.PosReqType_POSITIONS,
            account_type=fix.AccountType_ACCOUNT_IS_CARRIED_ON_CUSTOMER_SIDE_OF_BOOKS,
            subscription_type=fix.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES
    ) -> fix.Message:
        """
        Send position request
            - https://www.onixs.biz/fix-dictionary/4.4/msgtype_an_6578.html
            - https://docs.deribit.com/#request-for-positions-an

        Use fix.SubscriptionRequestType_SNAPSHOT if positions should only be obtained once.
        """
        message = fix.Message()
        header = message.getHeader()
        header.setField(fix.MsgType(fix.MsgType_RequestForPositions))
        message.setField(fix.SecurityExchange(exchange))
        message.setField(fix.PosReqID(pos_req_id))
        message.setField(fix.PosReqType(pos_req_type))
        message.setField(fix.Account(account))
        message.setField(fix.AccountType(account_type))
        message.setField(fix.SubscriptionRequestType(subscription_type))
        if symbol is not None:
            message.setField(fix.Symbol(symbol))
        if currency is not None:
            message.setField(fix.Currency(currency))

        self.position_subscriptions[(pos_req_id, subscription_type)] = (datetime.utcnow(), [(exchange, symbol)])

        tx_time = fix.TransactTime()
        tx_time.setString(datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        message.setField(tx_time)
        cl_business_date = fix.ClearingBusinessDate()
        cl_business_date.setString(datetime.utcnow().strftime("%Y%m%d"))
        message.setField(cl_business_date)
        self.send_message_to_session(message)
        return message

    def trade_capture_report_request(
            self,
            trade_req_id: str,
            exchange=None,
            symbol=None,
            trade_request_type=None,
            subscription_type=fix.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES
    ) -> fix.Message:
        message = fix.Message()
        header = message.getHeader()
        header.setField(fix.MsgType(fix.MsgType_TradeCaptureReportRequest))
        message.setField(fix.TradeRequestID(trade_req_id))
        if exchange is not None:
            message.setField(fix.SecurityExchange(exchange))
        if symbol is not None:
            message.setField(fix.Symbol(symbol))

        if exchange is None and symbol is None:
            trade_request_type = fix.TradeRequestType_ALL_TRADES
        elif exchange is not None or symbol is not None:
            trade_request_type = fix.TradeRequestType_MATCHED_TRADES_MATCHING_CRITERIA_PROVIDED_ON_REQUEST \
                if trade_request_type is None else trade_request_type
        else:
            raise ValueError(f"trade_capture_report_request - Incorrect request type {trade_request_type} "
                             f"for exchange {exchange} and symbol {symbol}")
        message.setField(fix.TradeRequestType(trade_request_type))
        message.setField(fix.SubscriptionRequestType(subscription_type))

        self.trade_report_subscriptions[(trade_req_id, subscription_type)] = (datetime.utcnow(), [(exchange, symbol)])

        self.send_message_to_session(message)
        return message

    def security_list_request(self, req_id="req_id", exchange: str = None,
                              subscription_request_type=fix.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES,
                              security_list_request_type=fix.SecurityListRequestType_ALL_SECURITIES) -> fix.Message:
        """
        Send security list request
        """
        message = fix.Message()
        header = message.getHeader()
        header.setField(fix.MsgType(fix.MsgType_SecurityListRequest))
        snd_time = fix.SendingTime()
        snd_time.setString(datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        message.setField(snd_time)
        if exchange is not None:
            message.setField(fix.SecurityExchange(exchange))
        if subscription_request_type is not None:
            message.setField(fix.SubscriptionRequestType(subscription_request_type))
        message.setField(fix.SecurityReqID(f"{req_id}_{self.next_request_id()}"))
        if security_list_request_type is not None:
            message.setField(fix.SecurityListRequestType(security_list_request_type))
        self.send_message_to_session(message)
        return message

    def security_definition_request(self, exchange: str, symbol: str, req_id="req_id",
                                    security_request_type=fix.SecurityRequestType_REQUEST_LIST_SECURITIES,
                                    subscription_request_type=None
                                    ) -> fix.Message:
        """
        Send security definition request
        """
        message = fix.Message()
        header = message.getHeader()
        header.setField(fix.MsgType(fix.MsgType_SecurityDefinitionRequest))
        snd_time = fix.SendingTime()
        snd_time.setString(datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        message.setField(snd_time)
        message.setField(fix.SecurityReqID(f"{req_id}_{self.next_request_id()}"))
        message.setField(fix.SecurityRequestType(security_request_type))
        if symbol is not None:
            message.setField(fix.Symbol(symbol))
        if exchange is not None:
            message.setField(fix.SecurityExchange(exchange))
        if subscription_request_type is not None:
            message.setField(fix.SubscriptionRequestType(subscription_request_type))
        self.send_message_to_session(message)
        return message

    def market_data_request(
            # exchange_symbol_pairs is list of tuple , tuple[0] is string of exchange name , and tuple[1] is string
            # of symbol
            self, exchange_symbol_pairs: List[Tuple[str, str]], market_depth: int = 0,
            content: str = "both", req_id: str = None,
            subscription_request_type: int = fix.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES,
            is_aggregated_book: bool = True
    ) -> fix.Message:
        """
        Send request for book and/or trades. Full book is obtained with market_depth=0
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_V_86.html
            - https://www.onixs.biz/fix-dictionary/4.4/tagNum_264.html
        """
        req_id = f"req_id_{self.next_request_id()}" if req_id is None else req_id
        message = fix.Message()
        header = message.getHeader()
        header.setField(fix.MsgType(fix.MsgType_MarketDataRequest))
        snd_time = fix.SendingTime()
        snd_time.setString(datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3])
        message.setField(snd_time)
        message.setField(fix.MDReqID(req_id))
        message.setField(fix.SubscriptionRequestType(subscription_request_type))
        message.setField(fix.MarketDepth(market_depth))
        message.setField(fix.MDUpdateType(fix.MDUpdateType_INCREMENTAL_REFRESH))
        message.setField(fix.AggregatedBook(is_aggregated_book))

        self.market_data_subscriptions[(req_id, subscription_request_type)] = (datetime.utcnow(), exchange_symbol_pairs)

        if content == "book":
            message.setField(fix.NoMDEntryTypes(2))
            group = fix44.MarketDataRequest().NoMDEntryTypes()
            group.setField(fix.MDEntryType(fix.MDEntryType_BID))
            group.setField(fix.MDEntryType(fix.MDEntryType_OFFER))
            message.addGroup(group)
        elif content == "trade":
            message.setField(fix.NoMDEntryTypes(1))
            group = fix44.MarketDataRequest().NoMDEntryTypes()
            group.setField(fix.MDEntryType(fix.MDEntryType_TRADE))
            message.addGroup(group)
        elif content == "both":
            message.setField(fix.NoMDEntryTypes(3))
            group = fix44.MarketDataRequest().NoMDEntryTypes()
            group.setField(fix.MDEntryType(fix.MDEntryType_BID))
            group.setField(fix.MDEntryType(fix.MDEntryType_OFFER))
            group.setField(fix.MDEntryType(fix.MDEntryType_TRADE))
            message.addGroup(group)
        else:
            raise Exception(f"content {content} not supported")

        ns = len(exchange_symbol_pairs)
        message.setField(fix.NoRelatedSym(ns))  # tag 146
        group = fix44.MarketDataRequest().NoRelatedSym()
        for (exchange, symbol) in exchange_symbol_pairs:
            group.setField(fix.Symbol(symbol))
            group.setField(fix.SecurityExchange(exchange))
            message.addGroup(group)

        self.send_message_to_session(message)
        return message

    def get_account(self):
        return self.session_settings.get(self.session_id).getString("Account")

    def get_username(self):
        return self.session_settings.get(self.session_id).getString("Username")

    def get_market_data_subscriptions(self):
        return copy.deepcopy(self.market_data_subscriptions)

    def get_position_subscriptions(self):
        return copy.deepcopy(self.position_subscriptions)

    def get_trade_report_subscriptions(self):
        return copy.deepcopy(self.trade_report_subscriptions)

    def purge_fix_message_history(self):
        """
        Purge history to avoid growing memory footprint
        """
        self.received_app_message_history = []
        self.received_admin_message_history = []
        self.sent_app_message_history = []
        self.sent_admin_message_history = []
        self.logger.debug("Purge Plain FIX Message History In Base App")

    def get_fix_message_history(self, purge_history=False) -> Dict[str, List[str]]:
        history = {
            "received_app_message_history": self.received_app_message_history.copy(),
            "received_admin_message_history": self.received_admin_message_history.copy(),
            "sent_app_message_history": self.sent_app_message_history.copy(),
            "sent_admin_message_history": self.sent_admin_message_history.copy(),
        }
        if purge_history:
            self.purge_fix_message_history()
        return history

    def save_fix_message_history(self, path=None, fmt="csv", pre=None, post=None, purge_history=False):
        if path is None:
            path = self.export_dir
        msg_hist = self.get_fix_message_history(purge_history)
        if sum([len(hist) for hist in msg_hist.values()]) > 0:
            self.logger.info(f"saving FIX message history to {path}")

            def filename(name):
                pre_ = pre + "_" if pre is not None else ""
                _post = "_" + post if post is not None else ""
                return os.path.join(path, f"{pre_}{name}{_post}.{fmt}")

            def save(fix_msg_history, name):
                with open(make_dirs_for_file(filename(name)), "w") as f:
                    for row in fix_msg_history:
                        f.write(row + "\n")

            for key, history in msg_hist.items():
                save(history, key)
