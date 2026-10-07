# Plugins

Plugins add directives to Dotbot. For example:

- Packages: [dotbot-brew], [dotbot-apt], [dotbot-yum]
- Secrets: [dotbot-age], [dotbot-gitcrypt]
- System and application settings: [crontab-dotbot], [dotbot-firefox]

## Load plugins

Load plugin files, or directories of plugin files, with the `plugins` directive. Paths are relative to the base directory.

```yaml
- plugins:
    - dotbot-plugins/dotbot-brew/
    - dotbot-plugins/custom_plugin.py
```

Or use `--plugin` (`-p`) one time for each plugin. These paths are relative to the current directory.

```sh
dotbot -c install.conf.yaml --plugin dotbot-plugins/dotbot-brew/ --plugin dotbot-plugins/custom_plugin.py
```

If you use an `install` script, put the `--plugin` options in it, so that each installation loads the same plugins. To use only your plugins, add `--disable-built-in-plugins`.

## Write a plugin

A plugin is a subclass of `dotbot.Plugin` with two methods:

- `can_handle(directive)` returns `True` if the plugin handles the directive.
- `handle(directive, data)` does the work and returns `True` if it succeeds. If it fails, log what failed with `self._log.error()`; if you don't, Dotbot logs `Action <directive> failed`.

Log each change with `self._log.action()`, and each command that the plugin runs with `self._log.command()`. The last line of a run counts the changes and the commands.

To support `--dry-run`, set `supports_dry_run = True`, and when `self._context.dry_run()` is true, log what the plugin would do without doing it. Dotbot skips plugins without dry-run support in a dry run.

```python
import dotbot


class Hello(dotbot.Plugin):
    supports_dry_run = True

    def can_handle(self, directive):
        return directive == "hello"

    def handle(self, directive, data):
        if self._context.dry_run():
            self._log.action(f"Would say hello to {data}")
        else:
            self._log.action(f"Hello, {data}!")
        return True
```

```yaml
- plugins:
    - plugins/hello.py

- hello: world
```

The built-in directives are plugins too. See [`src/dotbot/plugins`](../src/dotbot/plugins) for more examples.

[dotbot-brew]: https://github.com/d12frosted/dotbot-brew
[dotbot-apt]: https://github.com/bryant1410/dotbot-apt
[dotbot-yum]: https://gitlab.com/flyingchipmunk/dotbot-yum
[dotbot-age]: https://github.com/fcatuhe/dotbot-age
[dotbot-gitcrypt]: https://gitlab.com/gnfzdz/dotbot-gitcrypt
[crontab-dotbot]: https://github.com/fundor333/crontab-dotbot
[dotbot-firefox]: https://github.com/kurtmckee/dotbot-firefox
