"""Tests for basic-block and control-flow graph construction."""

from asm2py.lexer import Lexer
from asm2py.parser import Parser
from asm2py.ir import build_blocks, label_to_block, to_dot


def blocks_for(source: str):
    program = Parser(Lexer(source).tokenize()).parse()
    return build_blocks(program)


def test_builds_expected_loop_blocks() -> None:
    blocks = blocks_for(
        "mov ecx, 5\n"
        "mov eax, 0\n"
        "loop1:\n"
        "add eax, ecx\n"
        "dec ecx\n"
        "cmp ecx, 0\n"
        "jne loop1\n"
        "print eax\n"
        "hlt\n"
    )

    assert len(blocks) == 3
    assert [(block.id, block.label) for block in blocks] == [
        (0, None),
        (1, "loop1"),
        (2, None),
    ]
    assert [[instruction.opcode for instruction in block.instructions] for block in blocks] == [
        ["mov", "mov"],
        ["add", "dec", "cmp", "jne"],
        ["print", "hlt"],
    ]
    assert [block.successors for block in blocks] == [[1], [1, 2], []]


def test_conditional_jump_and_else_layout() -> None:
    blocks = blocks_for(
        "cmp eax, 0\n"
        "je otherwise\n"
        "mov ebx, 1\n"
        "jmp end\n"
        "otherwise: mov ebx, 2\n"
        "end: hlt\n"
    )

    assert [block.successors for block in blocks] == [[2, 1], [3], [3], []]
    assert label_to_block(blocks) == {"otherwise": 2, "end": 3}


def test_call_has_target_and_return_successors() -> None:
    blocks = blocks_for(
        "call worker\n"
        "print eax\n"
        "hlt\n"
        "worker: mov eax, 1\n"
        "ret\n"
    )

    assert [block.successors for block in blocks] == [[2, 1], [], []]
    assert [[instruction.opcode for instruction in block.instructions] for block in blocks] == [
        ["call"],
        ["print", "hlt"],
        ["mov", "ret"],
    ]
    assert label_to_block(blocks) == {"worker": 2}


def test_jmp_has_only_target_successor() -> None:
    blocks = blocks_for("jmp done\nmov eax, 1\ndone: hlt\n")
    assert blocks[0].successors == [2]


def test_ret_and_hlt_have_no_successors() -> None:
    blocks = blocks_for("ret\nhlt\n")
    assert [block.successors for block in blocks] == [[], []]


def test_to_dot_includes_nodes_and_edges() -> None:
    blocks = blocks_for("start: jmp end\nend: hlt\n")
    dot = to_dot(blocks)

    assert dot.startswith("digraph CFG {\n")
    assert '0 [label="0: start"];' in dot
    assert '1 [label="1: end"];' in dot
    assert "  0 -> 1;" in dot
    assert dot.endswith("}")


def test_empty_program_has_no_blocks() -> None:
    assert blocks_for("") == []
