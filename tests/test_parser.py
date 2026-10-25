"""Tests for the assembly parser."""

import pytest

from asm2py.ast_nodes import AsmSyntaxError, Immediate, LabelRef, Register
from asm2py.lexer import Lexer
from asm2py.parser import Parser


def parse(source: str):
    return Parser(Lexer(source).tokenize()).parse()


def test_parses_instructions_and_operands() -> None:
    program = parse("mov eax, 10\nadd eax, ebx\nprint eax\nhlt\n")
    assert len(program.instructions) == 4
    assert program.instructions[0].operands == [Register("eax"), Immediate(10)]
    assert program.instructions[1].opcode == "add"


def test_parses_hex_and_negative_immediates() -> None:
    program = parse("mov eax, 0x10\nsub eax, -2\n")
    assert program.instructions[0].operands[1] == Immediate(16)
    assert program.instructions[1].operands[1] == Immediate(-2)


def test_attaches_inline_label_and_maps_index() -> None:
    program = parse("start: mov eax, 1\nhlt\n")
    assert program.labels == {"start": 0}
    assert program.instructions[0].label == "start"


def test_attaches_label_on_own_line_to_next_instruction() -> None:
    program = parse("loop:\ninc eax\njmp loop\n")
    assert program.labels == {"loop": 0}
    assert program.instructions[0].label == "loop"
    assert program.instructions[1].operands == [LabelRef("loop")]


def test_label_without_following_instruction_is_rejected() -> None:
    with pytest.raises(AsmSyntaxError, match=r"label 'finished' has no instruction after it"):
        parse("hlt\nfinished:\n")


def test_allows_blank_lines() -> None:
    assert len(parse("\n\nhlt\n").instructions) == 1


def test_rejects_wrong_operand_count() -> None:
    with pytest.raises(AsmSyntaxError, match=r"line 1"):
        parse("ret eax\n")


def test_rejects_invalid_mov_destination() -> None:
    with pytest.raises(AsmSyntaxError, match="destination must be a register"):
        parse("mov 5, eax\n")


def test_rejects_non_label_jump_target() -> None:
    with pytest.raises(AsmSyntaxError, match="target must be a label"):
        parse("jmp eax\n")


def test_rejects_missing_newline() -> None:
    with pytest.raises(AsmSyntaxError, match="end of line"):
        parse("hlt")
