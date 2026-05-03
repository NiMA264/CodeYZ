from packages.tools.shell import run_shell


def git_status() -> str:
    return run_shell("git status --short")


def git_diff() -> str:
    return run_shell("git diff -- .")


def git_commit(message: str) -> str:
    return run_shell(f'git commit -m "{message}"')
