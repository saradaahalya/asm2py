; sum of 1..5
    mov eax, 0
    mov ecx, 1
loop_start:
    add eax, ecx
    inc ecx
    cmp ecx, 6
    jl loop_start
    print eax
    hlt
