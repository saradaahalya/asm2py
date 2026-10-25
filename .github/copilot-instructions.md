Project: asm2py, a compiler that translates a simplified x86-style assembly
language into an equivalent runnable Python program. Language: Python 3.10+,
no external dependencies except pytest.

Pipeline: Lexer -> Parser -> AST -> Semantic Analyzer -> IR (basic blocks)
-> Optimizer -> Python Code Generator.

Assembly spec:
- Registers: eax, ebx, ecx, edx (case-insensitive)
- Instructions: mov, add, sub, mul, div, inc, dec, cmp, jmp, je, jne, jg, jl,
  jge, jle, push, pop, call, ret, print, hlt
- Labels: `name:` on its own line or before an instruction
- Comments start with `;`
- Operands: register, decimal or hex (0x..) immediate, or label name (jumps/call)
- cmp sets flags zf (zero) and sf (sign) from (left - right)
- div: eax = eax // operand, edx = eax % operand (before update)
- print: outputs the operand value followed by newline

Data structures live in src/asm2py/ast_nodes.py. Always import from there and
never redefine them. Use dataclasses, type hints, docstrings, and raise custom
errors that include line numbers. Keep code simple and readable. Every module
needs pytest tests in tests/.