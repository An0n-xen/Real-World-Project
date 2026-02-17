"""Dynamic tool registry for managing diagnostic tool functions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from medagent.logger import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """Register, look up, and invoke diagnostic tool functions.

    Tools follow the standard MedAgent-Pro signature::

        tool_function(image_path_or_inputs, save_dir, save_name)
    """

    def __init__(self) -> None:
        self._registry: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        """Register a tool function under *name*."""
        self._registry[name] = fn
        logger.info("Registered tool: %s", name)

    def get(self, name: str) -> Callable[..., Any] | None:
        """Look up a tool by *name*. Returns ``None`` if not found."""
        fn = self._registry.get(name)
        if fn is None:
            logger.warning("Tool not found: %s", name)
        return fn

    def invoke(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Invoke a registered tool. Raises ``KeyError`` if missing."""
        fn = self._registry.get(name)
        if fn is None:
            raise KeyError(f"Tool '{name}' is not registered")
        logger.info("Invoking tool: %s", name)
        return fn(*args, **kwargs)

    def list_tools(self) -> list[str]:
        """Return names of all registered tools."""
        return list(self._registry.keys())

    def register_from_module(self, module: object, prefix: str = "") -> int:
        """Bulk-register all callable attributes from *module*.

        Returns the count of newly registered tools.
        """
        count = 0
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            obj = getattr(module, attr_name)
            if callable(obj):
                name = f"{prefix}{attr_name}" if prefix else attr_name
                self.register(name, obj)
                count += 1
        logger.info(
            "Registered %d tools from module %s", count, getattr(module, "__name__", "?")
        )
        return count

    def __contains__(self, name: str) -> bool:
        return name in self._registry

    def __len__(self) -> int:
        return len(self._registry)
