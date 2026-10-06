import os
from typing import Any

from dotbot.plugin import Plugin
from dotbot.util.common import (
    display_path,
    normslash,
    undefined_variable,
    unknown_options,
)


class Create(Plugin):
    """
    Create empty paths.
    """

    supports_dry_run = True

    _directive = "create"
    _options = frozenset({"mode"})

    def can_handle(self, directive: str) -> bool:
        return directive == self._directive

    def handle(self, directive: str, data: Any) -> bool:
        if directive != self._directive:
            msg = f"Create cannot handle directive {directive}"
            raise ValueError(msg)
        return self._process_paths(data)

    def _process_paths(self, paths: Any) -> bool:
        success = True
        defaults = self._context.defaults().get("create", {})
        for key in unknown_options(defaults, self._options):
            self._log.warning(f"Unknown option '{key}' in create defaults")
        for key in paths:
            path = os.path.expandvars(os.path.expanduser(normslash(key)))
            # only warn, because a path can contain a literal "$"
            variable = undefined_variable(path)
            if variable is not None:
                self._log.warning(
                    f"Undefined environment variable {variable} in {key}"
                    ", using the name as written"
                )
            path = os.path.abspath(path)
            mode = defaults.get("mode", 0o777)  # same as the default for os.makedirs
            if isinstance(paths, dict):
                options = paths[key]
                for option in unknown_options(options, self._options):
                    self._log.warning(f"Unknown option '{option}' for {key}")
                if options:
                    mode = options.get("mode", mode)
            success &= self._create(path, mode)
        if success:
            self._log.info("All paths have been set up")
        else:
            self._log.error("Some paths were not successfully set up")
        return success

    def _exists(self, path: str) -> bool:
        """
        Returns true if the path exists.
        """
        path = os.path.expanduser(path)
        return os.path.exists(path)

    def _create(self, path: str, mode: int) -> bool:
        success = True
        if not self._exists(path):
            self._log.debug(f"Trying to create path {path} with mode {mode}")
            try:
                if self._context.dry_run():
                    self._log.action(f"Would create path {display_path(path)}")
                    return True
                self._log.action(f"Creating path {display_path(path)}")
                os.makedirs(path, mode)
                # On Windows, the *mode* argument to `os.makedirs()` is ignored.
                # The mode must be set explicitly in a follow-up call.
                os.chmod(path, mode)
            except OSError:
                self._log.warning(f"Failed to create path {display_path(path)}")
                success = False
        else:
            self._log.info(f"Path exists {display_path(path)}")
        return success
