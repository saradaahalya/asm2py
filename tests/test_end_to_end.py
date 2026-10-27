import subprocess
import sys
from pathlib import Path

import pytest

from asm2py.main import compile_source

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "tests" / "samples"
ENV = {**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")}


def compile_file(asm: Path, out: Path, *extra: str):
    return subprocess.run(
        [sys.executable, "-m", "asm2py.main", str(asm), "-o", str(out), *extra],
        capture_output=True, text=True, timeout=30, env=ENV, cwd=ROOT,
    )


def run_py(path: Path) -> str:
    result = subprocess.run(
        [sys.executable, str(path)], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


EXPECTED = {
    "sum_to_n": "15\n",
    "factorial": "120\n",
    "fibonacci": "0\n1\n1\n2\n3\n5\n8\n13\n21\n34\n",
    "max_of_two": "12\n",
}


@pytest.mark.parametrize("name", EXPECTED)
@pytest.mark.parametrize("extra", [(), ("--no-optimize",)])
def test_sample_programs(name, extra, tmp_path):
    out = tmp_path / f"{name}.py"
    result = compile_file(SAMPLES / f"{name}.asm", out, *extra)
    assert result.returncode == 0, result.stderr
    assert run_py(out) == EXPECTED[name]


def test_source_without_trailing_newline(tmp_path):
    asm = tmp_path / "no_newline.asm"
    asm.write_text("mov eax, 4\nprint eax\nhlt", encoding="utf-8")
    out = tmp_path / "no_newline.py"
    assert compile_file(asm, out).returncode == 0
    assert run_py(out) == "4\n"


def test_undefined_label_is_clean_error(tmp_path):
    asm = tmp_path / "bad.asm"
    asm.write_text("jmp nowhere\nhlt\n", encoding="utf-8")
    result = compile_file(asm, tmp_path / "bad.py")
    assert result.returncode != 0
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "bad.py").exists()


def test_missing_input_file(tmp_path):
    result = compile_file(tmp_path / "nope.asm", tmp_path / "nope.py")
    assert result.returncode != 0
    assert "Traceback" not in result.stderr


def test_runtime_division_by_zero(tmp_path):
    asm = tmp_path / "div0.asm"
    asm.write_text("mov eax, 5\nmov ebx, 0\ndiv eax, ebx\nhlt\n", encoding="utf-8")
    out = tmp_path / "div0.py"
    assert compile_file(asm, out).returncode == 0
    result = subprocess.run(
        [sys.executable, str(out)], capture_output=True, text=True, timeout=10
    )
    assert result.returncode != 0
    assert "ZeroDivisionError" in result.stderr


def test_structured_compile_honors_optimization() -> None:
    source = "mov eax, 2\nadd eax, 3\nprint eax\nhlt\n"
    optimized, _ = compile_source(source, True)
    unoptimized, _ = compile_source(source, False)
    assert "eax = 5" in optimized
    assert "add eax, 3" not in optimized
    assert "add eax, 3" in unoptimized


def test_show_tokens(tmp_path):
    asm = tmp_path / "tokens.asm"
    asm.write_text("mov eax, 1\nhlt\n", encoding="utf-8")
    result = compile_file(asm, tmp_path / "tokens.py", "--show-tokens")
    assert result.returncode == 0, result.stderr
    assert "INSTRUCTION: 'mov' (line 1)" in result.stdout
    assert "REGISTER: 'eax' (line 1)" in result.stdout
    assert "EOF: ''" in result.stdout


def test_show_ast(tmp_path):
    asm = tmp_path / "ast.asm"
    asm.write_text("start: mov eax, 1\nhlt\n", encoding="utf-8")
    result = compile_file(asm, tmp_path / "ast.py", "--show-ast")
    assert result.returncode == 0, result.stderr
    assert "0: mov operands=[Register(name='eax'), Immediate(value=1)] label='start'" in result.stdout
    assert "labels: {'start': 0}" in result.stdout


def test_dot_writes_parent_folders(tmp_path):
    asm = tmp_path / "graph.asm"
    dot = tmp_path / "nested" / "graphs" / "graph.dot"
    asm.write_text("start: jmp done\ndone: hlt\n", encoding="utf-8")
    result = compile_file(asm, tmp_path / "graph.py", "--dot", str(dot))
    assert result.returncode == 0, result.stderr
    assert dot.exists()
    assert "digraph CFG" in dot.read_text(encoding="utf-8")


def test_run_shows_generated_program_output(tmp_path):
    asm = tmp_path / "run.asm"
    asm.write_text("mov eax, 7\nprint eax\nhlt\n", encoding="utf-8")
    result = compile_file(asm, tmp_path / "run.py", "--run")
    assert result.returncode == 0, result.stderr
    assert "wrote " in result.stdout
    assert "7\n" in result.stdout