import logging
import queue
from datetime import datetime
from pathlib import Path

import yaml
from phx.fix.app import App, AppRunner, FixSessionConfig
from phx.fix.model.auth import FixAuthenticationMethod
from phx.utils import make_dirs, set_file_loging_handler, setup_logger

from strategy import DeribitTestStrategy


def temp_dir() -> Path:
    local = Path(__file__).parent.resolve()
    return local.absolute() / "temp"


def fix_schema_file() -> Path:
    local = Path(__file__).parent.resolve()
    return str(local.parent.parent.absolute() / "src" / "phx" / "fix" / "specs" / "FIX44.xml")


if __name__ == "__main__":
    config = yaml.safe_load(open("strategy.yaml"))
    export_dir = temp_dir()
    make_dirs(export_dir)
    LOG_TIMESTAMP = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    logger = set_file_loging_handler(
        setup_logger("fix_service", level=logging.INFO),
        export_dir / f"test_base_strategy_{LOG_TIMESTAMP}.log"
    )
    message_queue = queue.Queue()
    logger.info(f"Fix schema file:{fix_schema_file()}")
    fix_configs = FixSessionConfig(
        sender_comp_id="test",
        target_comp_id="phoenix-prime",
        user_name="trader",
        password="secret",
        fix_auth_method=FixAuthenticationMethod.HMAC_SHA256,
        account="T1",
        socket_connect_port="1238",
        socket_connect_host="127.0.0.1",
        fix_schema_dict=fix_schema_file()
    )
    fix_session_settings = fix_configs.get_fix_session_settings()
    app = App(message_queue, fix_session_settings, logger, export_dir)
    app_runner = AppRunner(app, fix_session_settings, fix_configs.get_session_id(), logger)

    strategy = DeribitTestStrategy(app_runner, config, logger)
    strategy.strategy_loop()

    logger.info("DeribitTestStrategy strategy finished")
