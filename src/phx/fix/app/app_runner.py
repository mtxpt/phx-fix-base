import logging

import quickfix as fix
from phx.fix.app import App


class AppRunner(object):

    def __init__(
            self,
            app: App,
            session_settings: fix.SessionSettings,
            session_id: fix.SessionID,
            logger: logging.Logger
    ):
        self.app = app
        self.session_settings = session_settings
        self.session_id = session_id
        self.logger = logger
        self.store_factory = fix.FileStoreFactory(session_settings)
        self.log_factory = fix.FileLogFactory(session_settings)
        self.initiator = None
        self.is_fix_session_up = False

    def roll_session_settings(self):
        start_time = self.session_settings.get().getString("StartTime")
        end_time = self.session_settings.get().getString("EndTime")
        self.session_settings.get().setString("StartTime", end_time)
        self.session_settings.get().setString("EndTime", start_time)
        self.session_settings.get(self.session_id).setString("StartTime", end_time)
        self.session_settings.get(self.session_id).setString("EndTime", start_time)

    def start(self):
        try:
            self.initiator = fix.SocketInitiator(self.app, self.store_factory, self.session_settings, self.log_factory)
            self.initiator.start()
            self.is_fix_session_up = True
        except Exception as e:
            self.logger.error(f"AppRunner.start: exception {e}")

    def stop(self):
        try:
            if self.initiator is not None:
                self.initiator.stop()
                self.is_fix_session_up = False
        except Exception as e:
            self.logger.error(f"AppRunner.stop: exception {e}")
