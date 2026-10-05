import sys

from dotbot.messenger.color import Color
from dotbot.messenger.level import Level
from dotbot.util.singleton import Singleton


class Messenger(metaclass=Singleton):
    def __init__(self, level: Level = Level.ACTION):
        self.set_level(level)
        self.use_color(True)

    def set_level(self, level: Level) -> None:
        self._level = level

    def use_color(self, yesno: bool) -> None:  # noqa: FBT001
        self._use_color = yesno

    def log(self, level: Level, message: str) -> None:
        if level >= self._level:
            # flush, so that messages stay in order with the output of shell commands
            print(  # noqa: T201
                f"{self._color(level)}{self._prefix(level)}{message}{self._reset()}",
                file=sys.stderr if level >= Level.WARNING else sys.stdout,
                flush=True,
            )

    def debug(self, message: str) -> None:
        self.log(Level.DEBUG, message)

    def action(self, message: str) -> None:
        self.log(Level.ACTION, message)

    def info(self, message: str) -> None:
        self.log(Level.INFO, message)

    def lowinfo(self, message: str) -> None:
        """Deprecated: use info() or action() instead."""
        self.info(message)

    def warning(self, message: str) -> None:
        self.log(Level.WARNING, message)

    def error(self, message: str) -> None:
        self.log(Level.ERROR, message)

    def _color(self, level: Level) -> str:
        """
        Get a color (terminal escape sequence) according to a level.
        """
        if not self._use_color or level < Level.DEBUG:
            return ""
        if level < Level.INFO:
            return Color.YELLOW
        if level < Level.ACTION:
            return Color.BLUE
        if level < Level.WARNING:
            return Color.GREEN
        if level < Level.ERROR:
            return Color.MAGENTA
        return Color.RED

    def _prefix(self, level: Level) -> str:
        """
        Get a prefix that shows the level of a message when color is disabled.
        """
        if self._use_color or level < Level.WARNING:
            return ""
        if level < Level.ERROR:
            return "warning: "
        return "error: "

    def _reset(self) -> str:
        """
        Get a reset color (terminal escape sequence).
        """
        if not self._use_color:
            return ""
        return Color.RESET
