import queue
import threading
import logging
from typing import Callable
from pathlib import Path

from phx.fix.app import App, AppRunner, FixSessionConfig
from phx.fix.model import Logon, Create
from phx.utils import setup_logger, set_file_loging_handler, make_dirs


def temp_dir() -> Path:
    local = Path(__file__).parent.resolve()
    return local.parent.absolute() / "temp"


class Strategy:

    def __init__(self, message_queue: queue.Queue, stop: Callable):
        self.message_queue = message_queue
        self.thread = None
        self.stop = stop

    def run(self):
        done = False
        print(f"Starting strategy...")
        while not done:
            msg = self.message_queue.get()
            print(f"Message received: {msg}")
            if isinstance(msg, Create):
                print(f"Create: {msg}")
            elif isinstance(msg, Logon):
                print(f"Logon: {msg}")
                done = True
                self.stop()

    def start(self):
        self.thread = threading.Thread(target=self.run, args=())
        self.thread.start()


if __name__ == "__main__":
    export_dir = temp_dir() / "simple_logon"
    make_dirs(export_dir)
    logger = set_file_loging_handler(
        setup_logger("fix_service", level=logging.INFO),
        export_dir / "fix_service.log"
    )
    message_queue = queue.Queue()
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

    app = App(message_queue, fix_session_settings, logger, export_dir)
    app_runner = AppRunner(app, fix_session_settings, fix_configs.get_session_id(), logger)
    strategy = Strategy(message_queue, lambda: app_runner.stop())

    app_runner.start()
    strategy.start()

    strategy.thread.join()

    print(f"Strategy completed")
