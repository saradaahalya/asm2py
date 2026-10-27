"""Tests for structured Python generation."""

import contextlib
import io
from pathlib import Path

from asm2py.codegen import CodeGenerator
from asm2py.ir import build_blocks
from asm2py.lexer import Lexer
from asm2py.parser import Parser
from asm2py.structurer import structure_program


SAMPLES = Path(__file__).parent / "samples"


def _program(source: str):
    return Parser(Lexer(source).tokenize()).parse()


def _run(source: str, structured: bool) -> str:
    program = _program(source)
    if structured:
        code = structure_program(program)
        assert code is not None
    else:
        code = CodeGenerator(build_blocks(program)).generate()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(code, {})
    return output.getvalue()


def test_structured_output_matches_state_machine_for_all_samples() -> None:
    for sample in SAMPLES.glob("*.asm"):
        source = sample.read_text(encoding="utf-8")
        assert _run(source, True) == _run(source, False)


def test_structured_samples_avoid_state_machine_artifacts() -> None:
    for name in ("sum_to_n.asm", "factorial.asm", "max_of_two.asm", "subroutine.asm"):
        source = (SAMPLES / name).read_text(encoding="utf-8")
        code = structure_program(_program(source))
        assert code is not None
        for forbidden in ("pc", "zf", "sf", "continue", "call_stack"):
            assert forbidden not in code
