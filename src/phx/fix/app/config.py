from typing import Optional, List, Callable
from pathlib import Path
import quickfix as fix

from phx.utils import make_dirs, make_dirs_for_file
from phx.utils.path_base import PathBase
from phx.fix.utils import dict_to_fix_dict, fix_session_default_config, fix_session_config


def get_settings_content(key, content: List[str]) -> Optional[str]:
    match = [c for c in content if c.startswith(key)]
    if match:
        tokens = match[0].split("=")
        if len(tokens) == 2:
            return tokens[1].rstrip()
    return None


def set_settings_content(content: List[str], key, value):
    for i in range(len(content)):
        if content[i].startswith(key):
            content[i] = f"{key}={str(value)}\n"


def default_settings_to_string(settings: fix.SessionSettings, pre) -> str:
    rows = []
    d = settings.get()
    rows.append("[DEFAULT]")
    rows.append("DefaultApplVerID="+d.getString("DefaultApplVerID"))
    rows.append("ConnectionType="+d.getString("ConnectionType"))
    rows.append("FileLogPath="+d.getString("FileLogPath"))
    rows.append("StartTime="+d.getString("StartTime"))
    rows.append("EndTime="+d.getString("EndTime"))
    rows.append("UseDataDictionary="+d.getString("UseDataDictionary"))
    rows.append("ReconnectInterval="+d.getString("ReconnectInterval"))
    rows.append("LogoutTimeout="+d.getString("LogoutTimeout"))
    rows.append("LogonTimeout="+d.getString("LogonTimeout"))
    rows.append("ResetOnLogon="+d.getString("ResetOnLogon"))
    rows.append("ResetOnLogout="+d.getString("ResetOnLogout"))
    rows.append("ResetOnDisconnect="+d.getString("ResetOnDisconnect"))
    rows.append("SendRedundantResendRequests="+d.getString("SendRedundantResendRequests"))
    rows.append("SocketNodelay="+d.getString("SocketNodelay"))
    rows.append("ValidateUserDefinedFields="+d.getString("ValidateUserDefinedFields"))
    rows.append("AllowUnknownMsgFields="+d.getString("AllowUnknownMsgFields"))

    return "\n".join([pre + r for r in rows])


def settings_to_string(settings: fix.SessionSettings, session_id, pre) -> str:
    rows = []
    d = settings.get(session_id)
    rows.append("[SESSION]")
    rows.append("BeginString="+d.getString("BeginString"))
    rows.append("SenderCompID="+d.getString("SenderCompID"))
    rows.append("TargetCompID="+d.getString("TargetCompID"))
    rows.append("HeartBtInt="+d.getString("HeartBtInt"))
    rows.append("SocketConnectPort="+d.getString("SocketConnectPort"))
    rows.append("SocketConnectHost="+d.getString("SocketConnectHost"))
    rows.append("DataDictionary="+d.getString("DataDictionary"))
    rows.append("FileStorePath="+d.getString("FileStorePath"))
    rows.append("Username="+d.getString("Username"))
    rows.append("Password="+d.getString("Password"))
    rows.append("Account="+d.getString("Account"))
    rows.append("AuthenticateByKey="+d.getString("AuthenticateByKey"))

    return default_settings_to_string(settings, pre) + "\n" + "\n".join([pre + r for r in rows])


def create_session_settings(self, filename: str, data_sub_dir: str = None, settings_mapper: Optional[Callable] = None):
    with open(filename) as f:
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
        fix_settings_file = str(self.data_dir / Path(filename).name)
        with open(make_dirs_for_file(fix_settings_file), "w") as new_file:
            new_file.writelines(mod_content)
        return fix.SessionSettings(fix_settings_file)


class FixSessionConfig(PathBase):

    def __init__(
            self,
            sender_comp_id,
            target_comp_id,
            user_name,
            password,
            auth_by_key,
            account="A1",
            sub_dir=None,
            begin_string="FIX.4.4",
            socket_connect_port="1238",
            socket_connect_host="127.0.0.1",
            data_dir=None,
            data_dictionary=None,
    ):
        PathBase.__init__(self)
        self.sender_comp_id = sender_comp_id
        if data_dictionary is None:
            data_dictionary = self.root / "phx/fix/specs/FIX44.xml"
        self.data_dictionary = data_dictionary
        if data_dir is None:
            if sub_dir is None:
                data_dir = self.temp / self.sender_comp_id
            else:
                data_dir = self.temp / sub_dir / self.sender_comp_id
        self.data_dir = data_dir
        self.log_dir = self.data_dir / "logs"
        self.session_dir = self.data_dir / "sessions"
        self.export_dir = self.data_dir / "exports"
        self.settings = fix.SessionSettings()
        session_default_cfg = fix_session_default_config(self.log_dir)
        fix_session_default_cfg = dict_to_fix_dict(session_default_cfg)
        self.settings.set(fix_session_default_cfg)
        session_cfg = fix_session_config(
            sender_comp_id,
            target_comp_id,
            user_name,
            password,
            auth_by_key,
            begin_string,
            socket_connect_port,
            socket_connect_host,
            data_dictionary,
            self.session_dir,
            account
        )
        self.session_id = fix.SessionID(begin_string, sender_comp_id, target_comp_id)
        fix_session_cfg = dict_to_fix_dict(session_cfg)
        self.settings.set(self.session_id, fix_session_cfg)

    def get_session_id(self) -> fix.SessionID:
        return self.session_id

    def get_fix_session_settings(self) -> fix.SessionSettings:
        return self.settings

    def get_string(self, key) -> str:
        return self.settings.get().getString(key)

    def set_string(self, key, value):
        return self.settings.get().setString(key, value)

    def to_str(self, pre="") -> str:
        return settings_to_string(self.settings, self.session_id, pre)

    def __str__(self):
        self.to_str()

    def make_dirs(self):
        make_dirs(self.log_dir)
        make_dirs(self.session_dir)
        make_dirs(self.export_dir)
