import os
import tomli
from pathlib import Path
from typing import List

from phx.fix_base.utils.logger import setup_logger
from phx.fix_base.utils.file import make_dirs_for_file


class PathBase(object):

    serv_num = 0

    def __init__(self):
        self.path = Path(__file__).parent.resolve()
        self.root = self.path.parent.parent.absolute()
        self.temp = self.root / "temp"
        self.config = self.root / "config"
        self.root_run = self.root / "run"
        if not os.path.exists(self.root_run):
            os.mkdir(self.root_run)
        self.conda_bin = self.root / "opt/conda/bin"
        self.home = Path.home()

        PathBase.serv_num += 1
        self.service_log = setup_logger(f"fix_service{PathBase.serv_num}")

    def create_temp_file(self, file_name, lines: List[str]) -> str:
        file_name = str(self.temp / file_name)
        with open(make_dirs_for_file(file_name), "w") as f:
            f.writelines(lines)
        return file_name

    def read_config_toml(self, file_name):
        conf_path = self.config / file_name
        with open(conf_path, mode="rb") as fp:
            config = tomli.load(fp)
        return config
