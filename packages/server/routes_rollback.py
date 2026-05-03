from fastapi import APIRouter, HTTPException

from packages.core.rollback import get_rollback, list_rollbacks, rollback_change

router = APIRouter(prefix="/rollback", tags=["rollback"])


@router.get("")
def rollback_list() -> dict:
    return {"rollbacks": list_rollbacks()}


@router.get("/{rollback_id}")
def rollback_get(rollback_id: str) -> dict:
    record = get_rollback(rollback_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Rollback not found")
    return record


@router.post("/{rollback_id}/apply")
def rollback_apply(rollback_id: str) -> dict:
    try:
        return rollback_change(rollback_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
