"""Control-flow graph construction for parsed assembly programs."""

from __future__ import annotations

from dataclasses import dataclass

from .ast_nodes import Instruction, LabelRef, Program


@dataclass
class BasicBlock:
    id: int
    label: str | None
    instructions: list[Instruction]
    successors: list[int]


_CONDITIONAL_JUMPS = {"je", "jne", "jg", "jl", "jge", "jle"}
_BLOCK_ENDS = {"jmp", *_CONDITIONAL_JUMPS, "call", "ret", "hlt"}


def build_blocks(program: Program) -> list[BasicBlock]:
    """Split a program into basic blocks and connect their control flow."""
    instructions = program.instructions
    if not instructions:
        return []

    leaders = {0, *program.labels.values()}
    leaders.update(
        index + 1
        for index, instruction in enumerate(instructions)
        if instruction.opcode in _BLOCK_ENDS and index + 1 < len(instructions)
    )
    starts = sorted(leaders)

    labels_by_index: dict[int, str] = {}
    for name, index in program.labels.items():
        labels_by_index.setdefault(index, name)

    blocks: list[BasicBlock] = []
    instruction_to_block: dict[int, int] = {}
    for block_id, start in enumerate(starts):
        end = starts[block_id + 1] if block_id + 1 < len(starts) else len(instructions)
        first_instruction = instructions[start]
        label = first_instruction.label or labels_by_index.get(start)
        block = BasicBlock(
            id=block_id,
            label=label,
            instructions=instructions[start:end],
            successors=[],
        )
        blocks.append(block)
        for instruction_index in range(start, end):
            instruction_to_block[instruction_index] = block_id

    for block in blocks:
        last = block.instructions[-1]
        next_block = block.id + 1 if block.id + 1 < len(blocks) else None

        if last.opcode in _BLOCK_ENDS and last.opcode not in {"ret", "hlt"}:
            target = last.operands[0]
            if not isinstance(target, LabelRef) or target.name not in program.labels:
                raise ValueError(
                    f"invalid control-flow target at line {last.line}"
                )
            target_index = program.labels[target.name]
            target_block = instruction_to_block[target_index]
            if last.opcode == "jmp":
                block.successors = [target_block]
            elif last.opcode == "call":
                block.successors = [target_block]
                if next_block is not None:
                    block.successors.append(next_block)
            else:
                block.successors = [target_block]
                if next_block is not None:
                    block.successors.append(next_block)
        elif last.opcode not in {"ret", "hlt"} and next_block is not None:
            block.successors = [next_block]

    return blocks


def label_to_block(blocks: list[BasicBlock]) -> dict[str, int]:
    """Return a mapping from each block label to its block id."""
    return {
        block.label: block.id
        for block in blocks
        if block.label is not None
    }


def to_dot(blocks: list[BasicBlock]) -> str:
    lines = ["digraph CFG {"]
    for block in blocks:
        label = f"{block.id}: {block.label}" if block.label else str(block.id)
        escaped_label = label.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'  {block.id} [label="{escaped_label}"];')
    for block in blocks:
        for successor in block.successors:
            lines.append(f"  {block.id} -> {successor};")
    lines.append("}")
    return "\n".join(lines)