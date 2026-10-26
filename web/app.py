import os
import subprocess
import sys
import tempfile
from pathlib import Path

from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from asm2py.ast_nodes import AsmSemanticError, AsmSyntaxError  # noqa: E402
from asm2py.main import compile_source  # noqa: E402
from asm2py.structurer import CannotStructure  # noqa: E402

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/compile")
def compile_route():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(ok=False, error="Request body must be a JSON object.")
    source = data.get("source", "")
    if not isinstance(source, str):
        return jsonify(ok=False, error="'source' must be a string.")
    optimize = bool(data.get("optimize", True))
    try:
        code, warnings = compile_source(source, optimize, style="structured")
    except (AsmSyntaxError, AsmSemanticError, CannotStructure, ValueError) as exc:
        return jsonify(ok=False, error=str(exc))

    output = ""
    if data.get("run"):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            path = f.name
        try:
            result = subprocess.run(
                [sys.executable, path], capture_output=True, text=True, timeout=5
            )
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            output = "Timed out after 5 seconds (infinite loop?)"
        finally:
            os.remove(path)

    return jsonify(ok=True, code=code, warnings=warnings, output=output)


if __name__ == "__main__":
    app.run(debug=False, port=5000)