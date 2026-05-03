import pytest
from fastapi.testclient import TestClient

from packages.core.rollback import (
    create_rollback_record,
    get_rollback,
    list_rollbacks,
    rollback_change,
)
from packages.server.app import app


def test_rollback_restore_file() -> None:
    record = create_rollback_record("tests/.rb_test.txt", "before", "after", "diff")
    target = "tests/.rb_test.txt"
    with open(target, "w", encoding="utf-8") as f:
        f.write("after")

    rollback_change(record["rollback_id"])
    with open(target, "r", encoding="utf-8") as f:
        assert f.read() == "before"


def test_secret_file_blocked() -> None:
    with pytest.raises(ValueError):
        create_rollback_record(".env", "a", "b", "d")


def test_list_and_get_rollbacks() -> None:
    record = create_rollback_record("tests/.rb_test2.txt", "x", "y", "d")
    assert get_rollback(record["rollback_id"]) is not None
    assert any(item["rollback_id"] == record["rollback_id"] for item in list_rollbacks())


def test_rollback_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "token123")
    client = TestClient(app)
    record = create_rollback_record("tests/.rb_api.txt", "v1", "v2", "d")
    headers = {"x-api-key": "token123"}

    r1 = client.get("/rollback", headers=headers)
    assert r1.status_code == 200

    r2 = client.get(f"/rollback/{record['rollback_id']}", headers=headers)
    assert r2.status_code == 200

    with open("tests/.rb_api.txt", "w", encoding="utf-8") as f:
        f.write("v2")

    r3 = client.post(f"/rollback/{record['rollback_id']}/apply", headers=headers)
    assert r3.status_code == 200
