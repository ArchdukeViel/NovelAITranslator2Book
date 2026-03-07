"""Source-checkout shim for the ``novelai`` package."""

from __future__ import annotations

from pathlib import Path

_SRC_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "src" / "novelai"
__path__ = [str(_SRC_PACKAGE_DIR)]
__file__ = str(_SRC_PACKAGE_DIR / "__init__.py")

exec(
    compile(
        (_SRC_PACKAGE_DIR / "__init__.py").read_text(encoding="utf-8"),
        __file__,
        "exec",
    ),
    globals(),
    globals(),
)
