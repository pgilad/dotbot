import os
import shutil
import subprocess
import sys

import pytest

from tests.conftest import Dotfiles


@pytest.mark.skipif(
    "sys.platform == 'win32'",
    reason="The hybrid sh/Python dotbot script doesn't run on Windows platforms",
)
@pytest.mark.parametrize(
    ("pythons", "uv", "expected"),
    [
        ({}, None, None),
        ({"python": True}, None, "python"),
        ({"python3": True}, None, "python3"),
        ({"python3": False}, None, None),
        ({"python3": False, "python": True}, None, "python"),
        ({"python3": False}, "installed", "uv-python"),
        ({}, "installable", "uv-python"),
        ({}, "unavailable", None),
    ],
)
def test_find_python_executable(
    pythons: dict[str, bool],
    uv: str | None,
    expected: str | None,
    home: str,
    dotfiles: Dotfiles,
) -> None:
    """Verify that the sh/Python hybrid dotbot executable can find Python.

    Each fake Python on the PATH either passes or fails the version check. The
    fake uv either finds a Python 3.14+ ("installed"), finds one after
    installing it ("installable"), or never finds one ("unavailable").
    """

    dotfiles.write_config([])
    dotbot_executable = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "dotbot"
    )

    # Create a link to sh.
    tmp_bin = os.path.join(home, "tmp_bin")
    os.makedirs(tmp_bin)
    sh_path = shutil.which("sh")
    assert sh_path is not None
    os.symlink(sh_path, os.path.join(tmp_bin, "sh"))

    def write_executable(path: str, body: str) -> None:
        with open(path, "w") as file:
            file.write("#!" + tmp_bin + "/sh\n")
            file.write(body)
        os.chmod(path, 0o777)

    def write_python(path: str, *, new_enough: bool) -> None:
        version_check = 0 if new_enough else 1
        write_executable(
            path,
            f'if [ "$1" = "-c" ]; then exit {version_check}; fi\n: > "{path}.ran"\n',
        )

    for name, new_enough in pythons.items():
        write_python(os.path.join(tmp_bin, name), new_enough=new_enough)

    uv_python = os.path.join(home, "uv-python")
    write_python(uv_python, new_enough=True)
    if uv is not None:
        installed = os.path.join(home, "uv-installed")
        write_executable(
            os.path.join(tmp_bin, "uv"),
            f'if [ "$1 $2" = "python install" ] && [ "{uv}" = installable ]; then\n'
            f'  : > "{installed}"; exit 0\n'
            "fi\n"
            f'if [ "$1 $2" = "python find" ] && {{ [ "{uv}" = installed ] || [ -e "{installed}" ]; }}; then\n'
            f'  echo "{uv_python}"; exit 0\n'
            "fi\n"
            "exit 1\n",
        )

    env = dict(os.environ)
    env["PATH"] = tmp_bin
    env["XDG_CACHE_HOME"] = os.path.join(home, ".cache")

    if expected is not None:
        subprocess.check_call(
            [dotbot_executable, "-c", dotfiles.config_filename],
            env=env,
        )
    else:
        with pytest.raises(subprocess.CalledProcessError):
            subprocess.check_call(
                [dotbot_executable, "-c", dotfiles.config_filename],
                env=env,
            )

    candidates = {name: os.path.join(tmp_bin, name) for name in pythons}
    candidates["uv-python"] = uv_python
    ran = {name for name, path in candidates.items() if os.path.exists(path + ".ran")}
    assert ran == ({expected} if expected is not None else set())


@pytest.mark.skipif(
    "sys.platform == 'win32'",
    reason="The hybrid sh/Python dotbot script doesn't run on Windows platforms",
)
def test_pythonpath_is_kept(home: str, dotfiles: Dotfiles) -> None:
    """Verify that the dotbot executable keeps the PYTHONPATH of the user.

    It adds its own source directory in front, so that shell commands can
    import dotbot.
    """

    output = os.path.join(home, "pythonpath")
    dotfiles.write_config([{"shell": [f'echo "$PYTHONPATH" > "{output}"']}])
    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Use the interpreter outside of the test environment, which doesn't have
    # dotbot installed, so that the dotbot executable adds its source directory.
    tmp_bin = os.path.join(home, "tmp_bin")
    os.makedirs(tmp_bin)
    with open(os.path.join(tmp_bin, "python3"), "w") as file:
        file.write(f'#!/bin/sh\nexec "{os.path.realpath(sys.executable)}" "$@"\n')
    os.chmod(os.path.join(tmp_bin, "python3"), 0o777)
    env = dict(os.environ)
    env["PATH"] = tmp_bin + os.pathsep + env["PATH"]
    env["PYTHONPATH"] = "/apple"

    subprocess.check_call(
        [os.path.join(project, "bin", "dotbot"), "-c", dotfiles.config_filename],
        env=env,
    )
    with open(output) as file:
        assert (
            file.read().strip() == os.path.join(project, "src") + os.pathsep + "/apple"
        )
