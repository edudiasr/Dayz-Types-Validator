"""Interface de linha de comando."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .limits import Limits
from .output import to_json, to_text
from .validator import validate_bytes
from .xmltree import XmlSyntaxError

EXIT_OK = 0
EXIT_ISSUES = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="types-validator",
        description="Valida arquivos types.xml da Central Economy do DayZ.",
    )
    parser.add_argument("files", nargs="+", type=Path, help="um ou mais arquivos types.xml")
    parser.add_argument(
        "-l",
        "--limits",
        action="append",
        type=Path,
        default=[],
        metavar="ARQUIVO",
        help="cfglimitsdefinition.xml ou cfglimitsdefinitionuser.xml (pode repetir)",
    )
    parser.add_argument("-f", "--format", choices=("text", "json"), default="text", help="formato da saída")
    parser.add_argument("--strict", action="store_true", help="avisos também fazem o comando falhar")
    parser.add_argument("--no-color", action="store_true", help="desliga as cores no terminal")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    limits = None
    if args.limits:
        limits = Limits()
        for path in args.limits:
            try:
                limits.merge_file(path.read_bytes())
            except OSError as exc:
                print(f"não foi possível ler {path}: {exc.strerror}", file=sys.stderr)
                return EXIT_USAGE
            except XmlSyntaxError as exc:
                print(f"{path}: XML inválido na linha {exc.line}: {exc.message}", file=sys.stderr)
                return EXIT_USAGE

    reports = []
    for path in args.files:
        try:
            data = path.read_bytes()
        except OSError as exc:
            print(f"não foi possível ler {path}: {exc.strerror}", file=sys.stderr)
            return EXIT_USAGE
        reports.append(validate_bytes(data, str(path), limits))

    if args.format == "json":
        print(to_json(reports))
    else:
        color = not args.no_color and sys.stdout.isatty() and "NO_COLOR" not in os.environ
        if color and os.name == "nt":
            os.system("")  # ativa as sequências ANSI no console do Windows
        print("\n\n".join(to_text(report, color) for report in reports))

    failed = any(r.errors or (args.strict and r.warnings) for r in reports)
    return EXIT_ISSUES if failed else EXIT_OK
