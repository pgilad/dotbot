import os
import subprocess
import sys
import traceback
from argparse import ArgumentParser, RawTextHelpFormatter
from typing import Any

import dotbot
from dotbot.config import ConfigReader, ReadingError
from dotbot.dispatcher import Dispatcher, DispatchError
from dotbot.messenger import Level, Messenger
from dotbot.plugins import Clean, Create, Link, Shell
from dotbot.util import module, string


def add_options(parser: ArgumentParser) -> None:
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="suppress most output"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="enable verbose output\n"
        "-v: show informational messages\n"
        "-vv: also, set shell commands stderr/stdout to true",
    )
    parser.add_argument(
        "-d",
        "--base-directory",
        help="execute commands from within BASE_DIR",
        metavar="BASE_DIR",
    )
    parser.add_argument(
        "-c",
        "--config-file",
        help="run commands given in CONFIG_FILE",
        metavar="CONFIG_FILE",
        nargs="+",
    )
    parser.add_argument(
        "-p",
        "--plugin",
        action="append",
        dest="plugins",
        default=[],
        help="load PLUGIN as a plugin",
        metavar="PLUGIN",
    )
    parser.add_argument(
        "--disable-built-in-plugins",
        action="store_true",
        help="disable built-in plugins",
    )
    parser.add_argument(
        "--only", nargs="+", help="only run specified directives", metavar="DIRECTIVE"
    )
    parser.add_argument(
        "--except",
        nargs="+",
        dest="skip",
        help="skip specified directives",
        metavar="DIRECTIVE",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="print what would be done, without doing it",
    )
    parser.add_argument(
        "--force-color",
        dest="force_color",
        action="store_true",
        help="force color output",
    )
    parser.add_argument(
        "--no-color", dest="no_color", action="store_true", help="disable color output"
    )
    parser.add_argument(
        "--version", action="store_true", help="show program's version number and exit"
    )
    parser.add_argument(
        "-x",
        "--exit-on-failure",
        dest="exit_on_failure",
        action="store_true",
        help="exit after first failed directive",
    )


def read_config(config_files: list[str]) -> Any:
    reader = ConfigReader(config_files)
    return reader.get_config()


def totals(log: Messenger) -> str:
    """
    Returns the numbers of errors, warnings, changes, and commands of the run.

    The changes are always there, also when there are none, because they tell
    if the run did something. Commands aren't changes, because Dotbot doesn't
    know what a command changes.
    """
    errors = log.count(Level.ERROR)
    warnings = log.count(Level.WARNING)
    changes = log.count(Level.ACTION)
    commands = log.count(Level.COMMAND)
    parts = []
    if errors:
        parts.append(string.plural(errors, "error"))
    if warnings:
        parts.append(string.plural(warnings, "warning"))
    parts.append(string.plural(changes, "change") if changes else "no changes")
    if commands:
        parts.append(string.plural(commands, "command"))
    return ", ".join(parts)


def git_commit() -> str | None:
    """
    Returns the commit of the checkout of Dotbot that runs, or None.

    An installed Dotbot isn't in a checkout, but it can be in the git
    repository of something else, such as a home directory under version
    control.
    """
    # the directory that has src/dotbot/cli.py in a checkout
    project_directory = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel", "HEAD"],  # noqa: S607
            cwd=project_directory,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        toplevel, commit = output.splitlines()
        in_checkout = os.path.samefile(toplevel, project_directory)
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None
    return commit if in_checkout else None


def main() -> None:
    log = Messenger()
    try:
        parser = ArgumentParser(formatter_class=RawTextHelpFormatter)
        add_options(parser)
        options = parser.parse_args()
        if options.version:
            commit = git_commit()
            hash_msg = f" (git {commit[:10]})" if commit else ""
            print(f"Dotbot version {dotbot.__version__}{hash_msg}")  # noqa: T201
            sys.exit(0)
        # set the level and reset the counts each time, because Messenger is a
        # singleton, and main() can run more than once in a process
        level = Level.ACTION
        if options.quiet:
            level = Level.WARNING
        if options.verbose > 0:
            level = Level.INFO if options.verbose == 1 else Level.DEBUG
        log.set_level(level)
        log.reset_counts()

        if options.force_color and options.no_color:
            log.error("`--force-color` and `--no-color` cannot both be provided")
            sys.exit(1)
        elif options.force_color:
            log.use_color(True)
        elif options.no_color:
            log.use_color(False)
        else:
            log.use_color(sys.stdout.isatty() and sys.stderr.isatty())

        plugins = []
        if not options.disable_built_in_plugins:
            plugins.extend([Clean, Create, Link, Shell])
        try:
            module.load_plugins(options.plugins, plugins)
        except Exception as e:  # noqa: BLE001
            log.error(f"Could not load plugins:\n{string.indent_lines(str(e))}")
            log.debug(traceback.format_exc())
            sys.exit(1)

        if not options.config_file:
            log.error("No configuration file specified")
            sys.exit(1)
        tasks = read_config(options.config_file)
        if not tasks:
            log.warning("No tasks given in configuration, no work to do")
        if options.base_directory:
            base_directory = os.path.abspath(options.base_directory)
        else:
            # default to directory of first config file
            base_directory = os.path.dirname(os.path.abspath(options.config_file[0]))
        try:
            os.chdir(base_directory)
        except OSError as e:
            msg = string.indent_lines(str(e))
            log.error(f"Could not use base directory:\n{msg}")
            sys.exit(1)
        # for backwards compatibility, see dispatcher.py
        dotbot.dispatcher._all_plugins = plugins  # noqa: SLF001
        dispatcher = Dispatcher(
            base_directory,
            only=options.only,
            skip=options.skip,
            exit_on_failure=options.exit_on_failure,
            options=options,
            plugins=plugins,
        )
        success = dispatcher.dispatch(tasks)
        if success:
            done = "Dry run done" if options.dry_run else "Done"
            log.summary(f"{done} ({totals(log)})")
        else:
            failed = (
                "Stopped after the first failed directive"
                if options.exit_on_failure
                else "Failed"
            )
            msg = f"{failed} ({totals(log)})"
            raise DispatchError(msg)  # noqa: TRY301
    except (ReadingError, DispatchError) as e:
        log.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        log.error("Operation aborted")
        sys.exit(1)
