import os
import re
import subprocess
import sys
from collections.abc import Collection
from typing import Any

# The syntax that os.path.expandvars expands
_VARIABLE = re.compile(r"\$(\w+|\{[^}]*\})", re.ASCII)


def shell_command(
    command: str,
    cwd: str | None = None,
    *,
    executable: str | None = None,
    enable_stdin: bool = False,
    enable_stdout: bool = False,
    enable_stderr: bool = False,
) -> int:
    """
    Run a command and return its exit code.

    Without an executable, the command runs in /bin/sh (cmd.exe on Windows),
    and not in the login shell of the user ($SHELL), so that a configuration
    behaves the same for all users. With an executable, the command runs as
    `executable -c command`.
    """
    with open(os.devnull, "w") as devnull_w, open(os.devnull) as devnull_r:
        stdin = None if enable_stdin else devnull_r
        stdout = None if enable_stdout else devnull_w
        stderr = None if enable_stderr else devnull_w
        return subprocess.call(  # noqa: S602
            command if executable is None else [executable, "-c", command],
            shell=executable is None,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            cwd=cwd,
        )


def undefined_variable(path: str) -> str | None:
    """
    Returns the first environment variable in a path that os.path.expandvars
    has expanded, or None.

    os.path.expandvars leaves undefined variables unchanged, so a variable that
    is still in the path is undefined.
    """
    match = _VARIABLE.search(path)
    return match.group(0) if match else None


def unknown_options(options: Any, known: Collection[str]) -> list[str]:
    """
    Returns the keys of an options dictionary that are not in known.
    """
    if not isinstance(options, dict):
        return []
    return [str(key) for key in options if key not in known]


def normslash(path: str) -> str:
    if sys.platform == "win32":
        # this is how normcase in cpython/Lib/ntpath.py does it; we don't use normcase
        # because we don't want to make all characters lowercase
        return path.replace("/", "\\")
    return path
