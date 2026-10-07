import contextlib
import os
import pathlib
import stat
import sys
from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest

from tests.conftest import Dotfiles


def readlink(path: str) -> str:
    """Read a symlink, without the prefix for long paths that Windows can add."""

    target = os.readlink(path)
    if sys.platform == "win32" and target.startswith("\\\\?\\"):
        target = target[4:]
    return target


@contextlib.contextmanager
def read_only(directory: str) -> Generator[None]:
    """Remove the write permissions of a directory, and restore them after."""

    mode = stat.S_IMODE(os.stat(directory).st_mode)
    os.chmod(directory, 0o555)
    try:
        yield
    finally:
        os.chmod(directory, mode)


def test_link_canonicalization(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify links to symlinked targets are canonical.

    "Canonical", here, means that dotbot does not create symlinks
    that point to intermediary symlinks.
    """

    dotfiles.write("f", "apple")
    dotfiles.write_config([{"link": {"~/.f": {"path": "f"}}}])

    # Point to the config file in a symlinked dotfiles directory.
    dotfiles_symlink = os.path.join(home, "dotfiles-symlink")
    os.symlink(dotfiles.directory, dotfiles_symlink)
    config_file = os.path.join(
        dotfiles_symlink, os.path.basename(dotfiles.config_filename)
    )
    run_dotbot("-c", config_file, custom=True)

    assert readlink(os.path.join(home, ".f")) == os.path.join(dotfiles.directory, "f")


@pytest.mark.parametrize("dst", ["~/.f", "~/f"])
@pytest.mark.parametrize("include_force", [True, False])
def test_link_default_target(
    dst: str,
    include_force: bool,  # noqa: FBT001
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that default targets are calculated correctly.

    This test includes verifying files with and without leading periods,
    as well as verifying handling of None dict values.
    """

    _ = home
    dotfiles.write("f", "apple")
    config = [
        {
            "link": {
                dst: {"force": False} if include_force else None,
            }
        }
    ]
    dotfiles.write_config(config)
    run_dotbot()

    with open(os.path.abspath(os.path.expanduser(dst))) as file:
        assert file.read() == "apple"


def test_link_environment_user_expansion_target(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify link expands user in target."""

    _ = home
    target = "~/f"
    link_name = "~/g"
    with open(os.path.abspath(os.path.expanduser(target)), "w") as file:
        file.write("apple")
    dotfiles.write_config([{"link": {link_name: target}}])
    run_dotbot()

    with open(os.path.abspath(os.path.expanduser(link_name))) as file:
        assert file.read() == "apple"


@pytest.mark.parametrize("target", ["$APPLE", {"path": "$APPLE"}])
def test_link_environment_variable_expansion_target(
    target: str | dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify link expands environment variables in target.

    The target can be in the short or in the extended config syntax.
    """

    monkeypatch.setenv("APPLE", "h")
    dotfiles.write("h", "grape")
    dotfiles.write_config([{"link": {"~/.i": target}}])
    run_dotbot()

    with open(os.path.join(home, ".i")) as file:
        assert file.read() == "grape"


def test_link_environment_variable_expansion_link_name(
    monkeypatch: pytest.MonkeyPatch,
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify link expands environment variables in link name."""

    monkeypatch.setenv("ORANGE", ".config")
    monkeypatch.setenv("BANANA", "g")
    dotfiles.write("f", "apple")
    dotfiles.write_config(
        [{"link": {"~/${ORANGE}/$BANANA": {"path": "f", "create": True}}}]
    )
    run_dotbot()

    with open(os.path.join(home, ".config", "g")) as file:
        assert file.read() == "apple"


def test_link_force_leaves_when_nonexistent(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify force doesn't erase existing files when targets are nonexistent."""

    os.mkdir(os.path.join(home, "dir"))
    open(os.path.join(home, "file"), "w").close()
    config = [
        {
            "link": {
                "~/dir": {"path": "dir", "force": True},
                "~/file": {"path": "file", "force": True},
            }
        }
    ]
    dotfiles.write_config(config)
    with pytest.raises(SystemExit):
        run_dotbot()

    assert os.path.isdir(os.path.join(home, "dir"))
    assert os.path.isfile(os.path.join(home, "file"))


def test_link_force_overwrite_symlink(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify force overwrites a symlinked directory."""

    os.mkdir(os.path.join(home, "dir"))
    dotfiles.write("dir/f")
    os.symlink(home, os.path.join(home, ".dir"))

    config = [{"link": {"~/.dir": {"path": "dir", "force": True}}}]
    dotfiles.write_config(config)
    run_dotbot()

    assert os.path.isfile(os.path.join(home, ".dir", "f"))


def test_link_force_directory(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify force deletes directories."""

    os.mkdir(os.path.join(home, ".dir"))
    with open(os.path.join(home, ".dir", "f"), "w") as f:
        f.write("apple")
    dotfiles.write("dir/f", "banana")

    config = [{"link": {"~/.dir": {"path": "dir", "force": True}}}]
    dotfiles.write_config(config)
    run_dotbot()

    with open(os.path.join(home, ".dir", "f")) as file:
        assert file.read() == "banana"


def test_link_backup_directory(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that a backup directory is created if destination directory exists."""

    os.mkdir(os.path.join(home, ".dir"))
    with open(os.path.join(home, ".dir", "f"), "w") as f:
        f.write("apple")
    dotfiles.write("dir/f", "banana")

    config = [{"link": {"~/.dir": {"path": "dir", "backup": True}}}]
    dotfiles.write_config(config)
    run_dotbot()

    backup_dirs = [d for d in os.listdir(home) if d.startswith(".dir.dotbot-backup")]
    assert len(backup_dirs) == 1
    with open(os.path.join(home, backup_dirs[0], "f")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, ".dir", "f")) as file:
        assert file.read() == "banana"


@pytest.mark.parametrize(
    "options",
    [
        pytest.param({}, id="backup"),
        pytest.param({"force": True}, id="force"),
        pytest.param({"relink": True}, id="relink"),
    ],
)
def test_link_backup_file(
    options: dict[str, bool],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a backup file is created if destination file exists.

    With force or relink, the file is backed up too, not removed.
    """

    with open(os.path.join(home, ".file"), "w") as f:
        f.write("apple")
    dotfiles.write("file", "banana")

    config = [{"link": {"~/.file": {"path": "file", "backup": True, **options}}}]
    dotfiles.write_config(config)
    run_dotbot()

    backup_files = [f for f in os.listdir(home) if f.startswith(".file.dotbot-backup")]
    assert len(backup_files) == 1
    with open(os.path.join(home, backup_files[0])) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, ".file")) as file:
        assert file.read() == "banana"


def test_link_backup_not_created_if_link(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that a backup file isn't created if destination is a symlink."""

    open(os.path.join(home, "file"), "w").close()
    dotfiles.write("file")
    os.symlink(os.path.join(home, "file"), os.path.join(home, ".file"))

    config = [{"link": {"~/.file": {"path": "file", "backup": True}}}]
    dotfiles.write_config(config)
    with pytest.raises(SystemExit):
        run_dotbot()

    assert os.path.islink(os.path.join(home, ".file"))
    assert not any(".dotbot-backup." in name for name in os.listdir(home))


def test_link_backup_error_if_dest_already_exists(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify an error is thrown if the backup already exists."""

    os.mkdir(os.path.join(home, ".dir"))
    # create fake backup directories; this test is technically timing dependent but it should work out in practice
    now = datetime.now(UTC).astimezone()
    for delta in range(10):
        timestamp = (now + timedelta(seconds=delta)).strftime("%Y%m%d-%H%M%S")
        os.mkdir(os.path.join(home, f".dir.dotbot-backup.{timestamp}"))
        with open(
            os.path.join(home, f".dir.dotbot-backup.{timestamp}", "f"), "w"
        ) as file:
            file.write("apple")
    dotfiles.write("dir")

    config = [{"link": {"~/.dir": {"path": "dir", "backup": True}}}]
    dotfiles.write_config(config)
    with pytest.raises(SystemExit):
        run_dotbot()

    for delta in range(10):
        timestamp = (now + timedelta(seconds=delta)).strftime("%Y%m%d-%H%M%S")
        with open(os.path.join(home, f".dir.dotbot-backup.{timestamp}", "f")) as file:
            assert file.read() == "apple"


def test_link_backup_glob(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that backup works with globbing."""
    dotfiles.write("bin/a", "apple")
    dotfiles.write("bin/b", "banana")
    dotfiles.write("bin/c", "cherry")

    os.mkdir(os.path.join(home, "bin"))
    with open(os.path.join(home, "bin", "a"), "w") as f:
        f.write("apricot")
    with open(os.path.join(home, "bin", "b"), "w") as f:
        f.write("blueberry")
    with open(os.path.join(home, "bin", "c"), "w") as f:
        f.write("cranberry")

    config = [
        {
            "defaults": {"link": {"glob": True, "create": True, "backup": True}},
        },
        {
            "link": {"~/bin": "bin/*"},
        },
    ]
    dotfiles.write_config(config)
    run_dotbot()

    backup_a = [
        f
        for f in os.listdir(os.path.join(home, "bin"))
        if f.startswith("a.dotbot-backup")
    ]
    backup_b = [
        f
        for f in os.listdir(os.path.join(home, "bin"))
        if f.startswith("b.dotbot-backup")
    ]
    backup_c = [
        f
        for f in os.listdir(os.path.join(home, "bin"))
        if f.startswith("c.dotbot-backup")
    ]
    assert len(backup_a) == 1
    assert len(backup_b) == 1
    assert len(backup_c) == 1
    with open(os.path.join(home, "bin", backup_a[0])) as file:
        assert file.read() == "apricot"
    with open(os.path.join(home, "bin", backup_b[0])) as file:
        assert file.read() == "blueberry"
    with open(os.path.join(home, "bin", backup_c[0])) as file:
        assert file.read() == "cranberry"

    with open(os.path.join(home, "bin", "a")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, "bin", "b")) as file:
        assert file.read() == "banana"
    with open(os.path.join(home, "bin", "c")) as file:
        assert file.read() == "cherry"


def test_link_backup_dry_run(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a backup file is not created if running in dry-run mode.

    With force, the dry run doesn't claim to remove the file, because the
    backup moves it away.
    """

    with open(os.path.join(home, ".file"), "w") as f:
        f.write("apple")
    dotfiles.write("file", "banana")

    config = [{"link": {"~/.file": {"path": "file", "backup": True, "force": True}}}]
    dotfiles.write_config(config)
    run_dotbot("-n")

    backup_files = [f for f in os.listdir(home) if f.startswith(".file.dotbot-backup")]
    assert len(backup_files) == 0
    with open(os.path.join(home, ".file")) as file:
        assert file.read() == "apple"

    link = os.path.join("~", ".file")
    target = os.path.join(dotfiles.directory, "file")
    lines = capfd.readouterr().out.splitlines()
    assert any(line.startswith(f"Would backup {link} to ") for line in lines)
    assert f"Would remove {link}" not in lines
    assert f"Would create symlink {link} -> {target}" in lines


@pytest.mark.parametrize("option", ["relink", "force"])
def test_link_backup_relink_force_with_existing_incorrect_symlink(
    option: str,
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that backup + relink/force replaces an incorrect symlink.

    When an incorrect symlink exists at the destination, backup should not
    prevent the symlink from being deleted and recreated correctly.
    """

    dotfiles.write("f", "apple")
    # Create an incorrect symlink at the destination.
    wrong_target = os.path.join(home, "wrong_target")
    open(wrong_target, "w").close()
    os.symlink(wrong_target, os.path.join(home, ".f"))

    config = [{"link": {"~/.f": {"path": "f", "backup": True, option: True}}}]
    dotfiles.write_config(config)
    run_dotbot()

    # The symlink should now point to the correct target.
    with open(os.path.join(home, ".f")) as file:
        assert file.read() == "apple"
    # Symlinks are not backed up (backup only applies to real files).
    backup_files = [f for f in os.listdir(home) if f.startswith(".f.dotbot-backup")]
    assert len(backup_files) == 0


def test_link_backup_relink_with_existing_incorrect_symlink_glob(
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that backup + relink replaces incorrect symlinks with globbing."""

    dotfiles.write("bin/a", "apple")
    dotfiles.write("bin/b", "banana")

    os.makedirs(os.path.join(home, "bin"))
    # Create incorrect symlinks at the destinations.
    wrong_target = os.path.join(home, "wrong_target")
    open(wrong_target, "w").close()
    os.symlink(wrong_target, os.path.join(home, "bin", "a"))
    os.symlink(wrong_target, os.path.join(home, "bin", "b"))

    config = [
        {
            "defaults": {
                "link": {"glob": True, "create": True, "backup": True, "relink": True}
            }
        },
        {"link": {"~/bin": "bin/*"}},
    ]
    dotfiles.write_config(config)
    run_dotbot()

    with open(os.path.join(home, "bin", "a")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, "bin", "b")) as file:
        assert file.read() == "banana"


@pytest.mark.parametrize("link_name", ["~/bin", "~/bin/"])
def test_link_glob(
    link_name: str, home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify globbing works, also with a trailing slash in the link name."""

    dotfiles.write("bin/a", "apple")
    dotfiles.write("bin/b", "banana")
    dotfiles.write("bin/c", "cherry")
    dotfiles.write_config(
        [
            {"defaults": {"link": {"glob": True, "create": True}}},
            {"link": {link_name: "bin/*"}},
        ]
    )
    run_dotbot()

    with open(os.path.join(home, "bin", "a")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, "bin", "b")) as file:
        assert file.read() == "banana"
    with open(os.path.join(home, "bin", "c")) as file:
        assert file.read() == "cherry"


def test_link_glob_at_root(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify globbing works at the root of the home and dotfiles directories."""

    dotfiles.write(".a", "dot-apple")
    dotfiles.write(".b", "dot-banana")
    dotfiles.write(".c", "dot-cherry")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~": {
                        "path": ".*",
                        "glob": True,
                    },
                },
            }
        ]
    )
    run_dotbot()

    with open(os.path.join(home, ".a")) as file:
        assert file.read() == "dot-apple"
    with open(os.path.join(home, ".b")) as file:
        assert file.read() == "dot-banana"
    with open(os.path.join(home, ".c")) as file:
        assert file.read() == "dot-cherry"


def test_link_glob_force(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that glob/force work together."""

    os.mkdir(os.path.join(home, "bin"))
    with open(os.path.join(home, "bin", "a"), "w") as f:
        f.write("apricot")
    with open(os.path.join(home, "bin", "b"), "w") as f:
        f.write("blueberry")
    with open(os.path.join(home, "bin", "c"), "w") as f:
        f.write("cranberry")

    dotfiles.write("bin/a", "apple")
    dotfiles.write("bin/b", "banana")
    dotfiles.write("bin/c", "cherry")
    dotfiles.write_config(
        [
            {"defaults": {"link": {"glob": True, "create": True, "force": True}}},
            {"link": {"~/bin": "bin/*"}},
        ]
    )
    run_dotbot()

    with open(os.path.join(home, "bin", "a")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, "bin", "b")) as file:
        assert file.read() == "banana"
    with open(os.path.join(home, "bin", "c")) as file:
        assert file.read() == "cherry"


@pytest.mark.parametrize("path", ["foo", "foo/"])
def test_link_glob_ignore_no_glob_chars(
    path: str, home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that glob links a path without glob characters as it is."""

    dotfiles.makedirs("foo")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/foo/": {
                        "path": path,
                        "glob": True,
                    }
                }
            }
        ]
    )
    run_dotbot()
    assert os.path.islink(os.path.join(home, "foo"))
    assert os.path.exists(os.path.join(home, "foo"))


def test_link_glob_exclude(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify link globbing with an explicit exclusion."""

    dotfiles.write("config/foo/a", "apple")
    dotfiles.write("config/bar/b", "banana")
    dotfiles.write("config/bar/c", "cherry")
    dotfiles.write("config/baz/d", "donut")
    dotfiles.write_config(
        [
            {
                "defaults": {
                    "link": {
                        "glob": True,
                        "create": True,
                    },
                },
            },
            {
                "link": {
                    "~/.config/": {
                        "path": "config/*",
                        "exclude": ["config/baz"],
                    },
                },
            },
        ]
    )
    run_dotbot()

    assert not os.path.exists(os.path.join(home, ".config", "baz"))

    assert not os.path.islink(os.path.join(home, ".config"))
    assert os.path.islink(os.path.join(home, ".config", "foo"))
    assert os.path.islink(os.path.join(home, ".config", "bar"))
    with open(os.path.join(home, ".config", "foo", "a")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, ".config", "bar", "b")) as file:
        assert file.read() == "banana"
    with open(os.path.join(home, ".config", "bar", "c")) as file:
        assert file.read() == "cherry"


def test_link_glob_exclude_nested(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify deep link globbing with an explicit exclusion."""

    dotfiles.write("config/foo/a", "apple")
    dotfiles.write("config/bar/b", "banana")
    dotfiles.write("config/bar/c", "cherry")
    dotfiles.write("config/baz/d", "donut")
    dotfiles.write("config/baz/buzz/e", "egg")
    dotfiles.write("config/baz/bizz/g", "grape")
    dotfiles.write_config(
        [
            {
                "defaults": {
                    "link": {
                        "glob": True,
                        "create": True,
                    },
                },
            },
            {
                "link": {
                    "~/.config/": {
                        "path": "config/*/*",
                        "exclude": ["config/baz/buzz"],
                    },
                },
            },
        ]
    )
    run_dotbot()

    assert not os.path.exists(os.path.join(home, ".config", "baz", "buzz"))

    assert not os.path.islink(os.path.join(home, ".config"))
    assert not os.path.islink(os.path.join(home, ".config", "foo"))
    assert not os.path.islink(os.path.join(home, ".config", "bar"))
    assert not os.path.islink(os.path.join(home, ".config", "baz"))
    assert os.path.islink(os.path.join(home, ".config", "baz", "bizz"))
    assert os.path.islink(os.path.join(home, ".config", "foo", "a"))
    with open(os.path.join(home, ".config", "foo", "a")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, ".config", "bar", "b")) as file:
        assert file.read() == "banana"
    with open(os.path.join(home, ".config", "bar", "c")) as file:
        assert file.read() == "cherry"
    with open(os.path.join(home, ".config", "baz", "d")) as file:
        assert file.read() == "donut"
    with open(os.path.join(home, ".config", "baz", "bizz", "g")) as file:
        assert file.read() == "grape"


def test_link_glob_exclude_multiple(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify deep link globbing with multiple globbed exclusions."""

    dotfiles.write("config/foo/a", "apple")
    dotfiles.write("config/bar/b", "banana")
    dotfiles.write("config/bar/c", "cherry")
    dotfiles.write("config/baz/d", "donut")
    dotfiles.write("config/baz/buzz/e", "egg")
    dotfiles.write("config/baz/bizz/g", "grape")
    dotfiles.write("config/fiz/f", "fig")
    dotfiles.write_config(
        [
            {
                "defaults": {
                    "link": {
                        "glob": True,
                        "create": True,
                    },
                },
            },
            {
                "link": {
                    "~/.config/": {
                        "path": "config/*/*",
                        "exclude": ["config/baz/*", "config/fiz/*"],
                    },
                },
            },
        ]
    )
    run_dotbot()

    assert not os.path.exists(os.path.join(home, ".config", "baz"))
    assert not os.path.exists(os.path.join(home, ".config", "fiz"))

    assert not os.path.islink(os.path.join(home, ".config"))
    assert not os.path.islink(os.path.join(home, ".config", "foo"))
    assert not os.path.islink(os.path.join(home, ".config", "bar"))
    assert os.path.islink(os.path.join(home, ".config", "foo", "a"))
    with open(os.path.join(home, ".config", "foo", "a")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, ".config", "bar", "b")) as file:
        assert file.read() == "banana"
    with open(os.path.join(home, ".config", "bar", "c")) as file:
        assert file.read() == "cherry"


@pytest.mark.parametrize(
    ("pattern", "expect_file"),
    [
        ("conf/*", lambda fruit: fruit),
        ("conf/.*", lambda fruit: "." + fruit),
        ("conf/[bc]*", lambda fruit: fruit if fruit[0] in "bc" else None),
        ("conf/*e", lambda fruit: fruit if fruit[-1] == "e" else None),
        ("conf/??r*", lambda fruit: fruit if fruit[2] == "r" else None),
    ],
)
def test_link_glob_patterns(
    pattern: str,
    expect_file: Callable[[str], str | None],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify link glob pattern matching."""

    fruits = ["apple", "apricot", "banana", "cherry", "currant", "cantalope"]
    for fruit in fruits:
        dotfiles.write("conf/" + fruit, fruit)
        dotfiles.write("conf/." + fruit, "dot-" + fruit)
    dotfiles.write_config(
        [
            {"defaults": {"link": {"glob": True, "create": True}}},
            {"link": {"~/globtest": pattern}},
        ]
    )
    run_dotbot()

    for fruit in fruits:
        expected = expect_file(fruit)
        if expected is None:
            assert not os.path.exists(os.path.join(home, "globtest", fruit))
            assert not os.path.exists(os.path.join(home, "globtest", "." + fruit))
        elif "." in expected:
            assert not os.path.islink(os.path.join(home, "globtest", fruit))
            assert os.path.islink(os.path.join(home, "globtest", "." + fruit))
        else:  # "." not in expected
            assert os.path.islink(os.path.join(home, "globtest", fruit))
            assert not os.path.islink(os.path.join(home, "globtest", "." + fruit))


def test_link_glob_recursive(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify recursive link globbing and exclusions."""

    dotfiles.write("config/foo/bar/a", "apple")
    dotfiles.write("config/foo/bar/b", "banana")
    dotfiles.write("config/foo/bar/c", "cherry")
    dotfiles.write_config(
        [
            {"defaults": {"link": {"glob": True, "create": True}}},
            {"link": {"~/.config/": {"path": "config/**", "exclude": ["config/**/b"]}}},
        ]
    )
    run_dotbot()

    assert not os.path.islink(os.path.join(home, ".config"))
    assert not os.path.islink(os.path.join(home, ".config", "foo"))
    assert not os.path.islink(os.path.join(home, ".config", "foo", "bar"))
    assert os.path.islink(os.path.join(home, ".config", "foo", "bar", "a"))
    assert not os.path.exists(os.path.join(home, ".config", "foo", "bar", "b"))
    assert os.path.islink(os.path.join(home, ".config", "foo", "bar", "c"))
    with open(os.path.join(home, ".config", "foo", "bar", "a")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, ".config", "foo", "bar", "c")) as file:
        assert file.read() == "cherry"


def test_link_glob_single_match(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify linking works even when glob matches exactly one file."""
    # regression test for https://github.com/anishathalye/dotbot/issues/282

    dotfiles.write("foo/a", "apple")
    dotfiles.write_config(
        [
            {"defaults": {"link": {"glob": True, "create": True}}},
            {"link": {"~/.config/foo": "foo/*"}},
        ]
    )
    run_dotbot()

    assert not os.path.islink(os.path.join(home, ".config"))
    assert not os.path.islink(os.path.join(home, ".config", "foo"))
    assert os.path.islink(os.path.join(home, ".config", "foo", "a"))
    with open(os.path.join(home, ".config", "foo", "a")) as file:
        assert file.read() == "apple"


def test_link_if(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify 'if' directives are checked when linking."""

    dotfiles.write("f", "apple")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/.f": {"path": "f", "if": "exit 0"},
                    "~/.g": {"path": "f", "if": "exit 1"},
                    "~/.h": {"path": "f", "if": "badcommand"},
                },
            }
        ]
    )
    run_dotbot()

    assert not os.path.exists(os.path.join(home, ".g"))
    assert not os.path.exists(os.path.join(home, ".h"))
    with open(os.path.join(home, ".f")) as file:
        assert file.read() == "apple"


def test_link_if_defaults(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify 'if' directive defaults are checked when linking."""

    dotfiles.write("f", "apple")
    dotfiles.write_config(
        [
            {
                "defaults": {
                    "link": {
                        "if": "exit 1",
                    },
                },
            },
            {
                "link": {
                    "~/.j": {"path": "f", "if": "exit 0"},
                    "~/.k": {"path": "f"},  # default is false
                },
            },
        ]
    )
    run_dotbot()

    assert not os.path.exists(os.path.join(home, ".k"))
    with open(os.path.join(home, ".j")) as file:
        assert file.read() == "apple"


def test_link_ignore_missing(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that ignore-missing links a missing target."""

    dotfiles.write_config(
        [{"link": {"~/missing_link": {"path": "missing", "ignore-missing": True}}}]
    )
    run_dotbot()

    assert os.path.islink(os.path.join(home, "missing_link"))
    assert not os.path.exists(os.path.join(home, "missing_link"))


@pytest.mark.parametrize("relink", [False, True])
def test_link_leaves_file(
    relink: bool,  # noqa: FBT001
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify link does not overwrite a file, also with relink."""

    dotfiles.write("f", "apple")
    with open(os.path.join(home, ".f"), "w") as file:
        file.write("grape")
    dotfiles.write_config([{"link": {"~/.f": {"path": "f", "relink": relink}}}])
    with pytest.raises(SystemExit):
        run_dotbot()

    with open(os.path.join(home, ".f")) as file:
        assert file.read() == "grape"


@pytest.mark.parametrize("key", ["canonicalize-path", "canonicalize"])
def test_link_no_canonicalize(
    key: str, home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify link canonicalization can be disabled."""

    dotfiles.write("f", "apple")
    dotfiles.write_config(
        [{"defaults": {"link": {key: False}}}, {"link": {"~/.f": {"path": "f"}}}]
    )
    os.symlink(
        dotfiles.directory,
        os.path.join(home, "dotfiles-symlink"),
        target_is_directory=True,
    )
    run_dotbot(
        "-c",
        os.path.join(
            home, "dotfiles-symlink", os.path.basename(dotfiles.config_filename)
        ),
        custom=True,
    )
    assert "dotfiles-symlink" in os.readlink(os.path.join(home, ".f"))


def test_link_prefix(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify link prefixes are prepended."""

    dotfiles.write("conf/a", "apple")
    dotfiles.write("conf/b", "banana")
    dotfiles.write("conf/c", "cherry")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/": {
                        "glob": True,
                        "path": "conf/*",
                        "prefix": ".",
                    },
                },
            }
        ]
    )
    run_dotbot()
    with open(os.path.join(home, ".a")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, ".b")) as file:
        assert file.read() == "banana"
    with open(os.path.join(home, ".c")) as file:
        assert file.read() == "cherry"


def test_link_relative(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Test relative linking works."""

    dotfiles.write("f", "apple")
    dotfiles.write("d/e", "grape")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/.f": {
                        "path": "f",
                    },
                    "~/.frel": {
                        "path": "f",
                        "relative": True,
                    },
                    "~/nested/.frel": {
                        "path": "f",
                        "relative": True,
                        "create": True,
                    },
                    "~/.d": {
                        "path": "d",
                        "relative": True,
                    },
                },
            }
        ]
    )
    run_dotbot()

    assert readlink(os.path.join(home, ".f")) == os.path.join(dotfiles.directory, "f")
    assert readlink(os.path.join(home, ".frel")) == os.path.normpath("../../dotfiles/f")
    assert readlink(os.path.join(home, "nested", ".frel")) == os.path.normpath(
        "../../../dotfiles/f"
    )
    assert readlink(os.path.join(home, ".d")) == os.path.normpath("../../dotfiles/d")

    with open(os.path.join(home, ".f")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, ".frel")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, "nested", ".frel")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, ".d", "e")) as file:
        assert file.read() == "grape"


@pytest.mark.parametrize(
    ("config", "relinked"),
    [
        pytest.param([{"link": {"~/.f": "f"}}], False, id="default"),
        pytest.param(
            [{"link": {"~/.f": {"path": "f", "relink": True}}}], True, id="option"
        ),
        pytest.param(
            [{"defaults": {"link": {"relink": True}}}, {"link": {"~/.f": "f"}}],
            True,
            id="defaults",
        ),
    ],
)
def test_link_relink_overwrite_symlink(
    config: list[dict[str, Any]],
    relinked: bool,  # noqa: FBT001
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that only relink overwrites a symlink that points somewhere else."""

    with open(os.path.join(home, "f"), "w") as file:
        file.write("grape")
    os.symlink(os.path.join(home, "f"), os.path.join(home, ".f"))
    dotfiles.write("f", "apple")
    dotfiles.write_config(config)
    if relinked:
        run_dotbot()
    else:
        with pytest.raises(SystemExit):
            run_dotbot()

    with open(os.path.join(home, ".f")) as file:
        assert file.read() == ("apple" if relinked else "grape")


def test_link_relink_relative_keeps_link(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify relink doesn't replace a relative link that is correct."""

    _ = home
    dotfiles.write("f", "apple")
    link = {"path": "f", "create": True, "relative": True}
    dotfiles.write_config([{"link": {"~/.folder/f": link}}])
    run_dotbot()
    dotfiles.write_config([{"link": {"~/.folder/f": {**link, "relink": True}}}])
    capfd.readouterr()
    run_dotbot()

    assert capfd.readouterr().out.splitlines()[-1] == "Done (no changes)"


def test_link_summary(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the summary line counts the result of each link."""

    dotfiles.write("f")
    dotfiles.write("c", "apple")
    for name in [".kept", ".updated"]:
        with open(os.path.join(home, name), "w") as file:
            file.write("banana")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/.f": "f",
                    "~/.kept": {"path": "c", "type": "copy"},
                    "~/.updated": {"path": "c", "type": "copy", "force": True},
                    "~/.skipped": {"path": "f", "if": "exit 1"},
                    "~/.missing": "missing",
                }
            },
            {"link": {}},
        ]
    )

    expected = [
        (
            ["--dry-run"],
            "link: 1 to create, 1 to update, 1 kept with local changes, "
            "1 skipped, 1 failed",
        ),
        (
            [],
            "link: 1 created, 1 updated, 1 kept with local changes, "
            "1 skipped, 1 failed",
        ),
        ([], "link: 2 in place, 1 kept with local changes, 1 skipped, 1 failed"),
    ]
    for arguments, summary in expected:
        with pytest.raises(SystemExit):
            run_dotbot(*arguments)
        lines = capfd.readouterr().out.splitlines()
        assert lines[-2:] == [summary, "link: nothing to do"]


def test_target_is_not_overwritten_by_symlink_trickery(
    capsys: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that force doesn't remove a target that is behind a symlink.

    The link name is in a symlinked directory, so it's the target itself.
    """

    dotfiles_path = pathlib.Path(dotfiles.directory)
    home_path = pathlib.Path(home)

    # Setup:
    #   *   A symlink exists from `~/.ssh` to `ssh` in the dotfiles directory.
    #   *   Dotbot is configured to force-recreate a symlink between two paths
    #       when, in reality, it's actually the same file when resolved.
    ssh_config = (dotfiles_path / "ssh/config").absolute()
    os.mkdir(str(ssh_config.parent))
    ssh_config.write_text("preserve me!")
    os.symlink(str(ssh_config.parent), str(home_path / ".ssh"))
    dotfiles.write_config(
        [
            {
                "defaults": {
                    "link": {
                        "relink": True,
                        "create": True,
                        "force": True,
                    },
                }
            },
            {
                "link": {
                    # When symlinks are resolved, these are actually the same file.
                    "~/.ssh/config": "ssh/config",
                },
            },
        ]
    )

    # Execute dotbot.
    with pytest.raises(SystemExit):
        run_dotbot()

    _, stderr = capsys.readouterr()
    assert "appears to be the same file" in stderr
    # Verify that the file was not overwritten.
    assert ssh_config.read_text() == "preserve me!"


@pytest.mark.parametrize(
    "config",
    [
        pytest.param([{"link": {"~/.f": "f"}}], id="unspecified"),
        pytest.param(
            [{"link": {"~/.f": {"path": "f", "type": "symlink"}}}],
            id="specified",
        ),
        pytest.param(
            [
                {"defaults": {"link": {"type": "symlink"}}},
                {"link": {"~/.f": "f"}},
            ],
            id="symlink set for all links by default",
        ),
    ],
)
def test_link_type_symlink(
    config: list[dict[str, Any]],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that symlinks are created by default, and when specified."""

    dotfiles.write("f", "apple")
    dotfiles.write_config(config)
    run_dotbot()

    assert os.path.islink(os.path.join(home, ".f"))


@pytest.mark.parametrize(
    "config",
    [
        pytest.param(
            [{"link": {"~/.f": {"path": "f", "type": "hardlink"}}}],
            id="specified",
        ),
        pytest.param(
            [
                {"defaults": {"link": {"type": "hardlink"}}},
                {"link": {"~/.f": "f"}},
            ],
            id="hardlink set for all links by default",
        ),
    ],
)
def test_link_type_hardlink(
    config: list[dict[str, Any]],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that hardlinks are created when specified."""

    dotfiles.write("f", "apple")
    assert os.stat(os.path.join(dotfiles.directory, "f")).st_nlink == 1
    dotfiles.write_config(config)
    run_dotbot()

    assert not os.path.islink(os.path.join(home, ".f"))
    assert os.stat(os.path.join(dotfiles.directory, "f")).st_nlink == 2
    assert os.stat(os.path.join(home, ".f")).st_nlink == 2


@pytest.mark.parametrize(
    "config",
    [
        pytest.param(
            [{"defaults": {"link": {"type": "default-bogus"}}, "link": {}}],
            id="default link type not recognized",
        ),
        pytest.param(
            [{"link": {"~/.f": {"type": "specified-bogus"}}}],
            id="specified link type not recognized",
        ),
    ],
)
def test_unknown_link_type(
    capsys: pytest.CaptureFixture[str],
    config: list[dict[str, Any]],
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that unknown link types are rejected."""

    dotfiles.write_config(config)
    with pytest.raises(SystemExit):
        run_dotbot()
    _, stderr = capsys.readouterr()
    assert "link type is not recognized" in stderr


def test_symlink_exists_when_hardlink_requested(
    capsys: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Confirm messaging when a symlink exists but a hardlink is requested."""

    # Setup: Create a symlink to the hardlink target.
    dotfiles.write("target", "potato")
    os.symlink(
        os.path.join(dotfiles.directory, "target"),
        os.path.join(home, "hardlink"),
    )

    # Act
    dotfiles.write_config(
        [{"link": {"~/hardlink": {"path": "target", "type": "hardlink"}}}]
    )
    with pytest.raises(SystemExit):
        run_dotbot()

    # Verify
    _, stderr = capsys.readouterr()
    assert "already exists but is a symbolic link, not a hard link" in stderr


def test_hardlink_already_exists(
    capsys: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Confirm messaging when the hardlink already exists."""

    dotfiles.write("target", "potato")
    os.link(
        os.path.join(dotfiles.directory, "target"),
        os.path.join(home, "hardlink"),
    )

    # Act
    dotfiles.write_config(
        [{"link": {"~/hardlink": {"path": "target", "type": "hardlink"}}}]
    )
    run_dotbot("-v")

    # Verify
    stdout, _ = capsys.readouterr()
    assert "Link exists" in stdout


def test_hardlink_ignore_missing_with_existing_file(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a file at a hardlink with a missing target fails with a warning.

    With ignore-missing, the target can be missing, and it can't be compared
    with the file.
    """

    with open(os.path.join(home, "f"), "w") as file:
        file.write("apple")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/f": {
                        "path": "missing",
                        "type": "hardlink",
                        "ignore-missing": True,
                    }
                }
            }
        ]
    )
    with pytest.raises(SystemExit):
        run_dotbot()

    stderr = capfd.readouterr().err
    assert "already exists but is a file, not a hard link" in stderr
    assert "An error was encountered" not in stderr


def test_broken_symlink_shows_invalid_link_message(
    capsys: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that broken symlinks show 'Invalid link' message instead of 'Linking failed'."""

    broken_target = os.path.join(home, "nonexistent")
    link_name = os.path.join(home, ".f")
    os.symlink(broken_target, link_name)

    dotfiles.write("f", "apple")
    dotfiles.write_config([{"link": {"~/.f": "f"}}])

    with pytest.raises(SystemExit):
        run_dotbot()

    _, stderr = capsys.readouterr()
    assert "Invalid link" in stderr
    assert "Linking failed" not in stderr


def test_link_dry_run(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the link plugin does not create links during a dry run."""

    dotfiles.write("f", "apple")
    dotfiles.write("g", "pear")
    dotfiles.write("h", "banana")
    os.symlink(os.path.join(dotfiles.directory, "g"), os.path.join(home, ".g"))
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/.f": "f",
                    "~/.g": {"path": None, "relink": True},
                    "~/.h": {"path": "h", "type": "hardlink"},
                }
            }
        ]
    )
    run_dotbot("-n", "-v")

    assert not os.path.exists(os.path.join(home, ".f"))

    lines = capfd.readouterr().out.splitlines()
    assert (
        f"Link exists {os.path.join('~', '.g')} -> {os.path.join(dotfiles.directory, 'g')}"
        in lines
    )
    assert (
        f"Would create symlink {os.path.join('~', '.f')} -> {os.path.join(dotfiles.directory, 'f')}"
        in lines
    )
    assert (
        f"Would create hardlink {os.path.join('~', '.h')} -> {os.path.join(dotfiles.directory, 'h')}"
        in lines
    )


def test_link_dry_run_if(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the link plugin does run condition checks during a dry run."""

    dotfiles.write("f", "apple")
    dotfiles.write("g", "pear")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/.f": {
                        "path": "f",
                        "if": "touch " + os.path.join(home, "side_effect"),
                    },
                    "~/.g": {
                        "path": "g",
                        "if": "exit 1",
                    },
                }
            }
        ]
    )
    run_dotbot("-n")

    assert os.path.exists(os.path.join(home, "side_effect"))
    assert not os.path.exists(os.path.join(home, ".f"))

    lines = capfd.readouterr().out.splitlines()
    assert (
        f"Would create symlink {os.path.join('~', '.f')} -> {os.path.join(dotfiles.directory, 'f')}"
        in lines
    )
    assert not any(
        line.startswith(f"Would create symlink {os.path.join('~', '.g')} ")
        for line in lines
    )


def test_link_dry_run_create(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the link plugin does not create parent directories during a dry run."""

    dotfiles.write("f", "apple")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/.config/.f": {
                        "path": "f",
                        "create": True,
                    }
                }
            }
        ]
    )
    run_dotbot("-n")
    assert not os.path.exists(os.path.join(home, ".config"))
    assert not os.path.exists(os.path.join(home, ".config", ".f"))

    lines = capfd.readouterr().out.splitlines()
    assert f"Would create directory {os.path.join('~', '.config')}" in lines
    assert (
        f"Would create symlink {os.path.join('~', '.config', '.f')} -> {os.path.join(dotfiles.directory, 'f')}"
        in lines
    )


def test_link_dry_run_relink(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the link plugin does not relink existing links during a dry run."""

    dotfiles.write("f", "apple")
    dotfiles.write("g", "pear")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/.f": {
                        "path": "f",
                        "relink": True,
                    }
                }
            }
        ]
    )
    os.symlink(os.path.join(dotfiles.directory, "g"), os.path.join(home, ".f"))
    run_dotbot("-n")
    with open(os.path.join(home, ".f")) as file:
        assert file.read() == "pear"

    lines = capfd.readouterr().out.splitlines()
    assert f"Would remove {os.path.join('~', '.f')}" in lines
    assert (
        f"Would create symlink {os.path.join('~', '.f')} -> {os.path.join(dotfiles.directory, 'f')}"
        in lines
    )


def test_link_dry_run_overwrite(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that the link plugin does not delete existing files during a dry run."""

    dotfiles.write("f", "apple")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/.f": {
                        "path": "f",
                        "force": True,
                    }
                }
            }
        ]
    )
    with open(os.path.join(home, ".f"), "w") as file:
        file.write("pear")
    run_dotbot("-n")
    with open(os.path.join(home, ".f")) as file:
        assert file.read() == "pear"

    lines = capfd.readouterr().out.splitlines()
    assert f"Would remove {os.path.join('~', '.f')}" in lines
    assert (
        f"Would create symlink {os.path.join('~', '.f')} -> {os.path.join(dotfiles.directory, 'f')}"
        in lines
    )


@pytest.mark.skipif(
    "sys.platform == 'win32'",
    reason="Permissions work differently on Windows",
)
@pytest.mark.skipif(
    "hasattr(os, 'getuid') and os.getuid() == 0",
    reason="Root bypasses permission checks",
)
@pytest.mark.parametrize(
    ("link_name", "options", "error"),
    [
        pytest.param(".f", {}, "Linking failed ~/subdir/.f -> {target}", id="link"),
        pytest.param(
            "d/.f",
            {"create": True},
            "Failed to create directory ~/subdir/d",
            id="create",
        ),
        pytest.param(
            "existing",
            {"force": True},
            "Failed to remove ~/subdir/existing",
            id="remove",
        ),
    ],
)
def test_link_permission_error(
    link_name: str,
    options: dict[str, bool],
    error: str,
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that link reports the errors of the file system with their reason."""

    subdir = os.path.join(home, "subdir")
    os.makedirs(subdir)
    with open(os.path.join(subdir, "existing"), "w") as file:
        file.write("grape")
    dotfiles.write("f", "apple")
    dotfiles.write_config(
        [{"link": {f"~/subdir/{link_name}": {"path": "f", **options}}}]
    )
    with read_only(subdir), pytest.raises(SystemExit):
        run_dotbot()

    error = error.format(target=os.path.join(dotfiles.directory, "f"))
    assert f"error: {error}: Permission denied" in capfd.readouterr().err.splitlines()


def test_link_dry_run_relink_regular_file(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a dry run doesn't claim that relink replaces a regular file.

    Without force, relink only replaces symlinks, so the dry run must fail like
    the real run.
    """

    dotfiles.write("f", "apple")
    dotfiles.write_config([{"link": {"~/.f": {"path": "f", "relink": True}}}])
    with open(os.path.join(home, ".f"), "w") as file:
        file.write("pear")
    with pytest.raises(SystemExit):
        run_dotbot("-n")
    with open(os.path.join(home, ".f")) as file:
        assert file.read() == "pear"

    output = capfd.readouterr()
    assert "Would remove" not in output.out
    assert "Would create" not in output.out
    assert "already exists but is a file, not a symbolic link" in output.err


def test_link_undefined_variable_warns(
    capfd: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify link warns about undefined environment variables.

    The link name and the target are used as written, and links that fail
    their test don't cause a warning.
    """

    monkeypatch.delenv("PEAR", raising=False)
    dotfiles.write("h", "grape")
    dotfiles.write("$PEAR", "apple")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/$PEAR": "h",
                    "~/f": "$PEAR",
                    "~/${PEAR}2": {"path": "h", "if": "exit 1"},
                }
            }
        ]
    )
    run_dotbot()

    with open(os.path.join(home, "$PEAR")) as file:
        assert file.read() == "grape"
    with open(os.path.join(home, "f")) as file:
        assert file.read() == "apple"
    warning = (
        "warning: Undefined environment variable $PEAR in {}, using the name as written"
    )
    assert capfd.readouterr().err.splitlines() == [
        warning.format(f"{os.path.join('~', '$PEAR')} -> h"),
        warning.format(f"{os.path.join('~', 'f')} -> $PEAR"),
    ]


def test_link_glob_no_match_warns(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a glob with no match warns, unless ignore-missing is set."""

    _ = home
    dotfiles.makedirs("foo")
    dotfiles.write_config(
        [
            {"defaults": {"link": {"glob": True, "create": True}}},
            {
                "link": {
                    "~/.config/foo": "foo/*",
                    "~/.config/bar": {"path": "foo/*", "ignore-missing": True},
                }
            },
        ]
    )
    run_dotbot()

    stderr = capfd.readouterr().err
    assert f"No files match {os.path.join('~', '.config', 'foo')}" in stderr
    assert "bar" not in stderr


def test_link_copy(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that type: copy copies a file and its mode, instead of linking it."""

    dotfiles.write("f", "apple")
    os.chmod(os.path.join(dotfiles.directory, "f"), 0o755)
    dotfiles.write_config([{"link": {"~/.f": {"path": "f", "type": "copy"}}}])
    run_dotbot()

    copy = os.path.join(home, ".f")
    assert not os.path.islink(copy)
    with open(copy) as file:
        assert file.read() == "apple"
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(copy).st_mode) == 0o755
    # a copy, not a hardlink: changing it doesn't change the target
    with open(copy, "w") as file:
        file.write("cherry")
    with open(os.path.join(dotfiles.directory, "f")) as file:
        assert file.read() == "apple"


@pytest.mark.parametrize(
    ("options", "existing", "expected", "backup"),
    [
        pytest.param({}, "apple", "apple", None, id="same"),
        pytest.param({}, "pear", "pear", None, id="local changes are kept"),
        pytest.param({"force": True}, "pear", "apple", None, id="force"),
        pytest.param({"backup": True}, "pear", "apple", "pear", id="backup"),
        pytest.param({"backup": True}, "apple", "apple", None, id="no backup if same"),
    ],
)
def test_link_copy_existing(
    options: dict[str, Any],
    existing: str,
    expected: str,
    backup: str | None,
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify how type: copy handles a file that already exists."""

    dotfiles.write("f", "apple")
    with open(os.path.join(home, ".f"), "w") as file:
        file.write(existing)
    dotfiles.write_config(
        [{"link": {"~/.f": {"path": "f", "type": "copy", **options}}}]
    )
    run_dotbot()

    with open(os.path.join(home, ".f")) as file:
        assert file.read() == expected
    backups = [name for name in os.listdir(home) if ".dotbot-backup." in name]
    if backup is None:
        assert backups == []
    else:
        assert len(backups) == 1
        with open(os.path.join(home, backups[0])) as file:
            assert file.read() == backup


@pytest.mark.parametrize("relink", [False, True])
def test_link_copy_replaces_symlink_only_with_relink(
    relink: bool,  # noqa: FBT001
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that type: copy replaces a symlink only if relink is set."""

    dotfiles.write("f", "apple")
    os.symlink(os.path.join(dotfiles.directory, "f"), os.path.join(home, ".f"))
    dotfiles.write_config(
        [{"link": {"~/.f": {"path": "f", "type": "copy", "relink": relink}}}]
    )
    if relink:
        run_dotbot()
    else:
        with pytest.raises(SystemExit):
            run_dotbot()

    assert os.path.islink(os.path.join(home, ".f")) is not relink
    with open(os.path.join(home, ".f")) as file:
        assert file.read() == "apple"
    # the symlink pointed at the target, which must still exist
    with open(os.path.join(dotfiles.directory, "f")) as file:
        assert file.read() == "apple"


def test_link_copy_directory(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that type: copy copies a directory file by file.

    With force, a changed file is updated, and a file that is only in the copy
    is kept.
    """

    dotfiles.write("d/a", "apple")
    dotfiles.write("d/sub/b", "banana")
    dotfiles.write_config(
        [{"link": {"~/d": {"path": "d", "type": "copy", "force": True}}}]
    )
    run_dotbot()

    assert not os.path.islink(os.path.join(home, "d"))
    with open(os.path.join(home, "d", "sub", "b")) as file:
        assert file.read() == "banana"

    with open(os.path.join(home, "d", "a"), "w") as file:
        file.write("pear")
    with open(os.path.join(home, "d", "extra"), "w") as file:
        file.write("cherry")
    run_dotbot()

    with open(os.path.join(home, "d", "a")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, "d", "extra")) as file:
        assert file.read() == "cherry"


@pytest.mark.parametrize("option", ["force", "backup"])
def test_link_copy_replaces_directory_with_force_or_backup(
    option: str, home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that type: copy with force or backup replaces a directory with a file."""

    dotfiles.write("f", "apple")
    os.makedirs(os.path.join(home, ".f"))
    dotfiles.write_config(
        [{"link": {"~/.f": {"path": "f", "type": "copy", option: True}}}]
    )
    run_dotbot()

    with open(os.path.join(home, ".f")) as file:
        assert file.read() == "apple"
    backups = [name for name in os.listdir(home) if ".dotbot-backup." in name]
    assert len(backups) == (1 if option == "backup" else 0)


@pytest.mark.parametrize("target_is_directory", [False, True])
def test_link_copy_fails_for_other_type(
    target_is_directory: bool,  # noqa: FBT001
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that type: copy fails if a file is where a directory copy should be.

    The same is true for a directory where a file copy should be.
    """

    if target_is_directory:
        dotfiles.write("x/a", "apple")
        with open(os.path.join(home, "x"), "w") as file:
            file.write("pear")
        expected = "already exists but is a file, not a directory"
    else:
        dotfiles.write("x", "apple")
        os.makedirs(os.path.join(home, "x"))
        expected = "already exists but is a directory, not a file"
    dotfiles.write_config([{"link": {"~/x": {"path": "x", "type": "copy"}}}])
    with pytest.raises(SystemExit):
        run_dotbot()

    assert os.path.isdir(os.path.join(home, "x")) is not target_is_directory
    assert f"{os.path.join('~', 'x')} {expected}" in capfd.readouterr().err


def test_link_copy_replaces_symlinks_in_copy(
    root: str, home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that updating a copy replaces the symlinks in it.

    Following a symlink would change a file outside of the copy.
    """

    dotfiles.write("d/a", "apple")
    dotfiles.write("d/sub/b", "banana")
    with open(os.path.join(root, "outside"), "w") as file:
        file.write("secret")
    os.makedirs(os.path.join(root, "outside-directory"))
    os.makedirs(os.path.join(home, "d"))
    os.symlink(os.path.join(root, "outside"), os.path.join(home, "d", "a"))
    os.symlink(
        os.path.join(root, "outside-directory"),
        os.path.join(home, "d", "sub"),
        target_is_directory=True,
    )
    dotfiles.write_config(
        [{"link": {"~/d": {"path": "d", "type": "copy", "force": True}}}]
    )
    run_dotbot()

    assert not os.path.islink(os.path.join(home, "d", "a"))
    assert not os.path.islink(os.path.join(home, "d", "sub"))
    with open(os.path.join(home, "d", "a")) as file:
        assert file.read() == "apple"
    with open(os.path.join(home, "d", "sub", "b")) as file:
        assert file.read() == "banana"
    with open(os.path.join(root, "outside")) as file:
        assert file.read() == "secret"
    assert os.listdir(os.path.join(root, "outside-directory")) == []


@pytest.mark.parametrize("in_directory", [False, True])
def test_link_copy_updates_read_only_copy(
    in_directory: bool,  # noqa: FBT001
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that force updates the copy of a read-only file.

    The copy gets the read-only mode of the target, so it can't be overwritten.
    """

    name = "d" if in_directory else "f"
    path = os.path.join("d", "f") if in_directory else "f"
    target = os.path.join(dotfiles.directory, path)
    dotfiles.write(path, "apple")
    os.chmod(target, 0o444)
    dotfiles.write_config(
        [{"link": {f"~/{name}": {"path": name, "type": "copy", "force": True}}}]
    )
    run_dotbot()
    os.chmod(target, 0o644)
    dotfiles.write(path, "banana")
    os.chmod(target, 0o444)
    run_dotbot()

    with open(os.path.join(home, path)) as file:
        assert file.read() == "banana"


def test_link_copy_fails_if_comparison_fails(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that a copy that can't be compared fails, and later links are set up."""

    dotfiles.write("a", "apple")
    dotfiles.write("b", "banana")
    with open(os.path.join(home, "a"), "w") as file:
        file.write("pear")
    dotfiles.write_config(
        [{"link": {"~/a": {"path": "a", "type": "copy"}, "~/b": "b"}}]
    )
    with (
        patch("filecmp.cmp", side_effect=PermissionError(13, "Permission denied")),
        pytest.raises(SystemExit),
    ):
        run_dotbot()

    with open(os.path.join(home, "a")) as file:
        assert file.read() == "pear"
    assert os.path.islink(os.path.join(home, "b"))
    assert f"Failed to compare {os.path.join('~', 'a')}" in capfd.readouterr().err


def test_link_copy_failure_keeps_copy(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that a failed update of a copy keeps the copy as it was.

    For example, the disk can be full. No temporary file must stay.
    """

    dotfiles.write("f", "apple")
    with open(os.path.join(home, "f"), "w") as file:
        file.write("pear")
    dotfiles.write_config(
        [{"link": {"~/f": {"path": "f", "type": "copy", "force": True}}}]
    )

    def copy_part(_source: str, destination: str) -> None:
        with open(destination, "w") as file:
            file.write("app")
        raise OSError(28, "No space left on device")

    with patch("shutil.copy2", side_effect=copy_part), pytest.raises(SystemExit):
        run_dotbot()

    with open(os.path.join(home, "f")) as file:
        assert file.read() == "pear"
    assert os.listdir(home) == ["f"]


def test_link_copy_glob(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that type: copy works with glob."""

    dotfiles.write("conf/a", "apple")
    dotfiles.write("conf/b", "banana")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/.conf": {
                        "path": "conf/*",
                        "glob": True,
                        "create": True,
                        "type": "copy",
                    }
                }
            }
        ]
    )
    run_dotbot()

    for name, content in [("a", "apple"), ("b", "banana")]:
        assert not os.path.islink(os.path.join(home, ".conf", name))
        with open(os.path.join(home, ".conf", name)) as file:
            assert file.read() == content
        # a copy, not a hardlink: changing it doesn't change the target
        with open(os.path.join(home, ".conf", name), "w") as file:
            file.write("cherry")
        with open(os.path.join(dotfiles.directory, "conf", name)) as file:
            assert file.read() == content


def test_link_copy_ignore_missing(
    home: str, dotfiles: Dotfiles, run_dotbot: Callable[..., None]
) -> None:
    """Verify that type: copy with ignore-missing skips a missing target."""

    dotfiles.write_config(
        [{"link": {"~/.f": {"path": "f", "type": "copy", "ignore-missing": True}}}]
    )
    run_dotbot()

    assert not os.path.lexists(os.path.join(home, ".f"))


def test_link_copy_dry_run(
    capfd: pytest.CaptureFixture[str],
    home: str,
    dotfiles: Dotfiles,
    run_dotbot: Callable[..., None],
) -> None:
    """Verify that type: copy doesn't copy anything during a dry run."""

    dotfiles.write("f", "apple")
    dotfiles.write("g", "banana")
    with open(os.path.join(home, ".g"), "w") as file:
        file.write("pear")
    dotfiles.write_config(
        [
            {
                "link": {
                    "~/.f": {"path": "f", "type": "copy"},
                    "~/.g": {"path": "g", "type": "copy", "force": True},
                }
            }
        ]
    )
    run_dotbot("-n")

    assert not os.path.lexists(os.path.join(home, ".f"))
    with open(os.path.join(home, ".g")) as file:
        assert file.read() == "pear"
    lines = [line.strip() for line in capfd.readouterr().out.splitlines()]
    assert (
        f"Would create copy {os.path.join('~', '.f')} -> {os.path.join(dotfiles.directory, 'f')}"
        in lines
    )
    assert (
        f"Would update copy {os.path.join('~', '.g')} -> {os.path.join(dotfiles.directory, 'g')}"
        in lines
    )
