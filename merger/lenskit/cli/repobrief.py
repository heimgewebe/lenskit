from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from .cmd_repobrief import register_repobrief_command_groups, run_repobrief


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repobrief",
        description="RepoBrief: explicit snapshot and read-only brief access commands",
    )
    register_repobrief_command_groups(parser)
    return parser


def main(args: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    parsed_args = parser.parse_args(list(args) if args is not None else None)
    return run_repobrief(parsed_args)


if __name__ == "__main__":
    sys.exit(main())
