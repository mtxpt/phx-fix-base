import quickfix as fix


class Message(object):
    def __init__(self):
        pass


class Create(Message):

    def __init__(self, session_id):
        self.session_id = session_id


class Logon(Message):

    def __init__(self, session_id):
        self.session_id = session_id


class Logout(Message):

    def __init__(self, session_id):
        self.session_id = session_id


class Heartbeat(Message):

    def __init__(self, receive_ts):
        self.receive_ts = receive_ts


class GatewayNotReady(Message):

    def __init__(self):
        pass


class PositionRequestAck(Message):

    def __init__(self, status):
        self.status = status

    def completed(self):
        return self.status == fix.PosReqStatus_COMPLETED

    def rejected(self):
        return self.status == fix.PosReqStatus_REJECTED


class TradeCaptureReportRequestAck(Message):

    def __init__(self, symbol, result, status):
        self.symbol = symbol
        self.result = result
        self.status = status


class OrderMassCancelReport(Message):

    def __init__(self, exchange, symbol, response, request_type, reject_reason, text):
        self.exchange = exchange
        self.symbol = symbol
        self.response = response
        self.response = response
        self.request_type = request_type
        self.reject_reason = reject_reason
        self.text = text


class BusinessMessageReject(Message):

    def __init__(self, ref_msg_seq_num, ref_msg_type, reason, text):
        self.ref_msg_seq_num = ref_msg_seq_num
        self.ref_msg_type = ref_msg_type
        self.reason = reason
        self.text = text


class Reject(Message):

    def __init__(self, ref_msg_seq_num, ref_msg_type, ref_tag, reason, text):
        self.ref_msg_seq_num = ref_msg_seq_num
        self.ref_msg_type = ref_msg_type
        self.ref_tag = ref_tag
        self.reason = reason
        self.text = text


class MarketDataRequestReject(Message):

    def __init__(self, reason, text):
        self.reason = reason
        self.text = text


