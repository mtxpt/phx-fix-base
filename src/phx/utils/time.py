import pandas as pd
from datetime import datetime, timedelta, timezone

def utcnow() -> pd.Timestamp:
    return pd.Timestamp.utcnow()


def dt_now_utc() -> datetime:
    return datetime.now(timezone.utc)

def round_up_second(t: datetime) -> datetime:
    if t.microsecond >= 500_000:
        t += timedelta(seconds=1)
    return t.replace(microsecond=0)


def round_down_second(t: datetime) -> datetime:
    return t.replace(microsecond=0)


def round_down_seconds(t: datetime, multiple_secs=1) -> datetime:
    multiple_micros = multiple_secs*1000_000
    micros = t.microsecond + (t.minute*60 + t.second)*1000_000
    return t - timedelta(microseconds=micros % multiple_micros)


def round_down_minutes(t: datetime, multiple=1) -> datetime:
    return t - timedelta(
        minutes=t.minute % multiple, seconds=t.second, microseconds=t.microsecond)




