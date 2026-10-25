"""Command-line entry point: assembly file in, Python file out."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .ast_nodes import AsmSemanticError, AsmSyntaxError, Program, Token
from .codegen import CodeGenerator
from .ir import BasicBlock, build_blocks, to_dot
from .lexer import Lexer
from .optimizer import optimize
from .parser import Parser
from .semantic import SemanticAnalyzer


def _compile_details(
    source: str, do_optimize: bool
) -> tuple[str, list[str], list[Token], Program, list[BasicBlock], dict[str, int]]:
    """Compile source and retain intermediate representations for CLI output."""
    tokens = Lexer(source).tokenize()
    program = Parser(tokens).parse()
    warnings = SemanticAnalyzer(program).analyze()
    blocks = build_blocks(program)
    changes: dict[str, int] = {}
    if do_optimize:
        blocks, changes = optimize(blocks)
    return CodeGenerator(blocks).generate(), warnings, tokens, program, blocks, changes


def compile_source(source: str, do_optimize: bool = True) -> tuple[str, list[str]]:
    """Compile assembly text. Returns (python_code, warnings)."""
    code, warnings, _, _, _, _ = _compile_details(source, do_optimize)
    return code, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="asm2py", description="Translate assembly into a Python program."
    )
    parser.add_argument("input", help="path to the .asm file")
    parser.add_argument("-o", "--output", help="output .py file (default: input name with .py)")
    optimize_group = parser.add_mutually_exclusive_group()
    optimize_group.add_argument(
        "--optimize", dest="optimize", action="store_true", default=True,
        help="run the optimizer (default)",
    )
    optimize_group.add_argument(
        "--no-optimize", dest="optimize", action="store_false",
        help="skip the optimizer",
    )
    parser.add_argument("--show-tokens", action="store_true", help="print lexer tokens")
    parser.add_argument("--show-ast", action="store_true", help="print parsed AST instructions")
    parser.add_argument("--dot", metavar="FILE", help="write the control-flow graph as DOT")
    parser.add_argument("--run", action="store_true", help="run the generated Python program")
    args = parser.parse_args(argv)

    in_path = Path(args.input)
    out_path = Path(args.output) if args.output else in_path.with_suffix(".py")

    try:
        source = in_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {in_path}: {exc.strerror}", file=sys.stderr)
        return 1

    try:
        code, warnings, tokens, program, blocks, changes = _compile_details(
            source, do_optimize=args.optimize
        )
    except (AsmSyntaxError, AsmSemanticError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.show_tokens:
        for token in tokens:
            print(f"{token.type.name}: {token.value!r} (line {token.line})")
    if args.show_ast:
        for index, instruction in enumerate(program.instructions):
            print(
                f"{index}: {instruction.opcode} "
                f"operands={instruction.operands!r} label={instruction.label!r}"
            )
        print(f"labels: {program.labels}")
    if args.optimize:
        for pass_name, count in changes.items():
            print(f"optimizer: {pass_name}: {count} change(s)")

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(code, encoding="utf-8")
        if args.dot:
            dot_path = Path(args.dot)
            dot_path.parent.mkdir(parents=True, exist_ok=True)
            dot_path.write_text(to_dot(blocks), encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write output: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {out_path}")
    if args.run:
        result = subprocess.run(
            [sys.executable, str(out_path)],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.returncode:
            print(f"error: generated program exited with code {result.returncode}", file=sys.stderr)
        return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())