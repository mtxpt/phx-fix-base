import queue
import threading
import quickfix as fix
from typing import Callable

from phx.fix.app import App, FixSessionConfig
from phx.fix.model import Logon, Create
from phx.utils import PathBase, setup_logger


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
    path_base = PathBase()
    temp_dir = path_base.temp
    logger = setup_logger("fix_service")
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
    )
    fix_settings = fix_configs.get_fix_session_settings()

    fix_app = App(message_queue, fix_settings, logger, temp_dir)
    store_factory = fix.FileStoreFactory(fix_settings)
    log_factory = fix.FileLogFactory(fix_settings)
    initiator = fix.SocketInitiator(fix_app, store_factory, fix_settings, log_factory)

    strategy = Strategy(message_queue, lambda: initiator.stop())

    strategy.start()
    initiator.start()

    strategy.thread.join()

    print(f"Strategy completed")




