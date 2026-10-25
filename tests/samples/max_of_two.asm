; max of two numbers
    mov eax, 7
    mov ebx, 12
    cmp eax, ebx
    jge eax_bigger
    print ebx
    hlt
eax_bigger:
    print eax
    hlt
