from __future__ import annotations

import argparse

from novelai.interfaces.cli import main as cli_main
from novelai.interfaces.web.server import main as web_main


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="novelai")
    parser.add_argument(
        "--interface",
        choices=["cli", "web", "tui", "gui"],
        default="tui",
        help="Which interface to run.",
    )
    args, remaining = parser.parse_known_args(argv)

    if args.interface == "cli":
        cli_main(remaining)
    elif args.interface == "tui":
        cli_main(["tui", *remaining])
    elif args.interface == "gui":
        cli_main(["gui", *remaining])
    else:
        web_main()


if __name__ == "__main__":
    main()
