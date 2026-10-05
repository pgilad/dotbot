import os
import subprocess
import sys
from collections.abc import Callable

import pytest

from tests.conftest import Dotfiles


def test_shell_allow_stdout(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify shell command STDOUT works."""

    dotfiles.write_config(
        [
            {
                "shell": [
                    {
                        "command": "echo apple",
                        "stdout": True,
                    }
                ],
            }
        ]
    )
    run_dotbot()

    output = capfd.readouterr()
    assert any(line.startswith("apple") for line in output.out.splitlines()), output


def test_shell_cli_verbosity_overrides_1(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that '-vv' overrides the implicit default stdout=False."""

    dotfiles.write_config([{"shell": [{"command": "echo apple"}]}])
    run_dotbot("-vv")

    lines = capfd.readouterr().out.splitlines()
    assert any(line.startswith("apple") for line in lines)


def test_shell_cli_verbosity_overrides_2(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that '-vv' overrides an explicit stdout=False."""

    dotfiles.write_config([{"shell": [{"command": "echo apple", "stdout": False}]}])
    run_dotbot("-vv")

    lines = capfd.readouterr().out.splitlines()
    assert any(line.startswith("apple") for line in lines)


def test_shell_cli_verbosity_overrides_3(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that '-vv' overrides an explicit defaults:shell:stdout=False."""

    dotfiles.write_config(
        [
            {"defaults": {"shell": {"stdout": False}}},
            {"shell": [{"command": "echo apple"}]},
        ]
    )
    run_dotbot("-vv")

    stdout = capfd.readouterr().out.splitlines()
    assert any(line.startswith("apple") for line in stdout)


def test_shell_cli_verbosity_stderr(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that commands can output to STDERR."""

    dotfiles.write_config([{"shell": [{"command": "echo apple >&2"}]}])
    run_dotbot("-vv")

    stderr = capfd.readouterr().err.splitlines()
    assert any(line.startswith("apple") for line in stderr)


def test_shell_cli_verbosity_stderr_with_explicit_stdout_off(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that commands can output to STDERR with STDOUT explicitly off."""

    dotfiles.write_config(
        [
            {
                "shell": [
                    {
                        "command": "echo apple >&2",
                        "stdout": False,
                    }
                ],
            }
        ]
    )
    run_dotbot("-vv")

    stderr = capfd.readouterr().err.splitlines()
    assert any(line.startswith("apple") for line in stderr)


def test_shell_cli_verbosity_stderr_with_defaults_stdout_off(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that commands can output to STDERR with defaults:shell:stdout=False."""

    dotfiles.write_config(
        [
            {
                "defaults": {
                    "shell": {
                        "stdout": False,
                    },
                },
            },
            {
                "shell": [
                    {"command": "echo apple >&2"},
                ],
            },
        ]
    )
    run_dotbot("-vv")

    stderr = capfd.readouterr().err.splitlines()
    assert any(line.startswith("apple") for line in stderr)


def test_shell_single_v_verbosity_stdout(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a single '-v' verbosity doesn't override stdout=False."""

    dotfiles.write_config([{"shell": [{"command": "echo apple"}]}])
    run_dotbot("-v")

    stdout = capfd.readouterr().out.splitlines()
    assert not any(line.startswith("apple") for line in stdout)


def test_shell_single_v_verbosity_stderr(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a single '-v' verbosity doesn't override stderr=False."""

    dotfiles.write_config([{"shell": [{"command": "echo apple >&2"}]}])
    run_dotbot("-v")

    stderr = capfd.readouterr().err.splitlines()
    assert not any(line.startswith("apple") for line in stderr)


def test_shell_compact_stdout_1(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that shell command stdout works in compact form."""

    dotfiles.write_config(
        [
            {"defaults": {"shell": {"stdout": True}}},
            {"shell": ["echo apple"]},
        ]
    )
    run_dotbot()

    stdout = capfd.readouterr().out.splitlines()
    assert any(line.startswith("apple") for line in stdout)


def test_shell_compact_stdout_2(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that shell command stdout works in compact form."""

    dotfiles.write_config(
        [
            {"defaults": {"shell": {"stdout": True}}},
            {"shell": [["echo apple", "echoing message"]]},
        ]
    )
    run_dotbot()

    stdout = capfd.readouterr().out.splitlines()
    assert any(line.startswith("apple") for line in stdout)
    assert any(line.startswith("echoing message") for line in stdout)


def test_shell_stdout_disabled_by_default(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the shell command disables stdout by default."""

    dotfiles.write_config(
        [
            {
                "shell": ["echo banana"],
            }
        ]
    )
    run_dotbot()

    stdout = capfd.readouterr().out.splitlines()
    assert not any(line.startswith("banana") for line in stdout)


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


def test_shell_quiet_default(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that quiet is off by default."""

    dotfiles.write_config(
        [
            {
                "shell": [
                    {
                        "command": "echo banana",
                        "description": "echoing a thing...",
                    }
                ],
            }
        ]
    )
    run_dotbot()

    stdout = capfd.readouterr().out.splitlines()
    assert not any(line.startswith("banana") for line in stdout)
    assert any("echo banana" in line for line in stdout)
    assert any(line.startswith("echoing a thing...") for line in stdout)


def test_shell_quiet_enabled_with_description(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that only the description is shown when quiet is enabled."""

    dotfiles.write_config(
        [
            {
                "shell": [
                    {
                        "command": "echo banana",
                        "description": "echoing a thing...",
                        "quiet": True,
                    }
                ],
            }
        ]
    )
    run_dotbot()

    stdout = capfd.readouterr().out.splitlines()
    assert not any(line.startswith("banana") for line in stdout)
    assert not any("echo banana" in line for line in stdout)
    assert any(line.startswith("echoing a thing...") for line in stdout)


def test_shell_quiet_enabled_without_description(
    capfd: pytest.CaptureFixture[str],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify nothing is shown when quiet is enabled with no description."""

    dotfiles.write_config(
        [
            {
                "shell": [
                    {
                        "command": "echo banana",
                        "quiet": True,
                    }
                ],
            }
        ]
    )
    run_dotbot()

    stdout = capfd.readouterr().out.splitlines()
    assert not any(line.startswith("banana") for line in stdout)
    assert not any(line.startswith("echo banana") for line in stdout)


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

    dotfiles.write_config([{"shell": [{"description": "no command"}]}])
    with pytest.raises(SystemExit):
        run_dotbot()

    stderr = capfd.readouterr().err
    assert (
        "An error was encountered while executing action shell: KeyError: 'command'"
        in stderr
    )
    assert "not handled" not in stderr


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
    assert lines == ["echo apple", "apple", "echo banana", "banana"]
