"""Small text helpers shared by services."""


def escape_like(text: str) -> str:
    """Escape LIKE wildcards so user input is matched literally (values are bound parameters)."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
