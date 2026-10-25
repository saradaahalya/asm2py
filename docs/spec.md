## Example

```asm
    mov ecx, 5
    mov eax, 0
loop_start:
    add eax, ecx
    dec ecx
    cmp ecx, 0
    jne loop_start
    print eax
    hlt
```

Expected output: 15

## Semantics (codegen contract)
- Two-operand instructions: destination is operand 1 (a register),
  source is operand 2 (register or immediate). add/sub/mul: dst = dst op src.
- cmp a, b: zf = (a == b); sf = (a < b). Nothing else changes.
- je: zf | jne: not zf | jg: not zf and not sf | jl: sf
  jge: not sf | jle: sf or zf
- div dst, src: edx = dst % src; dst = dst // src. Runtime error if src is 0.
- push/pop use a stack list. call pushes the return block id; ret pops it.
  ret with an empty call stack ends the program like hlt.
- Values are plain Python ints (no 32-bit wraparound).
- A label must be followed by an instruction. Duplicate labels are an error.