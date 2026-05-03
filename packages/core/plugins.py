from collections.abc import Callable

PluginHandler = Callable[..., object]

_REGISTRY: dict[str, dict[str, object]] = {}


def register_plugin(name: str, description: str, handler: PluginHandler) -> None:
    _REGISTRY[name] = {
        "name": name,
        "description": description,
        "handler": handler,
    }


def list_plugins() -> list[dict[str, str]]:
    return [
        {"name": item["name"], "description": item["description"]}
        for item in _REGISTRY.values()
    ]


def call_plugin(name: str, *args, **kwargs) -> object:
    plugin = _REGISTRY.get(name)
    if plugin is None:
        raise ValueError(f"Unknown plugin: {name}")
    handler = plugin["handler"]
    return handler(*args, **kwargs)
