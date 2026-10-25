"""Tests for semantic analysis of parsed assembly programs."""

import pytest

from asm2py.ast_nodes import AsmSemanticError
from asm2py.lexer import Lexer
from asm2py.parser import Parser
from asm2py.semantic import SemanticAnalyzer


def analyze(source: str) -> list[str]:
    program = Parser(Lexer(source).tokenize()).parse()
    return SemanticAnalyzer(program).analyze()


def test_rejects_undefined_jump_target() -> None:
    with pytest.raises(AsmSemanticError, match=r"undefined label 'missing'.*line 1"):
        analyze("jmp missing\n")


def test_rejects_undefined_call_target() -> None:
    with pytest.raises(AsmSemanticError, match=r"undefined label 'routine'.*line 2"):
        analyze("mov eax, 0\ncall routine\n")


def test_rejects_division_by_zero() -> None:
    with pytest.raises(AsmSemanticError, match=r"division by zero.*line 2"):
        analyze("mov eax, 5\ndiv eax, 0\n")


def test_warns_when_register_is_read_before_write() -> None:
    warnings = analyze("print eax\nhlt\n")
    assert any("Register eax read before write at line 1" in warning for warning in warnings)


def test_tracks_register_writes_in_program_order() -> None:
    warnings = analyze("mov eax, 1\nadd eax, 2\nprint eax\nhlt\n")
    assert not any("Register eax read before write" in warning for warning in warnings)


def test_arithmetic_destination_is_read_before_write() -> None:
    warnings = analyze("add eax, 1\nhlt\n")
    assert any("Register eax read before write at line 1" in warning for warning in warnings)


def test_division_marks_eax_and_edx_as_written() -> None:
    warnings = analyze("mov ebx, 1\nmov ecx, 2\ndiv ebx, ecx\nprint eax\nprint edx\nret\n")
    assert not any("Register eax read before write" in warning for warning in warnings)
    assert not any("Register edx read before write" in warning for warning in warnings)


def test_warns_for_unreachable_unlabeled_instruction() -> None:
    warnings = analyze("jmp done\nprint eax\ndone: hlt\n")
    assert any("Unreachable instruction at line 2" in warning for warning in warnings)


def test_does_not_warn_for_labeled_instruction_after_terminator() -> None:
    warnings = analyze("hlt\nnext: print eax\nret\n")
    assert not any("Unreachable instruction" in warning for warning in warnings)


def test_warns_when_program_does_not_end_with_hlt_or_ret() -> None:
    warnings = analyze("mov eax, 1\n")
    assert any("Program does not end with hlt or ret (line 1)" in warning for warning in warnings)
