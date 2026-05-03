from fastapi import APIRouter

from packages.core.plugins import list_plugins

router = APIRouter(prefix="/plugins", tags=["plugins"])


@router.get("")
def get_plugins() -> dict[str, list[dict[str, str]]]:
    return {"plugins": list_plugins()}
