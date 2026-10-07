import glob
import hashlib
import importlib.util
import os
import sys
from types import ModuleType

from dotbot.plugin import Plugin


def load(path: str) -> list[type[Plugin]]:
    basename = os.path.basename(path)
    module_name, _ = os.path.splitext(basename)
    loaded_module = load_module(module_name, path)
    plugins = []
    for name in dir(loaded_module):
        possible_plugin = getattr(loaded_module, name)
        try:
            if issubclass(possible_plugin, Plugin) and possible_plugin is not Plugin:
                plugins.append(possible_plugin)
        except TypeError:
            pass
    return plugins


def load_module(module_name: str, path: str) -> ModuleType:
    # Register the module in sys.modules, because some code (such as
    # dataclasses) looks up the module of a class there. The prefix keeps a
    # plugin file such as "copy.py" from replacing a standard library module,
    # and the hash of the path keeps plugin files with the same name apart
    # (load_plugins() also uses the module name to find duplicate plugins).
    digest = hashlib.sha256(os.fsencode(path)).hexdigest()[:16]
    module_name = f"_dotbot_plugin_{module_name}_{digest}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if not spec or not spec.loader:
        msg = f"Unable to load module {module_name} from {path}"
        raise ImportError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[module_name]
        raise
    return module


def load_plugins(
    paths: list[str], plugins: list[type[Plugin]] | None = None
) -> list[type[Plugin]]:
    """
    Load plugins from the given paths and add them to the given list of plugins.

    Args:
        paths: List of file paths to load plugins from. Each path can be either a file or a directory.
        plugins: List of existing plugins to add to.

    Returns the newly-loaded plugins.
    """
    if plugins is None:
        plugins = []
    new_plugins = []
    plugin_paths = []
    for path in paths:
        if os.path.isdir(path):
            plugin_paths.extend(glob.glob(os.path.join(path, "*.py")))
        else:
            plugin_paths.append(path)
    for plugin_path in plugin_paths:
        abspath = os.path.abspath(plugin_path)
        for plugin in load(abspath):
            # ensure plugins are unique to avoid duplicate execution, which
            # can happen if, for example, a third-party plugin loads a
            # built-in plugin, which will cause it to appear in the list
            # returned by load() above
            plugin_already_loaded = any(
                existing_plugin.__module__ == plugin.__module__
                and existing_plugin.__name__ == plugin.__name__
                for existing_plugin in plugins
            )
            if not plugin_already_loaded:
                plugins.append(plugin)
                new_plugins.append(plugin)
    return new_plugins
