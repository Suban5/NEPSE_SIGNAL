"""Main entrypoint for the NEPSE analyzer CLI."""

from __future__ import annotations

import logging

from cli.commands import parse_args, run
from config.settings import setup_logging


def main() -> None:
    """Run the command line application."""
    setup_logging()
    logger = logging.getLogger(__name__)
    args = parse_args()
    try:
        run(args)
    except Exception as exc:
        logger.exception("Execution failed: %s", exc)
        raise


if __name__ == "__main__":
    main()
