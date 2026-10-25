"""Command-line entry point: assembly file in, Python file out."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .ast_nodes import AsmSemanticError, AsmSyntaxError
from .codegen import CodeGenerator
from .ir import build_blocks
from .lexer import Lexer
from .optimizer import optimize
from .parser import Parser
from .semantic import SemanticAnalyzer


def compile_source(source: str, do_optimize: bool = True) -> tuple[str, list[str]]:
    """Compile assembly text. Returns (python_code, warnings)."""
    if not source.endswith("\n"):
        source += "\n"  # the parser needs a newline after the last line
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    warnings = SemanticAnalyzer(program).analyze()
    blocks = build_blocks(program)
    if do_optimize:
        blocks, _ = optimize(blocks)
    return CodeGenerator(blocks).generate(), warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="asm2py", description="Translate assembly into a Python program."
    )
    parser.add_argument("input", help="path to the .asm file")
    parser.add_argument("-o", "--output", help="output .py file (default: input name with .py)")
    parser.add_argument("--no-optimize", action="store_true", help="skip the optimizer")
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    out_path = Path(args.output) if args.output else in_path.with_suffix(".py")

    try:
        source = in_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {in_path}: {exc.strerror}", file=sys.stderr)
        return 1

    try:
        code, warnings = compile_source(source, do_optimize=not args.no_optimize)
    except (AsmSyntaxError, AsmSemanticError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    out_path.write_text(code, encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())