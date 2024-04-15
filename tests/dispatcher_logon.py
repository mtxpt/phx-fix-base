import queue
import time
import threading
import logging
from pathlib import Path

from phx.fix.app import App, AppRunner, FixSessionConfig
from phx.fix.model import Create, Logon, Logout, FixAuthenticationMethod
from phx.utils import setup_logger, set_file_loging_handler, make_dirs


def temp_dir() -> Path:
    local = Path(__file__).parent.resolve()
    return local.parent.absolute() / "temp"


class Dispatcher:

    def __init__(self, message_queue: queue.Queue, runner: AppRunner):
        self.message_queue = message_queue
        self.logged_on = False
        self.thread = None
        self.runner = runner
        self.logger = self.runner.logger
        self.delay = 1

    def dispatch(self):
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
                self.logger.info(f"****> stopping FIX app...")
                self.runner.stop()
            elif isinstance(msg, Logout) and not self.logged_on:
                self.logger.info(f"****> {msg} without Logon first - most likely connection problem - stopping now")
                error = "connection problems"
                break
            elif isinstance(msg, Logout) and self.logged_on:
                break
            else:
                self.logger.info(f"****> unexpected message {msg}")

        self.logger.info(f"****> message loop completed with {error}")

    def start(self):
        self.logger.info(f"====> starting FIX app...")
        self.runner.start()
        self.logger.info(f"starting strategy processing FIX messages...")
        self.thread = threading.Thread(target=self.dispatch, args=())
        self.thread.start()

    def stop(self):
        self.thread.join()
        self.logger.info(f"<==== Strategy completed.")


if __name__ == "__main__":
    export_dir = temp_dir() / "test_logon"
    make_dirs(export_dir)

    # setup logger to console and log file
    logger = set_file_loging_handler(
        setup_logger("fix_service", level=logging.INFO),
        export_dir / "fix_service.log"
    )
    message_queue = queue.Queue()

    # FIX session config
    #   - adjust sender and target comp id as well as socket host and port
    #   - provide user name and secret
    fix_configs = FixSessionConfig(
        sender_comp_id="fix-client",
        target_comp_id="phoenix-prime",
        user_name="trader",
        password="secret",
        fix_auth_method=FixAuthenticationMethod.HMAC_SHA256,
        account="T1",
        socket_connect_port="1238",
        socket_connect_host="127.0.0.1",
        sub_dir="simple_logon",
    )
    fix_session_settings = fix_configs.get_fix_session_settings()

    # create a FIX application and run it to connect to FIX server, which then pushes to message queue
    app = App(message_queue, fix_session_settings, logger, str(export_dir))
    app_runner = AppRunner(app, fix_session_settings, fix_configs.get_session_id(), logger)

    # start the message processor which pulls from the message queue and dispatches accordingly
    dispatcher = Dispatcher(message_queue, app_runner)
    dispatcher.start()
    dispatcher.stop()
