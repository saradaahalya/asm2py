"""Recursive-descent parser for the simplified assembly language."""

from __future__ import annotations

from .ast_nodes import (
    AsmSyntaxError,
    Immediate,
    Instruction,
    LabelRef,
    Operand,
    Program,
    Register,
    Token,
    TokenType,
)


class Parser:
    """Parse lexer tokens into an assembly :class:`Program`."""

    _TWO_OPERAND = {"mov", "add", "sub", "mul", "div", "cmp"}
    _ONE_OPERAND = {"inc", "dec", "push", "pop", "print"}
    _JUMPS = {"jmp", "je", "jne", "jg", "jl", "jge", "jle", "call"}
    _ZERO_OPERAND = {"ret", "hlt"}

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.position = 0

    def parse(self) -> Program:
        """Parse all tokens and return the resulting program."""
        program = Program()
        pending_label: str | None = None
        pending_label_line: int | None = None

        while not self._at(TokenType.EOF):
            label, instruction = self._parse_line()
            if label is not None:
                if label in program.labels:
                    raise AsmSyntaxError(f"duplicate label {label!r}", self._previous_line())
                if pending_label is not None:
                    raise AsmSyntaxError("a line cannot contain multiple labels", self._previous_line())
                pending_label = label
                pending_label_line = self._previous_line()
            if instruction is not None:
                if pending_label is not None:
                    instruction.label = pending_label
                    program.labels[pending_label] = len(program.instructions)
                    pending_label = None
                    pending_label_line = None
                program.instructions.append(instruction)

        if pending_label is not None:
            raise AsmSyntaxError(
                f"label {pending_label!r} has no instruction after it",
                pending_label_line if pending_label_line is not None else self._previous_line(),
            )
        return program

    def _parse_line(self) -> tuple[str | None, Instruction | None]:
        """Parse one line according to ``[LABEL_DEF] [instruction] NEWLINE``."""
        label: str | None = None
        if self._at(TokenType.LABEL_DEF):
            label = self._advance().value

        instruction = None
        if self._at(TokenType.INSTRUCTION):
            instruction = self._parse_instruction()

        if not self._at(TokenType.NEWLINE):
            token = self._current()
            if label is not None and token.type is TokenType.EOF:
                raise AsmSyntaxError(f"label {label!r} has no instruction after it", token.line)
            raise AsmSyntaxError("expected end of line", token.line)
        self._advance()
        return label, instruction

    def _parse_instruction(self) -> Instruction:
        """Parse an opcode and its comma-separated operands."""
        opcode_token = self._advance()
        opcode = opcode_token.value
        operands: list[Operand] = []

        if not self._at(TokenType.NEWLINE) and not self._at(TokenType.EOF):
            operands.append(self._parse_operand())
            while self._at(TokenType.COMMA):
                self._advance()
                operands.append(self._parse_operand())

        expected = (
            2 if opcode in self._TWO_OPERAND else
            1 if opcode in self._ONE_OPERAND or opcode in self._JUMPS else 0
        )
        if len(operands) != expected:
            raise AsmSyntaxError(
                f"{opcode} expects {expected} operand(s), got {len(operands)}",
                opcode_token.line,
            )

        self._validate_operands(opcode, operands, opcode_token.line)
        return Instruction(opcode, operands, opcode_token.line)

    def _parse_operand(self) -> Operand:
        """Parse one register, immediate, or label reference."""
        token = self._current()
        if token.type is TokenType.REGISTER:
            self._advance()
            return Register(token.value)
        if token.type is TokenType.NUMBER:
            self._advance()
            return Immediate(int(token.value, 0))
        if token.type is TokenType.IDENTIFIER:
            self._advance()
            return LabelRef(token.value)
        raise AsmSyntaxError("expected an operand", token.line)

    def _validate_operands(self, opcode: str, operands: list[Operand], line: int) -> None:
        if opcode in self._JUMPS:
            if not isinstance(operands[0], LabelRef):
                raise AsmSyntaxError(f"{opcode} target must be a label", line)
            return
        if any(isinstance(operand, LabelRef) for operand in operands):
            raise AsmSyntaxError(f"{opcode} does not accept label operands", line)
        if opcode == "mov" and not isinstance(operands[0], Register):
            raise AsmSyntaxError("mov destination must be a register", line)
        if opcode == "pop" and not isinstance(operands[0], Register):
            raise AsmSyntaxError("pop destination must be a register", line)
        if opcode in {"inc", "dec"} and not isinstance(operands[0], Register):
            raise AsmSyntaxError(f"{opcode} operand must be a register", line)

    def _current(self) -> Token:
        return self.tokens[self.position]

    def _advance(self) -> Token:
        token = self._current()
        self.position += 1
        return token

    def _at(self, token_type: TokenType) -> bool:
        return self._current().type is token_type

    def _previous_line(self) -> int:
        return self.tokens[max(0, self.position - 1)].line