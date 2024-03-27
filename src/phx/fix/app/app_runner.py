import logging
import queue
from pathlib import Path
from typing import Optional, Callable, Union

import quickfix as fix

from phx.fix.app.config import PathBase
from phx.fix.app.config import set_settings_content, get_settings_content, FixSessionConfig
from phx.utils import make_dirs, make_dirs_for_file


class AppRunner(PathBase):

    def __init__(
        self,
        fix_app_type,
        message_queue: queue.Queue,
        fix_settings: Union[str, FixSessionConfig],
        data_sub_dir=None,
        settings_mapper: Optional[Callable] = None,
        log_level=logging.INFO,
        re_raise_exception=True
    ):
        PathBase.__init__(self)
        self.fix_app_type = fix_app_type
        self.message_queue = message_queue
        self.re_raise_exception = re_raise_exception
        self.log_level = log_level
        self.data_dir = None
        self.export_dir = None
        self.log_dir = None
        self.session_dir = None
        self.exception = None

        # quickfix settings configuration
        self.fix_settings: Optional[fix.SessionSettings] = None
        self.session_id: Optional[fix.SessionID] = None
        self.sender_comp_id: Optional[str] = None
        self.create_session_settings(fix_settings, data_sub_dir, settings_mapper)

    def create_session_settings(self, fix_settings: Union[str, FixSessionConfig], data_sub_dir, settings_mapper):
        if isinstance(fix_settings, str):
            with open(fix_settings) as f:
                content = f.readlines()
                mod_content = settings_mapper(content) if settings_mapper is not None else content
                self.sender_comp_id = get_settings_content("SenderCompID", mod_content)
                target_comp_id = get_settings_content("TargetCompID", mod_content)
                begin_string = get_settings_content("BeginString", mod_content)
                self.session_id = fix.SessionID(begin_string, self.sender_comp_id, target_comp_id)
                if data_sub_dir is None:
                    self.data_dir = self.temp / self.sender_comp_id
                else:
                    self.data_dir = self.temp / data_sub_dir / self.sender_comp_id
                self.log_dir = self.data_dir / "logs"
                self.session_dir = self.data_dir / "sessions"
                self.export_dir = self.data_dir / "exports"
                make_dirs(self.log_dir)
                make_dirs(self.session_dir)
                make_dirs(self.export_dir)
                set_settings_content(mod_content, "DataDictionary", self.root / "phx/fix/specs/FIX44.xml")
                set_settings_content(mod_content, "FileLogPath", self.log_dir)
                set_settings_content(mod_content, "FileStorePath", self.session_dir)
                fix_settings_file = str(self.data_dir / Path(fix_settings).name)
                with open(make_dirs_for_file(fix_settings_file), "w") as new_file:
                    new_file.writelines(mod_content)
                self.fix_settings = fix.SessionSettings(fix_settings_file)
        elif isinstance(fix_settings, FixSessionConfig):
            self.fix_settings = fix_settings.settings
            self.session_id = fix_settings.session_id
            self.sender_comp_id = fix_settings.sender_comp_id
            self.data_dir = fix_settings.data_dir
            self.log_dir = fix_settings.log_dir
            self.session_dir = fix_settings.session_dir
            self.export_dir = fix_settings.export_dir
            fix_settings.make_dirs()

    def run(self):
        while self.should_run_again():
            self.run_once()
            # there is a bug in fix.SessionConfig, we need to set StartTime and EndTime
            # both values at the global and session level, otherwise QuickFix is too stupid to log in again
            start_time = self.fix_settings.get().getString("StartTime")
            end_time = self.fix_settings.get().getString("EndTime")
            self.fix_settings.get().setString("StartTime", end_time)
            self.fix_settings.get().setString("EndTime", start_time)
            self.fix_settings.get(self.session_id).setString("StartTime", end_time)
            self.fix_settings.get(self.session_id).setString("EndTime", start_time)

    def should_run_again(self) -> bool:
        return True

    def run_once(self) -> bool:
        initiator = None

        try:
            self.service_log.setLevel(self.log_level)
            self.service_log.info(
                f"starting FIX application: sender comp id={self.sender_comp_id}, "
                f"fix app class={self.fix_app_type.__name__}, "
                f"data_dir={self.data_dir}"
            )

            start_time = self.fix_settings.get().getString("StartTime")
            end_time = self.fix_settings.get().getString("EndTime")
            self.service_log.info(f"FIX session time from {start_time} to {end_time}")

            # create the FIX application and pass along the strategy to route the callbacks to the strategy
            fix_app = self.fix_app_type(
                self.message_queue,
                self.fix_settings,
                self.service_log,
                self.export_dir,
            )

            # start talking to FIX server
            store_factory = fix.FileStoreFactory(self.fix_settings)
            log_factory = fix.FileLogFactory(self.fix_settings)
            initiator = fix.SocketInitiator(fix_app, store_factory, self.fix_settings, log_factory)
            initiator.start()

            if initiator is not None:
                initiator.stop()
                self.service_log.info(f"initiator stopped")

        except Exception as e:
            self.exception = e
            self.service_log.info(
                f"exception of type {type(e).__name__} in {self.__class__.__name__}.run : {e}"
            )

        finally:
            if initiator is not None and initiator.isLoggedOn():
                initiator.stop()
                self.service_log.info(f"initiator stopped in finally")
            if self.exception is not None:
                raise self.exception

