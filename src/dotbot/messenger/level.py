from enum import Enum


class Level(Enum):
    NOTSET = 0
    DEBUG = 10
    INFO = 15
    LOWINFO = 15  # Deprecated: use INFO instead  # noqa: PIE796
    ACTION = 20  # a change, such as a new link
    COMMAND = 21  # a command that runs, which can change anything
    SUMMARY = 25  # a line that counts the results of a directive or a run
    WARNING = 30
    ERROR = 40

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Level):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Level):
            return NotImplemented
        return self.value <= other.value

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Level):
            return NotImplemented
        return self.value > other.value

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Level):
            return NotImplemented
        return self.value >= other.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Level):
            return NotImplemented
        return self.value == other.value

    def __hash__(self) -> int:
        return hash(self.value)
