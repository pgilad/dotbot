import os
import subprocess
import sys
from collections.abc import Callable

import pytest

from tests.conftest import Dotfiles

# a command that writes to stdout and to stderr (also in cmd.exe on Windows)
APPLE_AND_BANANA = "echo apple && echo banana >&2"


@pytest.mark.parametrize("arguments", [[], ["-v"]])
def test_shell_output_hidden_by_default(
    arguments: list[str],
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the output of commands is hidden by default, also with '-v'."""

    dotfiles.write_config([{"shell": [APPLE_AND_BANANA]}])
    run_dotbot(*arguments)

    output = capfd.readouterr()
    assert not any(line.startswith("apple") for line in output.out.splitlines())
    assert not any(line.startswith("banana") for line in output.err.splitlines())


@pytest.mark.parametrize("disabled_in", [None, "command", "defaults"])
def test_shell_vv_shows_output(
    disabled_in: str | None,
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that '-vv' shows the output of commands, also if it's disabled."""

    disabled = {"stdout": False, "stderr": False}
    command: dict[str, object] = {"command": APPLE_AND_BANANA}
    config: list[dict[str, object]] = [{"shell": [command]}]
    if disabled_in == "command":
        command.update(disabled)
    elif disabled_in == "defaults":
        config.insert(0, {"defaults": {"shell": disabled}})
    dotfiles.write_config(config)
    run_dotbot("-vv")

    output = capfd.readouterr()
    assert any(line.startswith("apple") for line in output.out.splitlines())
    assert any(line.startswith("banana") for line in output.err.splitlines())


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        pytest.param("echo apple", ["echo apple", "apple"], id="string"),
        pytest.param(
            ["echo apple", "echoing message"],
            ["echoing message [echo apple]", "apple"],
            id="list",
        ),
    ],
)
def test_shell_short_forms(
    entry: str | list[str],
    expected: list[str],
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify the string form and the [command, description] form of a command.

    The defaults apply to them.
    """

    dotfiles.write_config(
        [
            {"defaults": {"shell": {"stdout": True}}},
            {"shell": [entry]},
        ]
    )
    run_dotbot()

    # the last line is the summary
    lines = [line.strip() for line in capfd.readouterr().out.splitlines()]
    assert lines[:-1] == expected


def test_shell_can_override_defaults(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the shell command can override defaults."""

    dotfiles.write_config(
        [
            {"defaults": {"shell": {"stdout": True}}},
            {"shell": [{"command": "echo apple", "stdout": False}]},
        ]
    )
    run_dotbot()

    stdout = capfd.readouterr().out.splitlines()
    assert not any(line.startswith("apple") for line in stdout)


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        pytest.param(
            {"description": "echoing a thing..."},
            ["echoing a thing... [echo banana]"],
            id="not-quiet",
        ),
        pytest.param(
            {"description": "echoing a thing...", "quiet": True},
            ["echoing a thing..."],
            id="quiet",
        ),
        pytest.param({"quiet": True}, [], id="quiet-without-description"),
    ],
)
def test_shell_quiet(
    options: dict[str, object],
    expected: list[str],
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that quiet shows only the description of a command, if it has one."""

    dotfiles.write_config([{"shell": [{"command": "echo banana", **options}]}])
    run_dotbot()

    # the last line is the summary
    assert capfd.readouterr().out.splitlines()[:-1] == expected


def test_shell_dry_run(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the shell plugin does not execute commands during a dry run."""

    dotfiles.write_config(
        [
            {
                "shell": [
                    {
                        "command": "exit 1",
                    }
                ],
            }
        ]
    )
    run_dotbot("--dry-run")

    lines = capfd.readouterr().out.splitlines()
    assert any(line.strip() == "Would run command exit 1" for line in lines)


def test_shell_ignores_login_shell(
    capfd: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that commands run in /bin/sh (cmd.exe on Windows), not in $SHELL."""

    monkeypatch.setenv("SHELL", os.path.join(dotfiles.directory, "nonexistent"))
    dotfiles.write_config([{"shell": [{"command": "echo apple", "stdout": True}]}])
    run_dotbot()

    lines = capfd.readouterr().out.splitlines()
    assert any(line.startswith("apple") for line in lines)


@pytest.mark.parametrize("in_defaults", [False, True])
def test_shell_executable(
    capfd: pytest.CaptureFixture[str],
    in_defaults: bool,  # noqa: FBT001
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the executable option runs commands as `executable -c command`."""

    command = {"command": "print('banana')", "stdout": True}
    config: list[dict[str, object]] = [{"shell": [command]}]
    if in_defaults:
        config.insert(0, {"defaults": {"shell": {"executable": sys.executable}}})
    else:
        command["executable"] = sys.executable
    dotfiles.write_config(config)
    run_dotbot()

    lines = capfd.readouterr().out.splitlines()
    assert any(line.startswith("banana") for line in lines)


def test_shell_exception_is_reported(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that an exception in a plugin is reported with its message.

    The action must not be reported as not handled.
    """

    dotfiles.write_config([{"shell": 5}])
    with pytest.raises(SystemExit):
        run_dotbot()

    stderr = capfd.readouterr().err
    assert (
        "An error was encountered while executing action shell: "
        "TypeError: 'int' object is not iterable" in stderr
    )
    assert "not handled" not in stderr


def test_shell_entry_without_command(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that an entry without a command fails, and the others still run."""

    dotfiles.write_config(
        [
            {
                "shell": [
                    {"description": "nothing to run"},
                    [],
                    None,
                    {"command": "echo apple", "stdout": True},
                ]
            }
        ]
    )
    with pytest.raises(SystemExit):
        run_dotbot()

    output = capfd.readouterr()
    for entry in ("{'description': 'nothing to run'}", "[]", "None"):
        assert f"Missing command for shell entry {entry}\n" in output.err
    assert any(line.startswith("apple") for line in output.out.splitlines())


def test_shell_output_order_with_pipe(home: str, dotfiles: Dotfiles) -> None:
    """Verify that log messages and command output stay in order in a pipe."""

    _ = home
    dotfiles.write_config(
        [
            {
                "shell": [
                    {"command": "echo apple", "stdout": True},
                    {"command": "echo banana", "stdout": True},
                ]
            }
        ]
    )
    result = subprocess.run(
        [sys.executable, "-m", "dotbot", "-c", dotfiles.config_filename],
        capture_output=True,
        text=True,
        check=True,
    )

    lines = [line.strip() for line in result.stdout.splitlines()]
    assert lines == [
        "echo apple",
        "apple",
        "echo banana",
        "banana",
        "Done (no changes, 2 commands)",
    ]


@pytest.mark.parametrize(
    ("command", "reason"),
    [
        ("exit 3", "failed with exit code 3"),
        pytest.param(
            "kill -9 $$",
            "was stopped by signal 9",
            marks=pytest.mark.skipif(
                "sys.platform == 'win32'", reason="Windows has no signals"
            ),
        ),
    ],
)
def test_shell_failure_reason(
    command: str,
    reason: str,
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a failed command shows its exit code or its signal."""

    dotfiles.write_config([{"shell": [command]}])
    with pytest.raises(SystemExit):
        run_dotbot()

    assert f"error: Command [{command}] {reason}" in capfd.readouterr().err.splitlines()
