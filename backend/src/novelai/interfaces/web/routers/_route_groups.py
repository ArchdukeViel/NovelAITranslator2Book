from __future__ import annotations

from collections.abc import Iterable

from fastapi import APIRouter
from fastapi.routing import APIRoute

from novelai.interfaces.web.routers import _legacy_novels

RouteSpec = str | tuple[str, Iterable[str]]


def include_legacy_routes(router: APIRouter, specs: Iterable[RouteSpec]) -> None:
    """Attach selected legacy endpoint registrations to a focused router.

    The handler bodies still live in `_legacy_novels` during this transition.
    This lets the public API keep the same paths while router modules become
    domain-focused.
    """
    normalized_specs: list[tuple[str, set[str] | None]] = []
    for spec in specs:
        if isinstance(spec, str):
            normalized_specs.append((spec, None))
            continue
        path, methods = spec
        normalized_specs.append((path, {method.upper() for method in methods}))

    for route in _legacy_novels.router.routes:
        if not isinstance(route, APIRoute):
            continue
        for path, methods in normalized_specs:
            if route.path != path:
                continue
            if methods is not None and not route.methods.intersection(methods):
                continue
            router.routes.append(route)
            break
