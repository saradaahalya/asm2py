"""Semantic checks for parsed assembly programs."""

from __future__ import annotations

from .ast_nodes import (
    AsmSemanticError,
    Immediate,
    LabelRef,
    Operand,
    Program,
    Register,
)


class SemanticAnalyzer:
    """Validate a program and report basic data-flow warnings."""

    _JUMPS = {"jmp", "je", "jne", "jg", "jl", "jge", "jle", "call"}
    _TERMINATORS = {"jmp", "ret", "hlt"}
    _ARITHMETIC = {"add", "sub", "mul", "div"}
    _READ_DESTINATIONS = {"add", "sub", "mul", "inc", "dec"}

    def __init__(self, program: Program) -> None:
        self.program = program

    def analyze(self) -> list[str]:
        """Raise on semantic errors and return source-line warnings."""
        warnings: list[str] = []
        written_registers: set[str] = set()
        instructions = self.program.instructions

        for index, instruction in enumerate(instructions):
            if instruction.opcode in self._JUMPS:
                target = instruction.operands[0]
                if isinstance(target, LabelRef) and target.name not in self.program.labels:
                    raise AsmSemanticError(
                        f"undefined label {target.name!r}",
                        instruction.line,
                    )

            if instruction.opcode == "div" and any(
                isinstance(operand, Immediate) and operand.value == 0
                for operand in instruction.operands
            ):
                raise AsmSemanticError("division by zero", instruction.line)

            if (
                index > 0
                and instructions[index - 1].opcode in self._TERMINATORS
                and instruction.label is None
            ):
                warnings.append(
                    f"Unreachable instruction at line {instruction.line}"
                )

            for register in self._read_registers(instruction.opcode, instruction.operands):
                if register.name not in written_registers:
                    warnings.append(
                        f"Register {register.name} read before write at line {instruction.line}"
                    )

            written_registers.update(
                register.name
                for register in self._written_registers(instruction.opcode, instruction.operands)
            )

        if not instructions or instructions[-1].opcode not in {"hlt", "ret"}:
            line = instructions[-1].line if instructions else 1
            warnings.append(f"Program does not end with hlt or ret (line {line})")

        return warnings

    def _read_registers(self, opcode: str, operands: list[Operand]) -> list[Register]:
        read_operands = []
        if opcode in {"mov", "add", "sub", "mul", "div"}:
            read_operands.extend(operands[1:])
        elif opcode == "cmp":
            read_operands.extend(operands)
        elif opcode in {"print", "push"}:
            read_operands.extend(operands)

        if opcode in self._READ_DESTINATIONS:
            read_operands.extend(operands[:1])

        return [operand for operand in read_operands if isinstance(operand, Register)]

    def _written_registers(self, opcode: str, operands: list[Operand]) -> list[Register]:
        if opcode in {"mov", "pop", *self._ARITHMETIC, "inc", "dec"} and operands:
            written = [operands[0]] if isinstance(operands[0], Register) else []
        else:
            written = []

        if opcode == "div":
            written.extend((Register("eax"), Register("edx")))

        return written