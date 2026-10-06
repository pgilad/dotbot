"""Test that a plugin can use dataclasses with postponed annotations.

This file is copied to a location with the name "copy.py",
and is then loaded from within the `test_plugins.py` code.
"""

from __future__ import annotations

import dataclasses
import os.path
from typing import Any, ClassVar

import dotbot


@dataclasses.dataclass
class Message:
    # the annotations are strings, so dataclasses looks up this module in
    # sys.modules to find out if they are ClassVar
    prefix: ClassVar[str] = "dataclass"
    text: str = "plugin loading works"


class Dataclass(dotbot.Plugin):
    def can_handle(self, directive: str) -> bool:
        return directive == "plugin_dataclass"

    def handle(self, directive: str, _data: Any) -> bool:
        if directive != "plugin_dataclass":
            msg = f"Dataclass cannot handle directive {directive}"
            raise ValueError(msg)

        message = Message()
        with open(os.path.abspath(os.path.expanduser("~/flag-dataclass")), "w") as file:
            file.write(f"{message.prefix} {message.text}")
        return True
