from packages.core.permissions import (
    AUTONOMOUS,
    FILES,
    READ_ONLY,
    TESTS,
    can_read_files,
    can_run_autonomous,
    can_run_tests,
    can_write_files,
)


def test_permissions_matrix() -> None:
    assert can_read_files(READ_ONLY)
    assert not can_write_files(READ_ONLY)
    assert not can_run_tests(READ_ONLY)
    assert not can_run_autonomous(READ_ONLY)

    assert can_write_files(FILES)
    assert not can_run_tests(FILES)

    assert can_run_tests(TESTS)
    assert not can_write_files(TESTS)

    assert can_write_files(AUTONOMOUS)
    assert can_run_tests(AUTONOMOUS)
    assert can_run_autonomous(AUTONOMOUS)
