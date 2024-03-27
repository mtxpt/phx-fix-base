import time
import random
from prometheus_client import start_http_server, Summary, Counter


def start_prometheus_server(port=8000):
    start_http_server(port=8000)


