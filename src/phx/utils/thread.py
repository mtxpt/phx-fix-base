import time
from datetime import datetime, timedelta
from threading import Event, Thread
from typing import Any, Callable, Union

import pandas as pd


def sleep_until(now: Union[datetime, pd.Timestamp], target: Union[datetime, pd.Timestamp]):
    now = pd.Timestamp(now)
    target = pd.Timestamp(target)
    delta = target - now
    if delta > timedelta(0):
        time.sleep(delta.total_seconds())
        return True


def set_and_notify(self):
    self._set()
    self.changed()


def clear_and_notify(self):
    self._clear()
    self.changed()


def notifying_event(e, changed_callback):
    e._set = e.set
    e._clear = e.clear
    e.changed = changed_callback
    e.set = lambda: set_and_notify(e)
    e.clear = lambda: clear_and_notify(e)


def or_event(*events):
    event = Event()

    def changed():
        bools = [ev.is_set() for ev in events]
        if any(bools):
            event.set()
        else:
            event.clear()
    for e in events:
        notifying_event(e, changed)
    changed()
    return event


def and_event(*events):
    event = Event()

    def changed():
        bools = [ev.is_set() for ev in events]
        if all(bools):
            event.set()
        else:
            event.clear()
    for e in events:
        notifying_event(e, changed)
    changed()
    return event


class AlignedRepeatingTimer(Thread):
    """
    Usage for example as follows:

        args = {
            "exchange": exchange,
            "symbol": symbol,
            "pips": self.pips,
            "quantity": self.quantity,
        }
        timer = AlignedRepeatingTimer(
            interval=self.quoting_delay,
            alignment_freq="S",
            function=self.quote, kwargs=args)
        timer.start()

    """
    def __init__(
            self,
            interval: pd.Timedelta,
            function: Callable,
            name: str = "AlignedRepeatingTimer",
            alignment_freq: str = "1s",
            args=None,
            kwargs=None,
    ):
        Thread.__init__(self, name=name)
        self.interval: pd.Timedelta = interval
        self.alignment_freq: str = alignment_freq
        self.function = function
        self.args = args if args is not None else []
        self.kwargs = kwargs if kwargs is not None else {}
        self.finished = Event()

    def cancel(self):
        self.finished.set()

    def run(self):
        now = pd.Timestamp.now()
        start = now.floor(freq=self.alignment_freq) + self.interval
        delay = (start - now).total_seconds()
        self.finished.wait(delay)
        while not self.finished.is_set():
            self.function(*self.args, **self.kwargs)
            now = pd.Timestamp.now()
            while start <= now:
                start += self.interval
            delay = (start - now).total_seconds()
            self.finished.wait(delay)
