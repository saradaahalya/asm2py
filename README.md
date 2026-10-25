\# asm2py



asm2py translates a simplified x86-style assembly language into an equivalent runnable Python program.



\## Pipeline



Lexer -> Parser -> Semantic Analyzer -> IR (basic blocks / CFG) -> Optimizer -> Code Generator -> `.py` file



\## Usage (yours)



From the project root:



```

python -m pip install pytest

set PYTHONPATH=src            (PowerShell: $env:PYTHONPATH = "src")

python -m asm2py.main tests/samples/sum\_to\_n.asm -o out.py

python out.py

```



Options:



\- `-o FILE` sets the output file (default: the input name with `.py`).

\- `--no-optimize` skips the optimizer.



Syntax and semantic errors are printed as `error: ... (line N)`. Semantic warnings go to stderr.



\## Generated code (yours)



The output is a single Python program. Registers `eax`, `ebx`, `ecx`, `edx` are variables, flags `zf` and `sf` are booleans, and `stack` and `call\_stack` are lists. Each basic block becomes one `if pc == <id>:` branch inside a `while True:` loop. Jumps set `pc` and `continue`. Each line keeps its original assembly as a trailing comment.



Notes:



\- Fall-through and call return use the next block in the list, not `id + 1`, because the optimizer can leave gaps in block ids.

\- A block with no instructions simply falls through.

\- `div dst, src` sets `edx = dst % src` first, then `dst = dst // src`, and raises `ZeroDivisionError` (with the line number) if `src` is 0.

\- Values are plain Python ints (no 32-bit wraparound).



\## Sample programs (yours)



| File | Output |

|------|--------|

| `tests/samples/sum\_to\_n.asm` | `15` |

| `tests/samples/factorial.asm` | `120` |

| `tests/samples/fibonacci.asm` | first 10 Fibonacci numbers |

| `tests/samples/max\_of\_two.asm` | `12` |



\## Running the tests (yours)



Run from the project root, not from `src`:



```

python -m pytest

```

