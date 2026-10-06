Note: this changelog only lists feature additions, not bugfixes. For details on those, see the Git history.

- v3.1
    - Show a summary at the end of a run, with the numbers of errors, warnings, and actions
    - Log each failure as one error, and keep the `warning:` and `error:` words in color output
    - Show `~` in place of the home directory in log messages
    - Show the exit code of a failed shell command and the reason of a failed file operation
- v3.0
    - Install Dotbot as an application with `uv tool install git+https://github.com/pgilad/dotbot`; remove `bin/dotbot`, `bin/dotbot.ps1`, and the install scripts for git submodules and Mercurial subrepos
    - Attach the wheel and the source distribution to GitHub releases
- v2.0
    - Require Python 3.14+: `bin/dotbot` and `bin/dotbot.ps1` use uv to find or download Python 3.14+ if it isn't installed
    - Run `shell` commands and `if:` tests with `/bin/sh` (`cmd.exe` on Windows) instead of `$SHELL`
    - Add `executable:` option for `shell`
    - Add `copy` type for `link`
    - Print warnings and errors to stderr
    - Warn about unknown options, undefined environment variables, and globs that match nothing
