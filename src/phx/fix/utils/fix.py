import quickfix as fix
from phx.utils.utils import str_to_datetime


def flip_trading_dir(direction):
    return fix.Side_SELL if direction == fix.Side_BUY else fix.Side_BUY


def signed_value(side, value):
    if side == fix.Side_BUY:
        return value
    elif side == fix.Side_SELL:
        return -value
    else:
        return None


def fix_message_string(message: fix.Message, delimiter='|'):
    m = message.toString().replace('\x01', delimiter)
    if len(m) >= 2:
        return m[:-2]
    return m


def extract_message_field_value(fix_api_object: fix.FieldBase, message, field_type: str = ""):
    if field_type == "msg_type":
        message.getHeader().getField(fix_api_object)
        return fix_api_object.getValue()
    if field_type == "datetime":
        message.getHeader().getField(fix_api_object)
        return str_to_datetime(fix_api_object.getString())
    if message.isSetField(fix_api_object.getField()):
        message.getField(fix_api_object)
        if field_type == "":
            return fix_api_object.getValue()
        elif field_type == "str":
            return str(fix_api_object.getValue())
        elif field_type == "int":
            try:
                return int(fix_api_object.getValue())
            except:
                return None
        elif field_type == "float":
            try:
                return float(fix_api_object.getValue())
            except:
                return None
        elif field_type == "bool":
            try:
                value = fix_api_object.getValue()
                if isinstance(value, bool):
                    return value
                elif isinstance(value, str):
                    if value == "Y":
                        return True
                    elif value == "N":
                        return False
                    else:
                        raise ValueError("invalid boolean value")
            except:
                return None
    else:
        return None


def update_action_type_to_str(action) -> str:
    if action == fix.MDUpdateAction_NEW:
        return "NEW"
    elif action == fix.MDUpdateAction_CHANGE:
        return "CHANGE"
    elif action == fix.MDUpdateAction_DELETE:
        return "DELETE"
    else:
        return f"UpdateAction-{action}"


def entry_type_to_str(entry_type):
    if entry_type == fix.MDEntryType_BID:
        return "BID"
    elif entry_type == fix.MDEntryType_OFFER:
        return "OFFER"
    elif entry_type == fix.MDEntryType_TRADE:
        return "TRADE"
    else:
        return f"EntryType-{entry_type}"


session_reject_reason_dict = {
    0: "Invalid tag number",
    1: "Required tag missing",
    2: "Tag not defined for this message type",
    3: "Undefined Tag",
    4: "Tag specified without a value",
    5: "Value is incorrect (out of range) for this tag",
    6: "Incorrect data format for value",
    7: "Decryption problem",
    8: "Signature <89> problem",
    9: "CompID problem",
    10: "SendingTime <52> accuracy problem",
    11: "Invalid MsgType <35>",
    12: "XML Validation error",
    13: "Tag appears more than once",
    14: "Tag specified out of required order",
    15: "Repeating group fields out of order",
    16: "Incorrect NumInGroup count for repeating group",
    17: "Non \"Data\" value includes field delimiter (<SOH> character)",
    99: "Other"
}


def session_reject_reason_to_string(reason):
    what = session_reject_reason_dict.get(reason, None)
    what = what if what is not None else "Unknown"
    return what


order_type_dict = {
    "1": "Market",
    "2": "Limit",
    "3": "Stop",
    "4": "Stop limit",
    "5": "Market on close",                   # (No longer used)
    "6": "With or without",
    "7": "Limit or better",                   # (Deprecated)
    "8": "Limit with or without",
    "9": "On basis",
    "A": "On close",                          # (No longer used)
    "B": "Limit on close",                    # (No longer used)
    "C": "Forex - Market",                    # (No longer used)
    "D": "Previously quoted",
    "E": "Previously indicated",
    "F": "Forex - Limit",                     # (No longer used)
    "G": "Forex - Swap",
    "H": "Forex - Previously Quoted",         # (No longer used)
    "I": "Funari",                            # (Limit Day Order with unexecuted portion handled as Market On Close. E.g. Japan)
    "J": "Market If Touched",                 # (MIT)
    "K": "Market with Leftover as Limit",     # (market order then unexecuted quantity becomes limit order at last price)
    "L": "Previous Fund Valuation Point",     # (Historic pricing) (for CIV)
    "M": "Next Fund Valuation Point",         # (Forward pricing) (for CIV)
    "P": "Pegged"
}


def order_type_to_string(order_type):
    what = order_type_dict.get(str(order_type), None)
    what = what if what is not None else "Unknown"
    return what


time_in_force_dict = {
    "0": "Day",
    "1": "Good Till Cancel (GTC)",
    "2": "At the Opening (OPG)",
    "3": "Immediate or Cancel (IOC)",
    "4": "Fill or Kill (FOK)",
    "5": "Good Till Crossing (GTX)",
    "6": "Good Till Date",
    "7": "At the Close"
}


def time_in_force_to_string(tif):
    what = time_in_force_dict.get(str(tif), None)
    what = what if what is not None else "Unknown"
    return what


order_status_dict = {
    "0": "New",
    "1": "Partially filled",
    "2": "Filled",
    "3": "Done for day",
    "4": "Canceled",
    "5": "Replaced",                # Removed/Replaced
    "6": "Pending Cancel",          # e.g. result of Order Cancel Request <F>
    "7": "Stopped",
    "8": "Rejected",
    "9": "Suspended",
    "A": "Pending New",
    "B": "Calculated",
    "C": "Expired",
    "D": "Accepted for bidding",
    "E": "Pending Replace"          # e.g. result of Order Cancel/Replace Request <G>
}


def order_status_to_string(status):
    what = order_status_dict.get(str(status), None)
    what = what if what is not None else "Unknown"
    return what


side_dict = {
    "1": "Buy",
    "2": "Sell",
    "3": "Buy minus",
    "4": "Sell plus",
    "5": "Sell short",
    "6": "Sell short exempt",
    "7": "Undisclosed",   # (valid for IOI and List Order messages only)
    "8": "Cross",         # (orders where counterparty is an exchange, valid for all messages except IOIs)
    "9": "Cross short",
    "A": "Cross short exempt",
    "B": "As Defined",    # (for use with multi-leg instruments)
    "C": "Opposite",      #(for use with multi-leg instruments)
    "D": "Subscribe",     # (e.g. CIV)
    "E": "Redeem",        # (e.g. CIV)
    "F": "Lend",          # (FINANCING - identifies direction of collateral)
    "G": "Borrow"         # (FINANCING - identifies direction of collateral)
}


def side_to_string(side):
    what = side_dict.get(str(side), None)
    what = what if what is not None else "Unknown"
    return what


exec_type_dict = {
    "0": "New",
    "1": "Partial fill",      # (Replaced)
    "2": "Fill",              # (Replaced)
    "3": "Done for day",
    "4": "Canceled",
    "5": "Replaced",
    "6": "Pending Cancel",    # (e.g. result of Order Cancel Request <F>)
    "7": "Stopped",
    "8": "Rejected",
    "9": "Suspended",
    "A": "Pending New",
    "B": "Calculated",
    "C": "Expired",
    "D": "Restated",          # (Execution Report <8> sent unsolicited by sellside with ExecRestatementReason <378> set)
    "E": "Pending Replace",   # (e.g. result of Order Cancel/Replace Request <G>)
    "F": "Trade",             # (partial fill or fill)
    "G": "Trade Correct",     # (formerly an ExecTransType <20>)
    "H": "Trade Cancel",      # (formerly an ExecTransType <20>)
    "I": "Order Status"       # (formerly an ExecTransType <20>)
}


def exec_type_to_string(exec_type):
    what = exec_type_dict.get(str(exec_type), None)
    what = what if what is not None else "Unknown"
    return what


msg_type_dict = {
    "7": "Advertisement",
    "J": "Allocation Instruction",
    "P": "Allocation Instruction Ack",
    "AS": "Allocation Report",
    "AT": "Allocation Report Ack",
    "AW": "Assignment Report",
    "k": "Bid Request",
    "l": "Bid Response",
    "j": "Business Message Reject",
    "AY": "Collateral Assignment",
    "BB": "Collateral Inquiry",
    "BG": "Collateral Inquiry Ack",
    "BA": "Collateral Report",
    "AX": "Collateral Request",
    "AZ": "Collateral Response",
    "AK": "Confirmation",
    "AU": "Confirmation Ack",
    "BH": "Confirmation Request",
    "t": "Cross Order Cancel/Replace Request",
    "u": "Cross Order Cancel Request",
    "AA": "Derivative Security List",
    "z": "Derivative Security List Request",
    "Q": "Don't Know Trade",
    "C": "Email",
    "8": "Execution Report",
    "0": "Heartbeat",
    "6": "IOI",
    "K": "List Cancel Request",
    "L": "List Execute",
    "N": "List Status",
    "M": "List Status Request",
    "m": "List Strike Price",
    "A": "Logon",
    "5": "Logout",
    "X": "Market Data - Incremental Refresh",
    "V": "Market Data Request",
    "Y": "Market Data Request Reject",
    "W": "Market Data - Snapshot/Full Refresh",
    "i": "Mass Quote",
    "b": "Mass Quote Acknowledgement",
    "AC": "Multileg Order Cancel/Replace",
    "BC": "Network Counterparty System Status Request",
    "BD": "Network Counterparty System Status Response",
    "s": "New Order Cross",
    "E": "New Order List",
    "AB": "New Order Multileg",
    "D": "New Order Single",
    "B": "News",
    "G": "Order Cancel/Replace Request",
    "9": "Order Cancel Reject",
    "F": "Order Cancel Request",
    "r": "Order Mass Cancel Report",
    "q": "Order Mass Cancel Request",
    "AF": "Order Mass Status Request",
    "H": "Order Status Request",
    "AM": "Position Maintenance Report",
    "AL": "Position Maintenance Request",
    "AP": "Position Report",
    "S": "Quote",
    "Z": "Quote Cancel",
    "R": "Quote Request",
    "AG": "Quote Request Reject",
    "AJ": "Quote Response",
    "AI": "Quote Status Report",
    "a": "Quote Status Request",
    "o": "Registration Instructions",
    "p": "Registration Instructions Response",
    "3": "Reject",
    "AN": "Request For Positions",
    "AO": "Request for Positions Ack",
    "2": "Resend Request",
    "AH": "RFQ Request",
    "d": "Security Definition",
    "c": "Security Definition Request",
    "y": "Security List",
    "x": "Security List Request",
    "f": "Security Status",
    "e": "Security Status Request",
    "v": "Security Type Request",
    "w": "Security Types",
    "4": "Sequence Reset",
    "AV": "Settlement Instruction Request",
    "T": "Settlement Instructions",
    "1": "Test Request",
    "AE": "Trade Capture Report",
    "AR": "Trade Capture Report Ack",
    "AD": "Trade Capture Report Request",
    "AQ": "Trade Capture Report Request Ack",
    "h": "Trading Session Status",
    "g": "Trading Session Status Request",
    "BE": "User Request",
    "BF": "User Response",
    "n": "XML Message",
}


def msg_type_to_string(msg_type):
    what = msg_type_dict.get(str(msg_type), None)
    what = what if what is not None else "Unknown"
    return what


def cxl_rej_response_to_to_string(clx):
    if clx == fix.CxlRejResponseTo_ORDER_CANCEL_REQUEST:
        return "ORDER_CANCEL_REQUEST"
    elif clx == fix.CxlRejResponseTo_ORDER_CANCEL_REPLACE_REQUEST:
        return "ORDER_CANCEL_REPLACE_REQUEST"
    else:
        return "Unknown"


cxl_rej_reason_dict = {
    0: "Too late to cancel",
    1: "Unknown order",
    2: "Broker / Exchange Option",
    3: "Order already in Pending Cancel or Pending Replace status",
    4: "Unable to process Order Mass Cancel Request <q>",
    5: "OrigOrdModTime <586> did not match last TransactTime <60> of order",
    6: "Duplicate ClOrdID <11> received",
    99: "Other"
}


def cxl_rej_reason_to_string(clx: int):
    what = cxl_rej_reason_dict.get(clx, None)
    what = what if what is not None else "Unknown"
    return what


mass_cancel_request_type_dict = {
    "1": "Cancel orders for a security",
    "2": "Cancel orders for an Underlying security",
    "3": "Cancel orders for a Product",
    "4": "Cancel orders for a CFICode",
    "5": "Cancel orders for a SecurityType",
    "6": "Cancel orders for a trading session",
    "7": "Cancel all orders",
}


def mass_cancel_request_type_to_string(t: str):
    what = mass_cancel_request_type_dict.get(t, None)
    what = what if what is not None else "Unknown"
    return what


mass_cancel_response_dict = {
    "0": "Cancel Request Rejected - See MassCancelRejectReason",
    "1": "Cancel orders for a security",
    "2": "Cancel orders for an Underlying security",
    "3": "Cancel orders for a Product",
    "4": "Cancel orders for a CFICode",
    "5": "Cancel orders for a SecurityType",
    "6": "Cancel orders for a trading session",
    "7": "Cancel all orders",
}


def mass_cancel_response_to_string(response: str):
    what = mass_cancel_response_dict.get(response, None)
    what = what if what is not None else "Unknown"
    return what


mass_cancel_reject_reason_dict = {
    0: "Mass Cancel Not Supported",
    1: "Invalid or unknown Security",
    2: "Invalid or unknown Underlying security",
    3: "Invalid or unknown Product",
    4: "Invalid or unknown CFICode",
    5: "Invalid or unknown SecurityType",
    6: "Invalid or unknown trading session",
    99: "Other",
}


def mass_cancel_reject_reason_to_string(reason_code: int):
    what = mass_cancel_reject_reason_dict.get(reason_code, None)
    what = what if what is not None else "Unknown"
    return what


class Types(object):
    Logon = 'A'
    Heartbeat = '0'
    TestRequest = '1'
    Logout = '5'
    ResendRequest = '2'
    Reject = '3'
    SequenceReset = '4'
    MarketDataRequest = 'V'
    MarketDataSnapshot = 'W'
    MarketDataRefresh = 'X'
    NewOrderSingle = 'D'
    ListOrder = 'E'
    OrderCancel = 'F'
    OrderCancelReplace = 'G'
    DontKnowTrade = 'Q'
    OrderStatus = 'H'
    ExecutionReport = '8'
    OrderCancelReject = '9'
    BusinessMessageReject = 'j'
    PositionRequest = 'AN'
    PositionReport = 'AP'


__SOH__ = chr(1)


def build_checksum(message):
    checksum = sum([ord(i) for i in list(message)]) % 256
    return make_pair((10, str(checksum).zfill(3)))


def make_pair(pair):
    return str(pair[0]) + "=" + str(pair[1]) + __SOH__


def dict_to_fix_dict(d: dict) -> fix.Dictionary:
    fd = fix.Dictionary()
    for key, value in d.items():
        if isinstance(value, str):
            fd.setString(key, value)
        elif isinstance(value, int):
            fd.setInt(key, int(value))
        elif isinstance(value, bool):
            fd.setBool(key, value)
        elif isinstance(value, float):
            fd.setDouble(key, value)
        else:
            fd.setString(key, str(value))
    return fd


def fix_session_default_config(file_log_path="./logs/"):
    """
    Settings that apply to all the sessions
    """
    return {
        "DefaultApplVerID": "FIX.4.4",
        "ConnectionType": "initiator",
        "FileLogPath": file_log_path,
        "StartTime": "00:00:00",
        "EndTime": "00:00:00",
        "NonStopSession": "N",
        "UseDataDictionary": "Y",
        "ReconnectInterval": 60,
        "LogoutTimeout": 5,
        "LogonTimeout": 30,
        "ResetOnLogon": "Y",
        "ResetOnLogout": "Y",
        "ResetOnDisconnect": "Y",
        "SendRedundantResendRequests": "Y",
        "SocketNodelay": "N",
        "PersistMessages": "Y",
        "CheckLatency": "Y",
        "ValidateUserDefinedFields": "N",
        "AllowUnknownMsgFields": "Y",
    }


def fix_session_config(
        sender_comp_id,
        target_comp_id,
        user_name,
        password,
        auth_by_key=False,
        begin_string="FIX.4.4",
        socket_connect_port="1238",
        socket_connect_host="127.0.0.1",
        data_dictionary="fix_spec/FIX44.xml",
        file_store_path="./sessions/",
        account="A1"
):
    return {
        "BeginString": begin_string,
        "SenderCompID": sender_comp_id,
        "TargetCompID": target_comp_id,
        "Username": user_name,
        "Password": password,
        "AuthenticateByKey": "Y" if auth_by_key else "N",
        "HeartBtInt": 30,
        "SocketConnectPort": socket_connect_port,
        "SocketConnectHost": socket_connect_host,
        "DataDictionary": data_dictionary,
        "FileStorePath": file_store_path,
        "Account": account,
    }


BeginString = 8
BodyLength = 9
MsgType = 35
SenderCompID = 49
TargetCompID = 56
TargetSubID = 57
SenderSubID = 50
MsgSeqNum = 34
SendingTime = 52
CheckSum = 10
TestReqID = 112
EncryptMethod = 98
HeartBtInt = 108
ResetSeqNum = 141
Username = 553
Password = 554
Text = 58
BeginSeqNo = 7
EndSeqNo = 16
GapFillFlag = 123
NewSeqNo = 36
MDReqID = 262
SubscriptionRequestType = 263
MarketDepth = 264
MDUpdateType = 265
NoMDEntryTypes = 267
NoMDEntries = 268
MDEntryType = 269
NoRelatedSym = 146
Symbol = 55
MDEntryPx = 270
MDUpdateAction = 279
MDEntryID = 278
MDEntrySize = 271
ClOrdID = 11
Side = 54
TransactTime = 60
OrderQty = 38
OrdType = 40
Price = 44
StopPx = 99
TimeInForce = 59
ExpireTime = 126
PosMaintRptID = 721
OrderID = 37
ExecType = 150
OrdStatus = 39
AvgPx = 6
LeavesQty = 151
CumQty = 14
Currency = 15
ExecID = 17
ExecRefID = 19
ExecTransType=20
OnBehalfOfSubID = 116
OnBehalfOfCompID = 115
OrigClOrdID = 41
OrdRejReason = 103
DeliverToCompID = 128
DeliverToSubID = 129
PossDupFlag = 43
PossResend = 97
OrigSendingTime = 122
ClientID = 109
Account = 1
Commission = 12
CommType = 13
SettlmntTyp = 63
FutSettDate = 64
HandlInst = 21
ExecInst = 18
CxlType = 125
ExDestination = 100
IDSource = 22
SecurityType = 167
SecurityID = 48
SettlCurrency = 120
SecurityExchange = 207
DKReason = 127
RefSeqNum = 45
RefMsgType = 372
BusinessRejectRefID = 379
BusinessRejectReason = 380



