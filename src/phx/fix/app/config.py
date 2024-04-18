from typing import Optional, List, Callable, Union
from pathlib import Path
import quickfix as fix

from phx.fix.model.auth import FixAuthenticationMethod
from phx.utils import make_dirs, make_dirs_for_file
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
    rows.append("FixAuthenticationMethod="+d.getString("FixAuthenticationMethod"))

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


class FixSessionConfig(object):

    FIX_SCHEMA_DICT = "src/phx/fix/specs/FIX44.xml"

    def __init__(
            self,
            sender_comp_id,
            target_comp_id,
            user_name,
            password,
            fix_auth_method: Union[FixAuthenticationMethod, str],
            account="A1",
            sub_dir=None,
            begin_string="FIX.4.4",
            socket_connect_port="1238",
            socket_connect_host="127.0.0.1",
            data_dir=None,
            fix_schema_dict: str = None,
            start_time="00:00:00",
            end_time="00:00:00",
            root=None
    ):
        self.sender_comp_id = sender_comp_id

        # different directories and files
        local = Path(__file__).parent.resolve()
        project_dir = local.parent.parent.parent.parent.absolute()
        self.root = Path(root) if root is not None else project_dir
        self.temp = self.root / "temp"
        self.fix_schema_dict = self.root / self.FIX_SCHEMA_DICT if fix_schema_dict is None else fix_schema_dict
        sub_dir = self.sender_comp_id if sub_dir is None else Path(sub_dir) / self.sender_comp_id
        self.data_dir = self.temp / sub_dir if data_dir is None else data_dir
        self.log_dir = self.data_dir / "logs"
        self.session_dir = self.data_dir / "sessions"
        self.export_dir = self.data_dir / "exports"

        # default config
        self.settings = fix.SessionSettings()
        self.settings.set(
            dict_to_fix_dict(
                fix_session_default_config(self.log_dir, start_time, end_time)
            )
        )

        # session specific config
        self.session_id = fix.SessionID(begin_string, sender_comp_id, target_comp_id)
        self.settings.set(
            self.session_id,
            dict_to_fix_dict(
                fix_session_config(
                    sender_comp_id,
                    target_comp_id,
                    user_name,
                    password,
                    FixAuthenticationMethod(fix_auth_method),
                    begin_string,
                    socket_connect_port,
                    socket_connect_host,
                    self.fix_schema_dict,
                    self.session_dir,
                    account
                )
            )
        )

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
        make_dirs(self.data_dir)
        make_dirs(self.log_dir)
        make_dirs(self.session_dir)
        make_dirs(self.export_dir)
