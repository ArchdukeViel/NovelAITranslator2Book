from __future__ import annotations

import argparse

from novelai.interfaces.cli import main as cli_main
from novelai.interfaces.web.server import main as web_main


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="novelai")
    parser.add_argument(
        "--interface",
        choices=["web", "cli"],
        default="web",
        help="Which interface to run.",
    )
    parser.add_argument("--reload", action="store_true", help="Reload the backend when Python files change.")
    args, remaining = parser.parse_known_args(argv)

    if args.interface == "cli":
        cli_main(remaining)
        return

    web_main(reload=bool(args.reload))


if __name__ == "__main__":
    main()
