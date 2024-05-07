import abc
from typing import List, Dict, Tuple, AnyStr

import quickfix as fix

from phx.fix_base.fix.model.order import Order


class FixInterface(abc.ABC):

    @abc.abstractmethod
    def generate_msg_id(self) -> AnyStr:
        pass

    @abc.abstractmethod
    def generate_exec_id(self) -> AnyStr:
        pass

    @abc.abstractmethod
    def generate_cl_ord_id(self) -> AnyStr:
        pass

    @abc.abstractmethod
    def next_request_id(self) -> int:
        pass

    @abc.abstractmethod
    def new_order_single(
            self,
            exchange,
            symbol,
            side,
            order_qty,
            price=None,
            ord_type=fix.OrdType_LIMIT,
            tif=fix.TimeInForce_GOOD_TILL_CANCEL,
            account=None,
            min_qty=0,
            text="NewOrderSingle"
    ) -> Tuple[Order, fix.Message]:
        pass

    @abc.abstractmethod
    def order_cancel_request(
            self,
            order: Order
    ) -> Tuple[Order, fix.Message]:
        """
        Send order cancel request
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_F_70.html
            - https://docs.deribit.com/test/#order-cancel-request-f
        """
        pass

    @abc.abstractmethod
    def order_cancel_replace_request(
            self,
            order,
            order_qty,
            price=None,
            ord_type=None,
            exec_instr=None,
            account=None
    ) -> Tuple[Order, fix.Message]:
        """
        Send order cancel replace request
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_G_71.html
            - https://docs.deribit.com/test/#order-cancel-replace-request-g

        Side cannot be changed (however, some side modifications are allowed by FIX standard)
        """
        pass

    @abc.abstractmethod
    def order_mass_cancel_request(
            self,
            exchange=None,
            symbol=None,
            side=None,
            currency=None,
            security_type=None
    ) -> fix.Message:
        """
        Send order mass cancel request
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_q_113.html
            - https://docs.deribit.com/test/#order-mass-cancel-request-q
        """
        pass

    @abc.abstractmethod
    def order_status_request(
            self,
            exchange,
            symbol,
            cl_ord_id,
            side,
            order_id=None,
            account=None
    ) -> fix.Message:
        """
        Send order status request.
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_H_72.html
        """
        pass

    @abc.abstractmethod
    def order_mass_status_request(
            self,
            exchange,
            symbol,
            account=None,
            mass_status_req_id="working_orders",
            mass_status_req_type=fix.MassStatusReqType_STATUS_FOR_ALL_ORDERS
    ) -> fix.Message:
        """
        Send order mass status request
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_AF_6570.html
            - https://docs.deribit.com/test/#order-mass-status-request-af
        """
        pass

    @abc.abstractmethod
    def request_for_positions(
            self,
            exchange,
            account,
            pos_req_id,
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
        pass

    @abc.abstractmethod
    def trade_capture_report_request(
            self,
            trade_req_id,
            exchange=None,
            symbol=None,
            trade_request_type=None,
            subscription_type=fix.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES
    ) -> fix.Message:
        pass

    @abc.abstractmethod
    def security_list_request(self, req_id="req_id") -> fix.Message:
        """
        Send security list request
        """
        pass

    @abc.abstractmethod
    def security_definition_request(
            self,
            exchange,
            symbol,
            req_id="req_id"
    ) -> fix.Message:
        """
        Send security definition request
        """
        pass

    @abc.abstractmethod
    def market_data_request(
            self,
            exchange_symbol_pairs,
            market_depth=0,
            content="both",
            req_id=None,
            subscription_request_type=fix.SubscriptionRequestType_SNAPSHOT_PLUS_UPDATES
    ) -> fix.Message:
        """
        Send request for book and/or trades. Full book is obtained with market_depth=0
            - https://www.onixs.biz/fix-dictionary/4.4/msgType_V_86.html
            - https://www.onixs.biz/fix-dictionary/4.4/tagNum_264.html
        """
        pass

    @abc.abstractmethod
    def get_market_data_subscriptions(self):
        pass

    @abc.abstractmethod
    def get_position_subscriptions(self):
        pass

    @abc.abstractmethod
    def get_trade_report_subscriptions(self):
        pass

    @abc.abstractmethod
    def get_account(self):
        pass

    @abc.abstractmethod
    def get_username(self):
        pass

    @abc.abstractmethod
    def purge_fix_message_history(self):
        pass

    @abc.abstractmethod
    def get_fix_message_history(
            self,
            purge_history=False
    ) -> Dict[str, List[str]]:
        pass

    @abc.abstractmethod
    def save_fix_message_history(
            self,
            path=None,
            fmt="csv",
            pre=None,
            post=None,
            purge_history=False
    ):
        pass
