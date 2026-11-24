from __future__ import annotations

import argparse
import logging
import sys

from . import config as config_module
from . import poller, status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tudo-ntfy")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print ntfy payloads instead of sending them",
    )
    parser.add_argument(
        "--once", action="store_true", help="Run a single poll cycle and exit"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    status.install_log_buffer()

    try:
        config = config_module.from_env()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    poller.run(config, once=args.once, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
