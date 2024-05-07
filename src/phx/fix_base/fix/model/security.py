from typing import Dict, Tuple

from phx.fix_base.fix.model.message import Message


class Security(object):
    def __init__(self, exchange, symbol, multiplier, min_trade_vol, min_price_increment):
        self.exchange = exchange
        self.symbol = symbol
        self.multiplier = multiplier
        self.min_trade_vol = min_trade_vol
        self.min_price_increment = min_price_increment

    def __str__(self):
        return (f"Security["
                f"exchange={self.exchange}, "
                f"symbol={self.symbol}, "
                f"multiplier={self.multiplier}, "
                f"min_trade_vol={self.min_trade_vol} "
                f"min_price_increment={self.min_price_increment}"
                f"]")


class SecurityReport(Message):
    def __init__(self, securities: Dict[Tuple[str, str], Security]):
        Message.__init__(self)
        self.securities = securities

    def __str__(self):
        return (f"SecurityReport["
                f"securities={self.securities}"
                f"]")
