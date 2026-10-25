"""Small, block-local optimization passes for the assembly IR."""

from __future__ import annotations

from .ast_nodes import Immediate, Register, Instruction
from .ir import BasicBlock


def fold_constants(blocks: list[BasicBlock]) -> int:
    """Fold adjacent immediate arithmetic into a preceding ``mov``."""
    changes = 0
    for block in blocks:
        index = 0
        while index + 1 < len(block.instructions):
            move, arithmetic = block.instructions[index:index + 2]
            if (
                move.opcode == "mov"
                and len(move.operands) == 2
                and isinstance(move.operands[0], Register)
                and isinstance(move.operands[1], Immediate)
                and arithmetic.opcode in {"add", "sub", "mul"}
                and len(arithmetic.operands) == 2
                and isinstance(arithmetic.operands[0], Register)
                and arithmetic.operands[0].name == move.operands[0].name
                and isinstance(arithmetic.operands[1], Immediate)
                and arithmetic.label is None
            ):
                value = move.operands[1].value
                operand = arithmetic.operands[1].value
                if arithmetic.opcode == "add":
                    result = value + operand
                elif arithmetic.opcode == "sub":
                    result = value - operand
                else:
                    result = value * operand
                block.instructions[index:index + 2] = [
                    Instruction(
                        "mov",
                        [move.operands[0], Immediate(result)],
                        move.line,
                        move.label,
                    )
                ]
                changes += 1
            else:
                index += 1
    return changes


def remove_noops(blocks: list[BasicBlock]) -> int:
    """Remove instructions that have no effect on a register value."""
    changes = 0
    control_terminators = {"jmp", "call", "ret", "hlt"}
    for block in blocks:
        retained = []
        for index, instruction in enumerate(block.instructions):
            if (
                index == len(block.instructions) - 1
                and instruction.opcode in control_terminators
            ):
                retained.append(instruction)
                continue

            is_noop = (
                instruction.opcode in {"add", "sub"}
                and len(instruction.operands) == 2
                and isinstance(instruction.operands[0], Register)
                and isinstance(instruction.operands[1], Immediate)
                and instruction.operands[1].value == 0
            ) or (
                instruction.opcode == "mul"
                and len(instruction.operands) == 2
                and isinstance(instruction.operands[0], Register)
                and isinstance(instruction.operands[1], Immediate)
                and instruction.operands[1].value == 1
            ) or (
                instruction.opcode == "mov"
                and len(instruction.operands) == 2
                and isinstance(instruction.operands[0], Register)
                and isinstance(instruction.operands[1], Register)
                and instruction.operands[0].name == instruction.operands[1].name
            )
            if is_noop:
                changes += 1
            else:
                retained.append(instruction)
        block.instructions = retained
    return changes


def remove_unreachable_blocks(blocks: list[BasicBlock]) -> int:
    """Remove blocks not reachable from the entry block without renumbering."""
    blocks_by_id = {block.id: block for block in blocks}
    if 0 not in blocks_by_id:
        removed = len(blocks)
        blocks.clear()
        return removed

    reachable: set[int] = set()
    pending = [0]
    while pending:
        block_id = pending.pop()
        if block_id in reachable:
            continue
        block = blocks_by_id.get(block_id)
        if block is None:
            continue
        reachable.add(block_id)
        pending.extend(block.successors)

    retained = [block for block in blocks if block.id in reachable]
    removed = len(blocks) - len(retained)
    blocks[:] = retained
    return removed


def optimize(blocks: list[BasicBlock]) -> tuple[list[BasicBlock], dict[str, int]]:
    """Run each optimization pass and return the change count per pass."""
    changes = {
        "fold_constants": fold_constants(blocks),
        "remove_noops": remove_noops(blocks),
        "remove_unreachable_blocks": remove_unreachable_blocks(blocks),
    }
    return blocks, changes