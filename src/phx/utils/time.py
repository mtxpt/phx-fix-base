import datetime

import pandas as pd


def utcnow() -> pd.Timestamp:
    return pd.Timestamp.utcnow()


def round_up_second(t: datetime.datetime) -> datetime.datetime:
    if t.microsecond >= 500_000:
        t += datetime.timedelta(seconds=1)
    return t.replace(microsecond=0)


def round_down_second(t: datetime.datetime) -> datetime.datetime:
    return t.replace(microsecond=0)


def round_down_seconds(t: datetime.datetime, multiple_secs=1) -> datetime.datetime:
    multiple_micros = multiple_secs*1000_000
    micros = t.microsecond + (t.minute*60 + t.second)*1000_000
    return t - datetime.timedelta(microseconds=micros % multiple_micros)


def round_down_minutes(t: datetime.datetime, multiple=1) -> datetime.datetime:
    return t - datetime.timedelta(
        minutes=t.minute % multiple, seconds=t.second, microseconds=t.microsecond)




