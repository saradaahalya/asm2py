; first 10 Fibonacci numbers
    mov eax, 0
    mov ebx, 1
    mov ecx, 10
loop_start:
    print eax
    mov edx, eax
    add edx, ebx
    mov eax, ebx
    mov ebx, edx
    dec ecx
    cmp ecx, 0
    jg loop_start
    hlt
