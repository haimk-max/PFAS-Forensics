"""Plugin registry: decorator-based registration + directory discovery."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Dict, Optional, Type

log = logging.getLogger(__name__)

PLUGIN_CATEGORIES = (
    "data_source",
    "forensics",
    "trend_detector",
    "source_attributor",
    "report_section",
    "family_analyzer",
)

_registry: Dict[str, Dict[str, Type]] = {cat: {} for cat in PLUGIN_CATEGORIES}


def register_plugin(category: str, name: Optional[str] = None):
    """Class decorator that registers a plugin under *category*.

    Usage::

        @register_plugin("forensics", name="chlorinated")
        class ChlorinatedForensics:
            ...
    """
    if category not in _registry:
        raise ValueError(
            f"Unknown plugin category '{category}'. "
            f"Valid: {sorted(_registry)}"
        )

    def decorator(cls: Type) -> Type:
        plugin_name = name or cls.__name__
        _registry[category][plugin_name] = cls
        log.debug("Registered plugin %s/%s → %s", category, plugin_name, cls)
        return cls

    return decorator


def discover_plugins(plugins_dir: Optional[Path] = None) -> int:
    """Import all ``plugin.py`` files found under *plugins_dir*.

    Returns the number of plugins successfully imported.
    """
    if plugins_dir is None:
        plugins_dir = Path(__file__).parent.parent / "plugins"
    if not plugins_dir.exists():
        return 0

    count = 0
    for plugin_file in sorted(plugins_dir.rglob("plugin.py")):
        parts = plugin_file.relative_to(plugins_dir.parent).with_suffix("")
        module_path = ".".join(parts.parts)
        try:
            importlib.import_module(module_path)
            count += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to import plugin %s: %s", module_path, exc)
    return count


def get_plugins(category: str) -> Dict[str, Type]:
    """Return all registered plugins in *category*."""
    return dict(_registry.get(category, {}))


def get_plugin(category: str, name: str) -> Optional[Type]:
    """Return a single plugin class, or ``None``."""
    return _registry.get(category, {}).get(name)


def clear_registry() -> None:
    """Reset all registrations (for testing)."""
    for cat in _registry:
        _registry[cat].clear()
