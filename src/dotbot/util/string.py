def indent_lines(string: str, amount: int = 2, delimiter: str = "\n") -> str:
    whitespace = " " * amount
    sep = f"{delimiter}{whitespace}"
    return f"{whitespace}{sep.join(string.split(delimiter))}"


def plural(count: int, singular: str, plural: str | None = None) -> str:
    """
    Returns the count with a noun, such as "1 error" or "2 errors".
    """
    if count == 1:
        return f"{count} {singular}"
    return f"{count} {plural or singular + 's'}"
