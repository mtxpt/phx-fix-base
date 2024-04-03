import logging


def setup_logger(logger_name, level=logging.INFO) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    formatter = logging.Formatter('%(asctime)s : %(message)s')
    logger.setLevel(level)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    # Multiprocess logging:
    # https://docs.python.org/3/howto/logging-cookbook.html#logging-to-a-single-file-from-multiple-processes
    return logger


def set_file_loging_handler(logger_or_name, log_file) -> logging.Logger:
    if isinstance(logger_or_name, str):
        logger = logging.getLogger(logger_or_name)
    else:
        logger = logger_or_name
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setFormatter(logging.Formatter('%(asctime)s : %(message)s'))
    logger.addHandler(file_handler)
    return logger
