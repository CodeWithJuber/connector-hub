"""Omni Connector Hub — one channel router for all your services."""
import importlib
import os
import pkgutil

from .base import (  # noqa: F401
    BaseConnector,
    ConnectorError,
    get_connector,
    list_connectors,
    register,
)

_LOADED = False


def load_connectors():
    """Import every module under connectors/ so @register decorators fire."""
    global _LOADED
    if _LOADED:
        return
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "connectors")
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith(".py") and not fn.startswith("__"):
                rel = os.path.relpath(os.path.join(dirpath, fn), os.path.dirname(root))
                mod = rel[:-3].replace(os.sep, ".")
                importlib.import_module(mod)
    _LOADED = True
