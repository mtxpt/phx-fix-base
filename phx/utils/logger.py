import logging


def setup_logger(logger_name, level=logging.INFO) -> logging.Logger:
    lz = logging.getLogger(logger_name)
    formatter = logging.Formatter('%(asctime)s : %(message)s')
    lz.setLevel(level)
    # Log to std.err
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    lz.addHandler(stream_handler)
    # Multiprocess logging:
    # https://docs.python.org/3/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes
    return lz


def set_file_loging_handler(logger_or_name, log_file):
    if isinstance(logger_or_name, str):
        lz = logging.getLogger(logger_or_name)
    else:
        lz = logger_or_name
    formatter = logging.Formatter('%(asctime)s : %(message)s')
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setFormatter(formatter)
    lz.addHandler(file_handler)


# phx_log = setup_logger('phx_log')
