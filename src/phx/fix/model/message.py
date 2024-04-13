import quickfix as fix


class Message(object):
    def __init__(self):
        pass


class Create(Message):

    def __init__(self, session_id: str):
        Message.__init__(self)
        self.session_id: str = session_id

    def __str__(self):
        return f"Create[session_id={self.session_id}]"


class Logon(Message):

    def __init__(self, session_id: str):
        Message.__init__(self)
        self.session_id: str = session_id

    def __str__(self):
        return f"Logon[session_id={self.session_id}]"


class Logout(Message):

    def __init__(self, session_id: str):
        Message.__init__(self)
        self.session_id: str = session_id

    def __str__(self):
        return f"Logout[session_id={self.session_id}]"


class Heartbeat(Message):

    def __init__(self, receive_ts):
        Message.__init__(self)
        self.receive_ts = receive_ts

    def __str__(self):
        return f"Heartbeat[receive_ts={self.receive_ts}]"


class GatewayNotReady(Message):

    def __init__(self, report):
        Message.__init__(self)
        self.report = report

    def __str__(self):
        return f"GatewayNotReady[{self.report}]"


class NotConnected(Message):

    def __init__(self, report):
        Message.__init__(self)
        self.report = report

    def __str__(self):
        return f"NotConnected[{self.report}]"


class PositionRequestAck(Message):

    def __init__(self, status):
        Message.__init__(self)
        self.status = status

    def completed(self):
        return self.status == fix.PosReqStatus_COMPLETED

    def rejected(self):
        return self.status == fix.PosReqStatus_REJECTED

    def __str__(self):
        return f"PositionRequestAck[status={self.status}]"


class TradeCaptureReportRequestAck(Message):

    def __init__(self, symbol, result, status):
        Message.__init__(self)
        self.symbol = symbol
        self.result = result
        self.status = status

    def __str__(self):
        return (f"TradeCaptureReportRequestAck["
                f"symbol={self.symbol}, "
                f"result={self.result}, "
                f"status={self.status}"
                f"]")


class OrderMassCancelReport(Message):

    def __init__(self, exchange, symbol, response, request_type, reject_reason, text):
        Message.__init__(self)
        self.exchange = exchange
        self.symbol = symbol
        self.response = response
        self.request_type = request_type
        self.reject_reason = reject_reason
        self.text = text

    def __str__(self):
        return (f"TradeCaptureReportRequestAck["
                f"exchange={self.exchange}, "
                f"symbol={self.symbol}, "
                f"response={self.response}, "
                f"request_type={self.request_type}, "
                f"reject_reason={self.reject_reason}, "
                f"text={self.text}"
                f"]")


class BusinessMessageReject(Message):

    def __init__(self, ref_msg_seq_num, ref_msg_type, reason, text):
        Message.__init__(self)
        self.ref_msg_seq_num = ref_msg_seq_num
        self.ref_msg_type = ref_msg_type
        self.reason = reason
        self.text = text

    def __str__(self):
        return (f"BusinessMessageReject["
                f"ref_msg_seq_num={self.ref_msg_seq_num}, "
                f"ref_msg_type={self.ref_msg_type}, "
                f"reason={self.reason}, "
                f"text={self.text}"
                f"]")


class Reject(Message):

    def __init__(self, ref_msg_seq_num, ref_msg_type, ref_tag, reason, text):
        Message.__init__(self)
        self.ref_msg_seq_num = ref_msg_seq_num
        self.ref_msg_type = ref_msg_type
        self.ref_tag = ref_tag
        self.reason = reason
        self.text = text

    def __str__(self):
        return (f"Reject["
                f"ref_msg_seq_num={self.ref_msg_seq_num}, "
                f"ref_msg_type={self.ref_msg_type}, "
                f"ref_tag={self.ref_tag}, "
                f"reason={self.reason}, "
                f"text={self.text}"
                f"]")


class OrderCancelReject(Message):
    def __init__(self, ord_id: str, cl_ord_id, orig_cl_ord_id, reason, text):
        super().__init__()
        self.ord_id = ord_id
        self.cl_ord_id = cl_ord_id
        self.orig_cl_ord_id = orig_cl_ord_id
        self.reason = reason
        self.text = text

    def __str__(self):
        return (
            "OrderCancelReject["
            f"ord_id={self.ord_id}, "
            f"cl_ord_id={self.cl_ord_id}, "
            f"orig_cl_ord_id={self.orig_cl_ord_id}, "
            f"reason='{self.reason}', "
            f"text='{self.text}'"
            "]"
        )

class MarketDataRequestReject(Message):

    def __init__(self, reason, text):
        Message.__init__(self)
        self.reason = reason
        self.text = text

    def __str__(self):
        return (f"MarketDataRequestReject["
                f"reason={self.reason}, "
                f"text={self.text}"
                f"]")
