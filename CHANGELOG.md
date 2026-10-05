Note: this changelog only lists feature additions, not bugfixes. For details on those, see the Git history.

- v2.0
    - Require Python 3.14+: `bin/dotbot` and `bin/dotbot.ps1` use uv to find or download Python 3.14+ if it isn't installed
    - Run `shell` commands and `if:` tests with `/bin/sh` (`cmd.exe` on Windows) instead of `$SHELL`
    - Add `executable:` option for `shell`
    - Add `copy` type for `link`
    - Print warnings and errors to stderr
    - Warn about unknown options, undefined environment variables, and globs that match nothing
