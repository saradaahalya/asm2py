; 5! = 120
    mov eax, 1
    mov ecx, 5
loop_start:
    mul eax, ecx
    dec ecx
    cmp ecx, 0
    jg loop_start
    print eax
    hlt
