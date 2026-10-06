# This file is copied as plugin.py into two directories, to verify that plugin
# files and classes with the same name don't replace each other. The name of
# the directory is the directive.

import os
from typing import Any

import dotbot

DIRECTIVE = os.path.basename(os.path.dirname(os.path.abspath(__file__)))


class SameName(dotbot.Plugin):
    def can_handle(self, directive: str) -> bool:
        return directive == DIRECTIVE

    def handle(self, directive: str, _data: Any) -> bool:
        if directive != DIRECTIVE:
            msg = f"SameName cannot handle directive {directive}"
            raise ValueError(msg)
        with open(os.path.abspath(os.path.expanduser(f"~/{DIRECTIVE}")), "w") as file:
            file.write(DIRECTIVE)
        return True
