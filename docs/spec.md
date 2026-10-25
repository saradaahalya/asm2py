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