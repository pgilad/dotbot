# A plugin that fails without an error message, like some third-party plugins.

from typing import Any

import dotbot


class Fail(dotbot.Plugin):
    supports_dry_run = True

    def can_handle(self, directive: str) -> bool:
        return directive == "fail"

    def handle(self, directive: str, _data: Any) -> bool:
        if directive != "fail":
            msg = f"Fail cannot handle directive {directive}"
            raise ValueError(msg)
        return False
