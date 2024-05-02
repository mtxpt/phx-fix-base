from prometheus_client import Gauge, Histogram, Counter

DECODE_MESSAGE_DURATION_MICROSECONDS_HISTOGRAM = Histogram(
    "decode_message_duration_microseconds_histogram",
    "Duration in microseconds for decode the SBE messages(histogram)",
    ["channel", "exchange", "symbol", "type"],
    buckets=[
        0.01,
        0.1,
        1.0,
        5.0,
        10.0,
        20.0,
        40.0,
        60.0,
        80.0,
        100.0,
        150.0,
        200.0,
        300.0,
        500.0,
        1000.0,
        2000.0,
        5000.0,
    ],
)

REORDER_MESSAGE_DURATION_MICROSECONDS_HISTOGRAM = Histogram(
    "reorder_message_duration_microseconds_histogram",
    "Duration in microseconds for reorder the UDP packets(histogram)",
    ["channel", "exchange", "symbol", "type"],
    buckets=[
        0.01,
        0.1,
        1.0,
        5.0,
        10.0,
        20.0,
        40.0,
        60.0,
        80.0,
        100.0,
        150.0,
        200.0,
        300.0,
        500.0,
        1000.0,
        2000.0,
        5000.0,
    ],
)

EXCHANGE_TIME_UTC_LATENCY_MILLISECONDS_HISTOGRAM = Histogram(
    "exchange_time_utc_latency_milliseconds_histogram",
    "Exchange time utc latency in milliseconds(histogram)",
    ["channel", "exchange", "symbol", "type"],
    buckets=[
        0.01,
        0.1,
        1.0,
        5.0,
        10.0,
        20.0,
        40.0,
        60.0,
        80.0,
        100.0,
        150.0,
        200.0,
        300.0,
        500.0,
        1000.0,
        2000.0,
        5000.0,
    ],
)

SENDING_TIME_LATENCY_MILLISECONDS_HISTOGRAM = Histogram(
    "sending_time_utc_latency_milliseconds_histogram",
    "Sending time latency in milliseconds(histogram)",
    ["channel", "exchange", "symbol", "type"],
    buckets=[
        0.01,
        0.1,
        1.0,
        5.0,
        10.0,
        20.0,
        40.0,
        60.0,
        80.0,
        100.0,
        150.0,
        200.0,
        300.0,
        500.0,
        1000.0,
        2000.0,
        5000.0,
    ],
)

ORIGIN_CREATE_TIME_LATENCY_MILLISECONDS_HISTOGRAM = Histogram(
    "origin_create_time_utc_latency_milliseconds_histogram",
    "Origin create time latency in milliseconds(histogram)",
    ["channel", "exchange", "symbol", "type"],
    buckets=[
        0.01,
        0.1,
        1.0,
        5.0,
        10.0,
        20.0,
        40.0,
        60.0,
        80.0,
        100.0,
        150.0,
        200.0,
        300.0,
        500.0,
        1000.0,
        2000.0,
        5000.0,
    ],
)

TOP_BID_PRICE_GAUGE = Gauge(
    "top_bid_price",
    "Top bid price",
    ["channel", "exchange", "symbol"],
)

TOP_ASK_PRICE_GAUGE = Gauge(
    "top_ask_price",
    "Top ask price",
    ["channel", "exchange", "symbol"],
)


TOP_BID_TRADE_VOLUME_GAUGE = Gauge(
    "top_bid_trade_volume",
    "Top bid trade volume",
    ["channel", "exchange", "symbol"],
)

TOP_ASK_TRADE_VOLUME_GAUGE = Gauge(
    "top_ask_trade_volume",
    "Top ask trade volume",
    ["channel", "exchange", "symbol"],
)

RUNNING_VOLUME_OF_TRADES = Counter(
    "running_volume_of_trades",
    "Running volume of trades",
    ["channel", "exchange", "symbol", "side"],
)
