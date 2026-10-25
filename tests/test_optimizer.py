"""Tests for optimization passes over basic blocks."""

from asm2py.ast_nodes import Immediate, Register
from asm2py.ir import BasicBlock, build_blocks
from asm2py.lexer import Lexer
from asm2py.optimizer import (
    fold_constants,
    optimize,
    remove_noops,
    remove_unreachable_blocks,
)
from asm2py.parser import Parser


def blocks_for(source: str) -> list[BasicBlock]:
    program = Parser(Lexer(source).tokenize()).parse()
    return build_blocks(program)


def test_folds_adjacent_immediate_arithmetic() -> None:
    blocks = blocks_for("mov eax, 4\nadd eax, 3\nsub eax, 1\nhlt\n")

    assert fold_constants(blocks) == 2
    assert [(instruction.opcode, instruction.operands) for instruction in blocks[0].instructions] == [
        ("mov", [Register("eax"), Immediate(6)]),
        ("hlt", []),
    ]
    assert blocks[0].instructions[0].line == 1


def test_does_not_fold_across_blocks_or_registers() -> None:
    blocks = blocks_for("mov eax, 4\nnext: add eax, 3\nhlt\n")
    assert fold_constants(blocks) == 0

    different_register = blocks_for("mov eax, 4\nadd ebx, 3\nhlt\n")
    assert fold_constants(different_register) == 0


def test_removes_arithmetic_and_move_noops() -> None:
    blocks = blocks_for(
        "add eax, 0\n"
        "sub ebx, 0\n"
        "mul ecx, 1\n"
        "mov edx, edx\n"
        "hlt\n"
    )

    assert remove_noops(blocks) == 4
    assert [instruction.opcode for instruction in blocks[0].instructions] == ["hlt"]


def test_keeps_labeled_block_when_its_instructions_become_empty() -> None:
    blocks = blocks_for("same: mov eax, eax\n")

    assert remove_noops(blocks) == 1
    assert blocks[0].label == "same"
    assert blocks[0].instructions == []


def test_removes_unreachable_blocks_without_renumbering() -> None:
    blocks = blocks_for("jmp live\nmov eax, 1\nlive: hlt\n")

    assert remove_unreachable_blocks(blocks) == 1
    assert [block.id for block in blocks] == [0, 2]


def test_optimize_reports_changes_per_pass() -> None:
    blocks = blocks_for("mov eax, 1\nadd eax, 2\njmp done\nmov ebx, 5\ndone: hlt\n")

    optimized, changes = optimize(blocks)

    assert optimized is blocks
    assert changes == {
        "fold_constants": 1,
        "remove_noops": 0,
        "remove_unreachable_blocks": 1,
    }
    assert [block.id for block in optimized] == [0, 2]


def test_optimized_program_prints_same_output() -> None:
    source = "mov eax, 2\nadd eax, 3\nmul eax, 4\nprint eax\nhlt\n"
    blocks = blocks_for(source)
    optimized, _ = optimize(blocks_for(source))

    def printed_values(program_blocks: list[BasicBlock]) -> list[int]:
        registers: dict[str, int] = {}
        output = []
        for block in program_blocks:
            for instruction in block.instructions:
                if instruction.opcode == "mov":
                    destination, value = instruction.operands
                    registers[destination.name] = (
                        value.value if isinstance(value, Immediate) else registers[value.name]
                    )
                elif instruction.opcode in {"add", "sub", "mul"}:
                    destination, value = instruction.operands
                    right = value.value if isinstance(value, Immediate) else registers[value.name]
                    if instruction.opcode == "add":
                        registers[destination.name] += right
                    elif instruction.opcode == "sub":
                        registers[destination.name] -= right
                    else:
                        registers[destination.name] *= right
                elif instruction.opcode == "print":
                    output.append(registers[instruction.operands[0].name])
        return output

    assert printed_values(blocks) == [20]
    assert printed_values(optimized) == [20]
