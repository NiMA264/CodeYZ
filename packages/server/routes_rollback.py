from fastapi import APIRouter

from packages.core.rollback import get_rollback, list_rollbacks, rollback_change
from packages.server.errors import raise_api_error

router = APIRouter(prefix="/rollback", tags=["rollback"])


@router.get("")
def rollback_list() -> dict:
    return {"rollbacks": list_rollbacks()}


@router.get("/{rollback_id}")
def rollback_get(rollback_id: str) -> dict:
    record = get_rollback(rollback_id)
    if record is None:
        raise_api_error(404, "rollback_not_found", "Rollback not found", "Check rollback id via GET /rollback.")
    return record


@router.post("/{rollback_id}/apply")
def rollback_apply(rollback_id: str) -> dict:
    try:
        return rollback_change(rollback_id)
    except ValueError as exc:
        raise_api_error(404, "rollback_not_found", str(exc), "Check rollback id via GET /rollback.")
