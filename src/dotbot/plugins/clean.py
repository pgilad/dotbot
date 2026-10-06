import os
import sys
from pathlib import Path
from typing import Any

from dotbot.plugin import Plugin
from dotbot.util.common import display_path, normslash, unknown_options


class Clean(Plugin):
    """
    Cleans broken symbolic links.
    """

    supports_dry_run = True

    _directive = "clean"
    _options = frozenset({"force", "recursive"})

    def can_handle(self, directive: str) -> bool:
        return directive == self._directive

    def handle(self, directive: str, data: Any) -> bool:
        if directive != self._directive:
            msg = f"Clean cannot handle directive {directive}"
            raise ValueError(msg)
        return self._process_clean(data)

    def _process_clean(self, targets: Any) -> bool:
        success = True
        defaults = self._context.defaults().get(self._directive, {})
        for key in unknown_options(defaults, self._options):
            self._log.warning(f"Unknown option '{key}' in clean defaults")
        for target in targets:
            force = defaults.get("force", False)
            recursive = defaults.get("recursive", False)
            if isinstance(targets, dict) and isinstance(targets[target], dict):
                for key in unknown_options(targets[target], self._options):
                    self._log.warning(
                        f"Unknown option '{key}' for {display_path(target)}"
                    )
                force = targets[target].get("force", force)
                recursive = targets[target].get("recursive", recursive)
            success &= self._clean(normslash(target), force=force, recursive=recursive)
        return success

    def _clean(self, target: str, *, force: bool, recursive: bool) -> bool:
        """
        Cleans all the broken symbolic links in target if they point to
        a subdirectory of the base directory or if forced to clean.
        """
        if not os.path.isdir(os.path.expandvars(os.path.expanduser(target))):
            self._log.debug(f"Ignoring nonexistent directory {target}")
            return True
        for item in os.listdir(os.path.expandvars(os.path.expanduser(target))):
            path = os.path.abspath(
                os.path.join(os.path.expandvars(os.path.expanduser(target)), item)
            )
            if recursive and os.path.isdir(path) and not os.path.islink(path):
                # isdir follows symlinks, so check islink too: we don't want to
                # descend into symlinked directories, which can point outside
                # of the target or form a loop. okay to do a recursive call
                # here because depth should be fairly limited
                self._clean(path, force=force, recursive=recursive)
            if not os.path.exists(path) and os.path.islink(path):
                points_at = os.path.join(os.path.dirname(path), os.readlink(path))
                if sys.platform == "win32" and points_at.startswith("\\\\?\\"):
                    points_at = points_at[4:]
                if self._in_directory(path, self._context.base_directory()) or force:
                    if self._context.dry_run():
                        self._log.action(
                            f"Would remove invalid link {display_path(path)} -> {display_path(points_at)}"
                        )
                    else:
                        self._log.action(
                            f"Removing invalid link {display_path(path)} -> {display_path(points_at)}"
                        )
                        os.remove(path)
                else:
                    self._log.info(
                        f"Keeping invalid link {display_path(path)} -> {display_path(points_at)}"
                        ", because it points outside of the base directory"
                    )
        return True

    def _in_directory(self, path: str, directory: str) -> bool:
        """
        Returns true if the path is in the directory.
        """
        directory = os.path.realpath(directory)
        path = os.path.realpath(path)
        return path != directory and Path(path).is_relative_to(directory)
