from enum import Enum
from logging import Logger
from typing import Tuple, Optional, Set

import pandas as pd
import quickfix as fix
from phx.fix.app import AppRunner
from phx.fix.utils import fix_message_string, flip_trading_dir
from phx.utils import TO_PIPS
from scipy.stats import bernoulli

from phx.strategy.base import StrategyBase, RoundingDirection
# from phx.strategy.base.types import Ticker


class TradingMode(str, Enum):
    MARKET_ORDERS = "market_orders"
    AGGRESSIVE_LIMIT_ORDERS = "aggressive_limit_orders"


class DebitTestStrategy(StrategyBase):
    def __init__(
            self,
            app_runner: AppRunner,
            config: dict,
            logger: Logger = None,
    ):
        trading_symbols = [("deribit", "BTC-PERPETUAL")]

        super().__init__(
            app_runner,
            config,
            trading_symbols,
            trading_symbols,
            logger,
        )

        self.quantity = config["quantity"]
        self.trade_interval = pd.Timedelta(config.get("trade_interval", "5s"))
        self.trading_mode = TradingMode.AGGRESSIVE_LIMIT_ORDERS
        self.aggressiveness_in_pips = 2
        self.current_trading_direction = fix.Side_BUY
        self.last_trade_time = pd.Timestamp(0, tz="UTC")

    def get_symbols_to_trade(self):
        return list(self.trading_symbols)

    def get_trading_direction(self):
        direction = self.current_trading_direction
        self.current_trading_direction = flip_trading_dir(self.current_trading_direction)
        return direction

    def submit_market_orders(self):
        FN = "submit_market_orders"
        direction = self.get_trading_direction()
        symbols = self.get_symbols_to_trade()
        account = self.fix_interface.get_account()
        for exchange, symbol in symbols:
            key = exchange, symbol
            book = self.order_books.get(key, None)
            if book is not None and book.mid_price is not None:
                order, msg = self.fix_interface.new_order_single(
                    exchange, symbol, direction, self.quantity, ord_type=fix.OrdType_MARKET, account=account
                )
                self.logger.info(
                    f"{FN}: {exchange} Symbol {symbol}: MKT {direction} order submitted {fix_message_string(msg)}"
                )
            else:
                self.logger.info(f"{FN}: {exchange} Symbol {symbol}: mid-price missing!")

    def submit_limit_orders(self):
        direction = self.get_trading_direction()
        symbols = self.get_symbols_to_trade()
        account = self.fix_interface.get_account()
        for exchange, symbol in symbols:
            key = exchange, symbol
            book = self.order_books.get(key, None)
            if book is not None:
                top_bid = book.top_bid_price
                top_ask = book.top_ask_price
                if top_bid and top_ask:
                    if direction == fix.Side_SELL:
                        price = self.round_down(top_bid * (1 - TO_PIPS * self.aggressiveness_in_pips), key, 1)
                        dir_str = "sell"
                    else:
                        price = self.round_up(top_ask * (1 + TO_PIPS * self.aggressiveness_in_pips), key, 1)
                        dir_str = "buy"
                    self.logger.info(
                        f"{exchange} Symbol {symbol}: top of book {(top_bid, top_ask)} => "
                        f"aggressive {dir_str} order {self.quantity} @ {price}"
                    )
                    order, msg = self.fix_interface.new_order_single(
                        exchange, symbol, direction, self.quantity, price, ord_type=fix.OrdType_LIMIT, account=account
                    )
                    self.logger.info(
                        f"{exchange} Symbol {symbol}: aggressive {dir_str} order submitted:{fix_message_string(msg)}"
                    )
                else:
                    self.logger.info(f"order book for {exchange}/{symbol} bid:{top_bid} ask:{top_ask}")
            else:
                self.logger.warning(f"no order book for {exchange}/{symbol}")

    def trade(self):
        now = pd.Timestamp.utcnow()
        if now > self.last_trade_time + self.trade_interval:
            self.logger.info(f"====> run trading step {now}")
            self.last_trade_time = now
            if self.trading_mode == TradingMode.MARKET_ORDERS:
                self.submit_market_orders()
                self.trading_mode = TradingMode.AGGRESSIVE_LIMIT_ORDERS
            elif self.trading_mode == TradingMode.AGGRESSIVE_LIMIT_ORDERS:
                self.submit_limit_orders()
                self.trading_mode = TradingMode.MARKET_ORDERS
