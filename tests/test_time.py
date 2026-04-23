"""测试时间格式转换函数。"""

from src.utils import format_time, ts_to_seconds


def test_format_time_zero():
    assert format_time(0.0) == "00:00:00,000"


def test_format_time_basic():
    assert format_time(3661.5) == "01:01:01,500"


def test_format_time_milliseconds():
    assert format_time(1.123) == "00:00:01,123"
    assert format_time(1.120) == "00:00:01,120"


def test_format_time_exact():
    assert format_time(3600) == "01:00:00,000"


def test_ts_to_seconds_zero():
    assert ts_to_seconds("00:00:00,000") == 0.0


def test_ts_to_seconds_basic():
    assert ts_to_seconds("01:01:01,500") == 3661.5


def test_ts_to_seconds_dot_separator():
    assert ts_to_seconds("00:00:01.123") == 1.123


def test_ts_to_seconds_roundtrip():
    ts = "02:30:45,678"
    assert format_time(ts_to_seconds(ts)) == ts


def test_ts_to_seconds_invalid():
    assert ts_to_seconds("invalid") == 0.0
