from typing import Any

from dotbot.plugin import Plugin
from dotbot.util.common import shell_command, unknown_options


class Shell(Plugin):
    """
    Run arbitrary shell commands.
    """

    supports_dry_run = True

    _directive = "shell"
    _default_options = frozenset({"executable", "quiet", "stderr", "stdin", "stdout"})
    _options = _default_options | {"command", "description"}
    _has_shown_override_message = False

    def can_handle(self, directive: str) -> bool:
        return directive == self._directive

    def handle(self, directive: str, data: Any) -> bool:
        if directive != self._directive:
            msg = f"Shell cannot handle directive {directive}"
            raise ValueError(msg)
        return self._process_commands(data)

    def _process_commands(self, data: Any) -> bool:
        success = True
        defaults = self._context.defaults().get("shell", {})
        for key in unknown_options(defaults, self._default_options):
            self._log.warning(f"Unknown option '{key}' in shell defaults")
        options = self._get_option_overrides()
        for item in data:
            stdin = defaults.get("stdin", False)
            stdout = defaults.get("stdout", False)
            stderr = defaults.get("stderr", False)
            quiet = defaults.get("quiet", False)
            executable = defaults.get("executable", None)
            if isinstance(item, dict):
                for key in unknown_options(item, self._options):
                    self._log.warning(f"Unknown option '{key}' for shell command")
                cmd = item.get("command")
                msg = item.get("description", None)
                stdin = item.get("stdin", stdin)
                stdout = item.get("stdout", stdout)
                stderr = item.get("stderr", stderr)
                quiet = item.get("quiet", quiet)
                executable = item.get("executable", executable)
            elif isinstance(item, list):
                cmd = item[0] if item else None
                msg = item[1] if len(item) > 1 else None
            else:
                cmd = item
                msg = None
            if cmd is None:
                success = False
                self._log.warning(f"Missing command for shell entry {item!r}")
                continue
            prefix = "Would run command " if self._context.dry_run() else ""
            if quiet:
                if msg is not None:
                    self._log.info(f"{prefix}{msg}")
                # if quiet and no msg, show nothing
            elif msg is None:
                self._log.action(f"{prefix}{cmd}")
            else:
                self._log.action(f"{prefix}{msg} [{cmd}]")
            if self._context.dry_run():
                continue
            stdout = options.get("stdout", stdout)
            stderr = options.get("stderr", stderr)
            ret = shell_command(
                cmd,
                cwd=self._context.base_directory(),
                executable=executable,
                enable_stdin=stdin,
                enable_stdout=stdout,
                enable_stderr=stderr,
            )
            if ret != 0:
                success = False
                self._log.warning(f"Command [{cmd}] failed")
        if success:
            self._log.info("All commands have been executed")
        else:
            self._log.error("Some commands were not successfully executed")
        return success

    def _get_option_overrides(self) -> dict[str, bool]:
        ret = {}
        options = self._context.options()
        if getattr(options, "verbose", 0) > 1:
            ret["stderr"] = True
            ret["stdout"] = True
            if not self._has_shown_override_message:
                self._log.debug(
                    "Shell: Found cli option to force show stderr and stdout."
                )
                self._has_shown_override_message = True
        return ret
