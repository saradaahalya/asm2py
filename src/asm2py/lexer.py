"""Lexer for the simplified assembly language."""

from __future__ import annotations

import re

from .ast_nodes import AsmSyntaxError, Token, TokenType


class Lexer:
    """Convert assembly source text into a sequence of tokens."""

    _INSTRUCTIONS = {
        "mov",
        "add",
        "sub",
        "mul",
        "div",
        "inc",
        "dec",
        "cmp",
        "jmp",
        "je",
        "jne",
        "jg",
        "jl",
        "jge",
        "jle",
        "push",
        "pop",
        "call",
        "ret",
        "print",
        "hlt",
    }
    _REGISTERS = {"eax", "ebx", "ecx", "edx"}
    _IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    _NUMBER = re.compile(r"-?(?:0[xX][0-9A-Fa-f]+|[0-9]+)")

    def __init__(self, source: str) -> None:
        self.source = source

    def tokenize(self) -> list[Token]:
        """Tokenize the source, raising ``AsmSyntaxError`` for bad input."""
        tokens: list[Token] = []
        index = 0
        line = 1
        column = 1

        while index < len(self.source):
            character = self.source[index]

            if character in " \t\f\v":
                index += 1
                column += 1
                continue

            if character == ";":
                while index < len(self.source) and self.source[index] not in "\r\n":
                    index += 1
                    column += 1
                continue

            if character in "\r\n":
                start_line, start_column = line, column
                if character == "\r" and index + 1 < len(self.source) and self.source[index + 1] == "\n":
                    index += 2
                else:
                    index += 1
                tokens.append(Token(TokenType.NEWLINE, "\n", start_line, start_column))
                line += 1
                column = 1
                continue

            if character == ",":
                tokens.append(Token(TokenType.COMMA, character, line, column))
                index += 1
                column += 1
                continue

            number = self._NUMBER.match(self.source, index)
            if number is not None:
                value = number.group()
                tokens.append(Token(TokenType.NUMBER, value, line, column))
                index = number.end()
                column += len(value)
                continue

            identifier = self._IDENTIFIER.match(self.source, index)
            if identifier is not None:
                value = identifier.group()
                normalized = value.lower()
                end = identifier.end()
                if end < len(self.source) and self.source[end] == ":":
                    tokens.append(Token(TokenType.LABEL_DEF, value, line, column))
                    index = end + 1
                    column += len(value) + 1
                else:
                    token_type = TokenType.IDENTIFIER
                    if normalized in self._INSTRUCTIONS:
                        token_type = TokenType.INSTRUCTION
                        value = normalized
                    elif normalized in self._REGISTERS:
                        token_type = TokenType.REGISTER
                        value = normalized
                    tokens.append(Token(token_type, value, line, column))
                    index = end
                    column += len(value)
                continue

            raise AsmSyntaxError(f"unknown character {character!r}", line)

        if tokens and tokens[-1].type is not TokenType.NEWLINE:
            tokens.append(Token(TokenType.NEWLINE, "\n", line, column))
        tokens.append(Token(TokenType.EOF, "", line, column))
        return tokens