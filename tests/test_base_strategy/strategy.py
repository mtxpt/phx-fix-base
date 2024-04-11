import time
from enum import Enum
from logging import Logger
# from typing import Tuple, Optional, Set

import pandas as pd
import quickfix as fix
from phx.fix.app import AppRunner
from phx.fix.utils import fix_message_string, flip_trading_dir
from phx.utils import TO_PIPS

from phx.api import PhxApi
from phx.utils.price_utils import price_round_down, price_round_up

from phx.utils.time import utcnow


class TradingMode(str, Enum):
    MARKET_ORDERS = "market_orders"
    AGGRESSIVE_LIMIT_ORDERS = "aggressive_limit_orders"


class DeribitTestStrategy:
    def __init__(
            self,
            app_runner: AppRunner,
            config: dict,
            logger: Logger,
    ):
        self.logger = logger
        self.exchange = "deribit"
        self.trading_symbols = ["BTC-PERPETUAL", "ETH-PERPETUAL"]
        self.phx_api = PhxApi(
            app_runner=app_runner,
            config=config,
            exchange=self.exchange,
            mkt_symbols=self.trading_symbols,
            trading_symbols=self.trading_symbols,
            logger=logger,
        )
        # time settings
        self.start_time = utcnow()
        self.timeout = pd.Timedelta(config.get("timeout", "00:00:30"))
        self.last_trade_time = pd.Timestamp(0, tz="UTC")
        self.trade_interval = pd.Timedelta(config.get("trade_interval", "10s"))
        # order settings
        self.quantity = config["quantity"]
        self.trading_mode = TradingMode.AGGRESSIVE_LIMIT_ORDERS
        self.aggressiveness_in_pips = 2
        self.current_trading_direction = fix.Side_BUY

    def get_symbols_to_trade(self):
        return list(self.trading_symbols)

    def check_if_completed(self):
        now = utcnow()
        end = self.start_time + self.timeout
        completed = (now >= end)
        self.logger.info(
            f"check_if_completed: {self.start_time=} "
            f"{end=} {now=} {completed=}"
        )
        return completed

    def strategy_loop(self):
        fn = "strategy_loop"
        api_finished = False
        try:
            while not api_finished:
                if not self.phx_api.stop:
                    if self.phx_api.is_ready_to_trade():
                        self.trade()
                    time_is_out = self.check_if_completed()
                    if time_is_out:
                        self.phx_api.stop = True
                else:
                    self.logger.info(f"{fn}: API Stopped. Waiting to be finished...")
                self.logger.info(f"{fn}: sleep for {self.trade_interval.total_seconds()} seconds")
                time.sleep(self.trade_interval.total_seconds())
                api_finished = (self.phx_api.is_finished())
                if api_finished:
                    self.logger.info(f"{fn}: API finished.")
        except Exception as e:
            self.logger.error(f"{fn}: Exception: {e}")
            self.phx_api.stop = True

    def get_trading_direction(self):
        direction = self.current_trading_direction
        self.current_trading_direction = flip_trading_dir(self.current_trading_direction)
        return direction

    def submit_market_orders(self):
        fn = "submit_market_orders"
        direction = self.get_trading_direction()
        symbols = self.get_symbols_to_trade()
        account = self.phx_api.fix_interface.get_account()
        for symbol in symbols:
            ticker = (self.exchange, symbol)
            book = self.phx_api.order_books.get(ticker)
            if book and book.mid_price:
                order, msg = self.phx_api.fix_interface.new_order_single(
                    self.exchange, symbol, direction, self.quantity, ord_type=fix.OrdType_MARKET, account=account
                )
                self.logger.info(
                    f"{fn}: {self.exchange=}/{symbol=}: MKT {direction} order submitted {fix_message_string(msg)}"
                )
            else:
                self.logger.info(f"{fn}: {self.exchange=}/{symbol=}: mid-price missing!")

    def submit_limit_orders(self):
        fn = "submit_limit_orders"
        direction = self.get_trading_direction()
        symbols = self.get_symbols_to_trade()
        account = self.phx_api.fix_interface.get_account()
        for symbol in symbols:
            ticker = (self.exchange, symbol)
            book = self.phx_api.order_books.get(ticker, None)
            min_tick_size = self.phx_api.get_security_attribute(ticker, 'min_price_increment')
            if book and min_tick_size:
                top_bid = book.top_bid_price
                top_ask = book.top_ask_price
                if top_bid and top_ask:
                    if direction == fix.Side_SELL:
                        price = price_round_down(top_bid * (1 + TO_PIPS * self.aggressiveness_in_pips), min_tick_size)
                        dir_str = "sell"
                    else:
                        price = price_round_up(top_ask * (1 - TO_PIPS * self.aggressiveness_in_pips), min_tick_size)
                        dir_str = "buy"
                    self.logger.info(
                        f"{fn}: {self.exchange}/{symbol}: top of book {(top_bid, top_ask)} => "
                        f"passive {dir_str} order {self.quantity} @ {price}"
                    )
                    order, msg = self.phx_api.fix_interface.new_order_single(
                        self.exchange, symbol, direction, self.quantity, price, ord_type=fix.OrdType_LIMIT, account=account
                    )
                    self.logger.info(
                        f"{fn}: {self.exchange}/{symbol}: passive {dir_str} order submitted:{fix_message_string(msg)}"
                    )
                else:
                    self.logger.info(
                        f"{fn}: order book for {self.exchange=}/{symbol=} {top_bid=} {top_ask=}"
                    )
            else:
                self.logger.warning(
                    f"{fn}: empty either order book for {self.exchange=}/{symbol=} or {min_tick_size=}"
                )

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
