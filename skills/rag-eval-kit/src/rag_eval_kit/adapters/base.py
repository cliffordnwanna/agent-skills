"""Shared adapter errors and JSON response validation."""

from typing import Any


class AdapterError(RuntimeError):
    """A target-app failure. ``kind`` is "timeout", "connection" or "error"."""

    def __init__(self, message: str, *, kind: str = "error") -> None:
        super().__init__(message)
        self.kind = kind


def optional_number(value: Any) -> int | float | None:
    """A non-negative number reported by the app, or None. Never raises."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value if value >= 0 and value == value else None


def extract_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdecimal() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise AdapterError(f"Configured response field is missing: {path}")
    return current


def extract_optional_path(value: Any, path: str | None) -> Any:
    return None if path is None else extract_path(value, path)


def string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise AdapterError(f"Response field must be an array of strings: {field}")
    return value


def response_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise AdapterError(f"Response field must be a string: {field}")
    return value
