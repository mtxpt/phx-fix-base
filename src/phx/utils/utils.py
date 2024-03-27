import operator as op
from datetime import datetime
from typing import Optional, Any


def float_to_string(value: float, digits=2) -> str:
    return '{0:.{1}%}'.format(value, digits)


def str_to_datetime(date_time_str) -> Optional[datetime]:
    try:
        # 20200720-07:32:15.114
        return datetime.strptime(date_time_str, '%Y%m%d-%H:%M:%S.%f')
    except:
        return None


def datetime_to_str(date_time: datetime) -> str:
    try:
        # 20200720-07:32:15.114
        return date_time.strftime('%Y%m%d-%H:%M:%S.%f')
    except:
        return None


def operator_str(f):
    if f == op.eq:
        return "=="
    elif f == op.ge:
        return ">="
    elif f == op.gt:
        return ">="
    elif f == op.le:
        return "<="
    elif f == op.lt:
        return "<"
    else:
        return f.__name__


def get_parent_attribute(instance, attribute) -> Optional[Any]:
    """
    This is from Stackoverflow
    https://stackoverflow.com/questions/2265060/how-to-access-parent-class-object-through-derived-class-instance
    """
    for parent in instance.__class__.__bases__:
        if attribute in parent.__dict__:
            return parent.__dict__[attribute]
    return None


def dict_get_or_else(data: dict, key, default):
    if key in data:
        return data[key]
    else:
        if isinstance(default, Callable):
            return default()
        else:
            return default


def dict_set_if_missing(data: dict, key, default):
    if key in data:
        return
    else:
        if isinstance(default, Callable):
            data[key] = default()
        else:
            data[key] = default


def dict_diff(this: dict, other: dict) -> dict:
    diff = {}
    keys = set(this.keys()).union(set(other.keys()))
    for key in keys:
        if key not in this:
            diff[key] = None, other[key]
        elif key not in other:
            diff[key] = this[key], None
        elif this[key] != other[key]:
            diff[key] = this[key], other[key]
    return diff

