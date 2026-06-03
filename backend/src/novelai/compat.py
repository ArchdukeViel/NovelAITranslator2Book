from __future__ import annotations

"""Central compatibility layer for legacy import paths.

New code should import from the canonical modules listed as values in
``LEGACY_MODULE_ALIASES``. These aliases keep older integrations working after
the web-focused folder reorganization without scattering tiny shim files across
the package.
"""

import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from types import ModuleType

LEGACY_MODULE_ALIASES: dict[str, str] = {
    "novelai.interfaces": "novelai.runtime",
    "novelai.interfaces.cli": "novelai.runtime.cli",
    "novelai.interfaces.web": "novelai.api",
    "novelai.interfaces.web.app": "novelai.api.app",
    "novelai.interfaces.web.server": "novelai.api.server",
    "novelai.interfaces.web.routers": "novelai.api.routers",
    "novelai.interfaces.web.routers.activity": "novelai.api.routers.activity",
    "novelai.interfaces.web.routers.admin": "novelai.api.routers.admin",
    "novelai.interfaces.web.routers.dependencies": "novelai.api.routers.dependencies",
    "novelai.interfaces.web.routers.editor": "novelai.api.routers.editor",
    "novelai.interfaces.web.routers.jobs": "novelai.api.routers.activity",
    "novelai.interfaces.web.routers.library": "novelai.api.routers.library",
    "novelai.interfaces.web.routers.novels": "novelai.api.routers.novels",
    "novelai.interfaces.web.routers.operations": "novelai.api.routers.operations",
    "novelai.interfaces.web.routers.requests": "novelai.api.routers.requests",
    "novelai.interfaces.web.routers.sources": "novelai.api.routers.sources",
    "novelai.jobs": "novelai.activity",
    "novelai.jobs.queue": "novelai.activity.queue",
    "novelai.jobs.runner": "novelai.activity.runner",
    "novelai.jobs.worker": "novelai.activity.worker",
    "novelai.pipeline": "novelai.translation.pipeline",
    "novelai.pipeline.context": "novelai.translation.pipeline.context",
    "novelai.pipeline.pipeline": "novelai.translation.pipeline.pipeline",
    "novelai.pipeline.stages": "novelai.translation.pipeline.stages",
    "novelai.pipeline.stages.base": "novelai.translation.pipeline.stages.base",
    "novelai.pipeline.stages.fetch": "novelai.translation.pipeline.stages.fetch",
    "novelai.pipeline.stages.parse": "novelai.translation.pipeline.stages.parse",
    "novelai.pipeline.stages.post_process": "novelai.translation.pipeline.stages.post_process",
    "novelai.pipeline.stages.segment": "novelai.translation.pipeline.stages.segment",
    "novelai.pipeline.stages.translate": "novelai.translation.pipeline.stages.translate",
    "novelai.services.job_queue": "novelai.activity.queue",
    "novelai.services.job_runner": "novelai.activity.runner",
    "novelai.services.job_worker": "novelai.activity.worker",
    "novelai.services.storage_service": "novelai.storage.service",
    "novelai.services.translation_service": "novelai.translation.service",
}


def _set_parent_attribute(module_name: str, module: ModuleType) -> None:
    parent_name, _, attribute = module_name.rpartition(".")
    if not parent_name:
        return
    parent = sys.modules.get(parent_name)
    if parent is not None:
        setattr(parent, attribute, module)


class _LegacyAliasLoader(importlib.abc.Loader):
    def __init__(self, legacy_name: str, target_name: str) -> None:
        self.legacy_name = legacy_name
        self.target_name = target_name

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        module = importlib.import_module(self.target_name)
        sys.modules[self.legacy_name] = module
        _set_parent_attribute(self.legacy_name, module)
        return module

    def exec_module(self, module: ModuleType) -> None:
        return None


class _LegacyAliasFinder(importlib.abc.MetaPathFinder):
    def __init__(self, aliases: dict[str, str]) -> None:
        self.aliases = dict(aliases)

    def find_spec(
        self,
        fullname: str,
        path: object | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        target_name = self.aliases.get(fullname)
        if target_name is None:
            return None

        target_spec = importlib.util.find_spec(target_name)
        if target_spec is None:
            return None

        is_package = target_spec.submodule_search_locations is not None
        spec = importlib.machinery.ModuleSpec(
            fullname,
            _LegacyAliasLoader(fullname, target_name),
            is_package=is_package,
        )
        spec.origin = f"alias:{target_name}"
        if target_spec.submodule_search_locations is not None:
            spec.submodule_search_locations = list(target_spec.submodule_search_locations)
        return spec


def install_legacy_import_aliases() -> None:
    """Install lazy import aliases for removed or moved modules."""
    for finder in sys.meta_path:
        if isinstance(finder, _LegacyAliasFinder):
            return
    sys.meta_path.insert(0, _LegacyAliasFinder(LEGACY_MODULE_ALIASES))


__all__ = ["LEGACY_MODULE_ALIASES", "install_legacy_import_aliases"]
