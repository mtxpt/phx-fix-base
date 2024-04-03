import queue
import time
import threading
import logging
from pathlib import Path

from phx.fix.app import App, AppRunner, FixSessionConfig
from phx.fix.model import Create, Logon, Logout
from phx.utils import setup_logger, set_file_loging_handler, make_dirs


def temp_dir() -> Path:
    local = Path(__file__).parent.resolve()
    return local.parent.absolute() / "temp"


class Strategy:

    def __init__(self, message_queue: queue.Queue, runner: AppRunner):
        self.message_queue = message_queue
        self.logged_on = False
        self.thread = None
        self.runner = runner
        self.logger = self.runner.logger
        self.delay = 1

    def run(self):
        error = "no errors"
        while True:
            msg = self.message_queue.get()
            self.logger.info(f"****> {msg} received")
            if isinstance(msg, Create):
                self.logger.info(f"****> {msg}")
            elif isinstance(msg, Logon):
                self.logger.info(f"****> {msg} - going to stop in {self.delay}s")
                time.sleep(2)
                self.logged_on = True
                self.logger.info(f"****> Stopping FIX app...")
                self.runner.stop()
            elif isinstance(msg, Logout) and not self.logged_on:
                self.logger.info(f"****> {msg} without Logon first - most likely connection problem - stopping now")
                error = "connection problems"
                break
            elif isinstance(msg, Logout) and self.logged_on:
                break
            else:
                self.logger.info(f"****> Unexpected message {msg}")

        self.logger.info(f"****> Message loop completed with {error}")

    def start(self):
        self.logger.info(f"====> Starting FIX app...")
        self.runner.start()
        self.logger.info(f"Starting strategy processing FIX messages...")
        self.thread = threading.Thread(target=self.run, args=())
        self.thread.start()

    def stop(self):
        self.thread.join()
        self.logger.info(f"<==== Strategy completed.")


if __name__ == "__main__":
    export_dir = temp_dir() / "simple_logon"
    make_dirs(export_dir)

    # setup logger to console and log file
    logger = set_file_loging_handler(
        setup_logger("fix_service", level=logging.INFO),
        export_dir / "fix_service.log"
    )
    message_queue = queue.Queue()

    # FIX session config
    fix_configs = FixSessionConfig(
        sender_comp_id="test",
        target_comp_id="proxy",
        user_name="trader",
        password="secret",
        auth_by_key=True,
        account="T1",
        socket_connect_port="1238",
        socket_connect_host="127.0.0.1",
        sub_dir="simple_logon",
    )
    fix_session_settings = fix_configs.get_fix_session_settings()

    app = App(message_queue, fix_session_settings, logger, str(export_dir))
    app_runner = AppRunner(app, fix_session_settings, fix_configs.get_session_id(), logger)
    strategy = Strategy(message_queue, app_runner)
    strategy.start()
    strategy.stop()
