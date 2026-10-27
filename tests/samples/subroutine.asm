; square routine: prints 49
    mov eax, 7
    call square
    print eax
    hlt
square:
    mul eax, eax
    ret