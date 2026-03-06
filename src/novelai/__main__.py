from __future__ import annotations

import argparse

from novelai.app.cli import main as cli_main
from novelai.app.web import main as web_main


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="novelai")
    parser.add_argument("--interface", choices=["web", "tui"], default="tui", help="Which interface to run.")
    args, remaining = parser.parse_known_args(argv)

    if args.interface == "tui":
        cli_main(remaining)
    else:
        web_main()


if __name__ == "__main__":
    main()
