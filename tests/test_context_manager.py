import pytest

from packages.core.context_manager import (
    build_chat_context,
    list_pinned_files,
    pin_file,
    unpin_file,
)


def test_pin_unpin_cycle() -> None:
    path = "README.md"
    pin_file(path)
    assert path in list_pinned_files()
    unpin_file(path)
    assert path not in list_pinned_files()


def test_pin_secret_file_blocked() -> None:
    with pytest.raises(ValueError):
        pin_file(".env")


def test_build_context_max_chars_enforced() -> None:
    pin_file("README.md")
    context = build_chat_context("README.md", list_pinned_files(), max_chars=120)
    assert len(context) <= 120
    unpin_file("README.md")
