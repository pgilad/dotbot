import json
import os.path
from typing import Any

import yaml

from dotbot.util import string


class ConfigReader:
    _config: list[Any]

    def __init__(self, config_file_paths: list[str]):
        self._config = []
        for path in config_file_paths:
            config = self._read(path)
            if config is None:
                continue
            if not isinstance(config, list):
                msg = "Configuration file must be a list of tasks"
                raise ReadingError(msg)
            for task in config:
                if not isinstance(task, dict):
                    msg = f"Each task must be a mapping of actions, but found: {task!r}"
                    raise ReadingError(msg)
                if "plugins" in task:
                    paths = task["plugins"]
                    if not isinstance(paths, list) or any(
                        not isinstance(plugin_path, str) or not plugin_path
                        for plugin_path in paths
                    ):
                        msg = f"Invalid 'plugins' directive in {path}: expected a list of paths"
                        raise ReadingError(msg)
                if "defaults" in task and not isinstance(task["defaults"], dict):
                    msg = f"Invalid 'defaults' directive in {path}: expected a mapping"
                    raise ReadingError(msg)
            self._config.extend(config)

    def _read(self, config_file_path: str) -> Any:
        try:
            _, ext = os.path.splitext(config_file_path)
            with open(config_file_path, encoding="utf-8") as fin:
                return json.load(fin) if ext == ".json" else yaml.safe_load(fin)
        except Exception as e:
            msg = string.indent_lines(str(e))
            msg = f"Could not read config file:\n{msg}"
            raise ReadingError(msg) from e

    def get_config(self) -> Any:
        return self._config


class ReadingError(Exception):
    pass
