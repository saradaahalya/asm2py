"""Tests for the assembly lexer."""

import pytest

from asm2py.ast_nodes import AsmSyntaxError, Token, TokenType
from asm2py.lexer import Lexer


def test_tokenizes_instruction_and_register_case_insensitively() -> None:
    tokens = Lexer("MOV EAX").tokenize()
    assert [(token.type, token.value) for token in tokens] == [
        (TokenType.INSTRUCTION, "mov"),
        (TokenType.REGISTER, "eax"),
        (TokenType.NEWLINE, "\n"),
        (TokenType.EOF, ""),
    ]


def test_tokenizes_decimal_and_negative_numbers() -> None:
    tokens = Lexer("add eax, -42").tokenize()
    assert [token.value for token in tokens[:-2]] == ["add", "eax", ",", "-42"]
    assert tokens[3].type is TokenType.NUMBER


def test_tokenizes_hex_numbers() -> None:
    tokens = Lexer("mov eax, 0xFF").tokenize()
    assert tokens[3].type is TokenType.NUMBER
    assert tokens[3].value == "0xFF"


def test_skips_comments() -> None:
    tokens = Lexer("mov eax, 1 ; ignored\n; whole line\nhlt").tokenize()
    assert [token.type for token in tokens] == [
        TokenType.INSTRUCTION,
        TokenType.REGISTER,
        TokenType.COMMA,
        TokenType.NUMBER,
        TokenType.NEWLINE,
        TokenType.NEWLINE,
        TokenType.INSTRUCTION,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_tokenizes_label_definition() -> None:
    tokens = Lexer("start: jmp START").tokenize()
    assert tokens[0].type is TokenType.LABEL_DEF
    assert tokens[0].value == "start"
    assert tokens[2].type is TokenType.IDENTIFIER
    assert tokens[2].value == "START"


def test_tokenizes_newlines_and_tracks_positions() -> None:
    tokens = Lexer("mov eax,\n  7").tokenize()
    assert tokens[0].line == 1 and tokens[0].column == 1
    assert tokens[3].type is TokenType.NEWLINE
    assert tokens[3].line == 1 and tokens[3].column == 9
    assert tokens[4].line == 2 and tokens[4].column == 3


def test_supports_crlf_newlines() -> None:
    tokens = Lexer("hlt\r\n").tokenize()
    assert tokens[1] == Token(TokenType.NEWLINE, "\n", 1, 4)
    assert tokens[-1].line == 2


def test_ends_with_eof_token_at_current_position() -> None:
    token = Lexer("  ").tokenize()[-1]
    assert token.type is TokenType.EOF
    assert (token.line, token.column) == (1, 3)


def test_adds_newline_before_eof_when_source_has_no_trailing_newline() -> None:
    tokens = Lexer("mov eax, 1\nhlt").tokenize()
    assert tokens[-2] == Token(TokenType.NEWLINE, "\n", 2, 4)
    assert tokens[-1].type is TokenType.EOF


def test_unknown_character_raises_syntax_error_with_line() -> None:
    with pytest.raises(AsmSyntaxError, match=r"line 2"):
        Lexer("hlt\n@").tokenize()
