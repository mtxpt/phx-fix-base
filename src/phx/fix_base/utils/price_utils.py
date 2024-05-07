import logging
import math
from enum import IntEnum
from typing import Optional


class RoundingDirection(IntEnum):
    UP = 0
    DOWN = 1


def price_round(
    price: float,
    direction: RoundingDirection,
    min_tick_size: float,
) -> Optional[float]:
    if price >= 0 and min_tick_size > 0:
        if direction == RoundingDirection.DOWN:
            return math.floor(price / min_tick_size) * min_tick_size
        elif direction == RoundingDirection.UP:
            return math.ceil(price / min_tick_size) * min_tick_size
        else:
            return None
    else:
        return None


def price_round_down(
    price: float,
    min_tick_size: float,
) -> Optional[float]:
    return price_round(price, RoundingDirection.DOWN, min_tick_size)


def price_round_up(
    price: float,
    min_tick_size: float,
) -> Optional[float]:
    return price_round(price, RoundingDirection.UP, min_tick_size)


def tick_round(
    price: float,
    min_tick_size: float,
) -> float:
    if min_tick_size <= 0.0:
        return round(price)
    else:
        rem = math.trunc((price % 1) / min_tick_size)
        return math.trunc(price) + rem * min_tick_size
