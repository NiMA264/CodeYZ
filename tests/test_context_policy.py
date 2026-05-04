from packages.core.context_policy import should_attach_code_context


def test_logo_request_in_chat_false() -> None:
    assert should_attach_code_context("erstelle mir ein Logo", mode="Chat") is False


def test_analyze_project_true() -> None:
    assert should_attach_code_context("analysiere das Projekt", mode="Chat") is True


def test_fix_bug_true() -> None:
    assert should_attach_code_context("fix den bug in app.py", mode="Chat") is True


def test_code_mode_true() -> None:
    assert should_attach_code_context("irgendwas", mode="Code") is True


def test_selected_file_true() -> None:
    assert should_attach_code_context("erstelle mir ein Logo", mode="Chat", selected_file="app.py") is True
