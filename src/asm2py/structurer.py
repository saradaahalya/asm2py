"""Generate structured Python from a supported subset of assembly."""

from __future__ import annotations

import keyword

from .ast_nodes import Immediate, Instruction, LabelRef, Program, Register
from .ir import BasicBlock


class CannotStructure(ValueError):
    """Raised when control flow cannot safely be translated to structured Python."""


class StructuredGenerator:
    CONDITIONS = {
        "je": "==",
        "jne": "!=",
        "jg": ">",
        "jl": "<",
        "jge": ">=",
        "jle": "<=",
    }

    def __init__(
        self, program: Program | list[BasicBlock], blocks: list[BasicBlock] | None = None
    ) -> None:
        if isinstance(program, Program):
            self.program = program
            self.blocks = blocks if blocks is not None else []
            if self.blocks:
                self.instructions, self.labels = self._flatten_blocks(self.blocks)
            else:
                self.instructions = program.instructions
                self.labels = dict(program.labels)
        else:
            self.blocks = program
            self.instructions, self.labels = self._flatten_blocks(program)
            self.program = Program(self.instructions, self.labels)

        self.block_for_instruction = {
            id(ins): block.id
            for block in self.blocks
            for ins in block.instructions
        }
        self.registers = sorted(
            {
                operand.name.lower()
                for ins in self.instructions
                for operand in ins.operands
                if isinstance(operand, Register)
            }
        )
        self._functions: dict[str, tuple[int, int]] = {}
        self._function_names: dict[str, str] = {}
        self._loop_starts: dict[int, int] = {}
        self._loop_first_names: dict[int, str] = {}

    @staticmethod
    def _flatten_blocks(
        blocks: list[BasicBlock],
    ) -> tuple[list[Instruction], dict[str, int]]:
        instructions: list[Instruction] = []
        labels: dict[str, int] = {}
        for block in blocks:
            if block.label is not None:
                labels[block.label] = len(instructions)
            for ins in block.instructions:
                if ins.label is not None:
                    labels[ins.label] = len(instructions)
                instructions.append(ins)
        return instructions, labels

    @staticmethod
    def _operand(operand: object) -> str:
        if isinstance(operand, Register):
            return operand.name.lower()
        if isinstance(operand, Immediate):
            return str(operand.value)
        if isinstance(operand, LabelRef):
            return operand.name
        raise CannotStructure(f"Unsupported operand: {operand!r}")

    @classmethod
    def _comment(cls, ins: Instruction) -> str:
        args = ", ".join(cls._operand(operand) for operand in ins.operands)
        return f"# {ins.opcode.lower()} {args}".rstrip()

    def _condition(self, jump: Instruction, compare: Instruction) -> str:
        opcode = jump.opcode.lower()
        if opcode not in self.CONDITIONS:
            raise CannotStructure(f"Unsupported conditional jump {jump.opcode!r}")
        if compare.opcode.lower() != "cmp" or len(compare.operands) != 2:
            raise CannotStructure(
                f"{jump.opcode} on line {jump.line} must immediately follow cmp"
            )
        left, right = map(self._operand, compare.operands)
        return f"{left} {self.CONDITIONS[opcode]} {right}"

    def _condition_value(
        self, jump: Instruction, compare: Instruction, known: dict[str, int | None]
    ) -> bool | None:
        values: list[int] = []
        for operand in compare.operands:
            if isinstance(operand, Immediate):
                values.append(operand.value)
            elif isinstance(operand, Register):
                value = known.get(operand.name.lower())
                if value is None:
                    return None
                values.append(value)
            else:
                return None
        left, right = values
        opcode = jump.opcode.lower()
        return {
            "je": left == right,
            "jne": left != right,
            "jg": left > right,
            "jl": left < right,
            "jge": left >= right,
            "jle": left <= right,
        }[opcode]

    def _collect_functions(self) -> None:
        calls = [
            ins for ins in self.instructions if ins.opcode.lower() == "call"
        ]
        for call in calls:
            target = call.operands[0]
            if not isinstance(target, LabelRef) or target.name not in self.labels:
                raise CannotStructure(f"Unknown call target on line {call.line}")
            if target.name in self._functions:
                continue

            start = self.labels[target.name]
            end = next(
                (
                    index
                    for index in range(start, len(self.instructions))
                    if self.instructions[index].opcode.lower() == "ret"
                ),
                None,
            )
            if end is None:
                raise CannotStructure(
                    f"Subroutine {target.name!r} called on line {call.line} has no ret"
                )
            if start > 0 and self.instructions[start - 1].opcode.lower() not in {
                "hlt",
                "jmp",
                "ret",
            }:
                raise CannotStructure(
                    f"Subroutine {target.name!r} must follow a control-flow terminator"
                )
            if any(
                self.instructions[index].opcode.lower() == "ret"
                for index in range(start, end)
            ):
                raise CannotStructure(
                    f"Subroutine {target.name!r} has a ret before its end"
                )
            self._functions[target.name] = (start, end)
            safe_name = "".join(
                character if character.isalnum() or character == "_" else "_"
                for character in target.name
            )
            function_name = f"_asm2py_{safe_name}"
            if keyword.iskeyword(function_name):
                function_name += "_"
            self._function_names[target.name] = function_name

        function_ranges = list(self._functions.items())
        for name, (start, end) in function_ranges:
            if any(
                other_start <= start < other_end or start < other_start < end
                for other_name, (other_start, other_end) in function_ranges
                if other_name != name
            ):
                raise CannotStructure("Overlapping subroutine definitions are unsupported")
            if self.instructions[end].opcode.lower() != "ret":
                raise CannotStructure(f"Subroutine {name!r} does not end with ret")

        function_indexes = {
            index
            for start, end in self._functions.values()
            for index in range(start, end + 1)
        }
        for ins in self.instructions:
            if ins.opcode.lower() not in {"jmp", *self.CONDITIONS}:
                continue
            target = ins.operands[0]
            if isinstance(target, LabelRef) and target.name in self.labels:
                if self.labels[target.name] in function_indexes:
                    raise CannotStructure(
                        f"Jump on line {ins.line} enters a subroutine; use call instead"
                    )

    def _collect_loops(self) -> None:
        for index, ins in enumerate(self.instructions):
            if ins.opcode.lower() not in self.CONDITIONS:
                continue
            target = ins.operands[0]
            if not isinstance(target, LabelRef) or target.name not in self.labels:
                raise CannotStructure(f"Unknown jump target on line {ins.line}")
            target_index = self.labels[target.name]
            if target_index <= index:
                if target_index in self._loop_starts:
                    raise CannotStructure(
                        f"Multiple loop back-edges target {target.name!r}"
                    )
                if index == 0 or self.instructions[index - 1].opcode.lower() != "cmp":
                    raise CannotStructure(
                        f"Loop jump on line {ins.line} must immediately follow cmp"
                    )
                if self.block_for_instruction and (
                    id(ins) not in self.block_for_instruction
                    or id(self.instructions[target_index]) not in self.block_for_instruction
                ):
                    raise CannotStructure(
                        f"Loop on line {ins.line} has an invalid basic-block mapping"
                    )
                self._loop_starts[target_index] = index

        intervals = sorted(
            (start, end) for start, end in self._loop_starts.items()
        )
        for index, (start, end) in enumerate(intervals):
            for other_start, other_end in intervals[index + 1 :]:
                if start < other_start <= end < other_end:
                    raise CannotStructure("Overlapping loop control-flow regions")

        used_names = set(self.registers)
        for number in range(len(self._loop_starts)):
            name = f"_asm2py_first_loop_{number}"
            while name in used_names:
                name += "_"
            self._loop_first_names[number] = name

    def _update_known(
        self, ins: Instruction, known: dict[str, int | None]
    ) -> None:
        opcode = ins.opcode.lower()
        if opcode not in {"mov", "add", "sub", "mul", "inc", "dec"}:
            return
        destination = ins.operands[0]
        if not isinstance(destination, Register):
            return
        name = destination.name.lower()
        if opcode in {"inc", "dec"}:
            current = known.get(name)
            known[name] = (
                current + (1 if opcode == "inc" else -1)
                if current is not None
                else None
            )
            return
        source = ins.operands[1]
        value = (
            source.value
            if isinstance(source, Immediate)
            else known.get(source.name.lower())
            if isinstance(source, Register)
            else None
        )
        current = known.get(name)
        if opcode == "mov":
            known[name] = value
        elif current is None or value is None:
            known[name] = None
        elif opcode == "add":
            known[name] = current + value
        elif opcode == "sub":
            known[name] = current - value
        else:
            known[name] = current * value

    def _emit_instruction(
        self, ins: Instruction, indent: int, known: dict[str, int | None]
    ) -> str | None:
        opcode = ins.opcode.lower()
        operands = [self._operand(item) for item in ins.operands]
        pad = "    " * indent
        note = f"  {self._comment(ins)}"
        if opcode == "mov":
            text = f"{operands[0]} = {operands[1]}"
        elif opcode == "add":
            text = f"{operands[0]} += {operands[1]}"
        elif opcode == "sub":
            text = f"{operands[0]} -= {operands[1]}"
        elif opcode == "mul":
            text = f"{operands[0]} *= {operands[1]}"
        elif opcode in {"inc", "dec"}:
            text = f"{operands[0]} {'+=' if opcode == 'inc' else '-='} 1"
        elif opcode == "cmp":
            self._update_known(ins, known)
            return None
        elif opcode == "print":
            text = f"print({operands[0]})"
        elif opcode == "div":
            destination, divisor = operands
            temp = f"_asm2py_divisor_{ins.line}"
            return (
                f"{pad}{temp} = {divisor}{note}\n"
                f"{pad}if {temp} == 0:\n"
                f'{pad}    raise ZeroDivisionError("division by zero (line {ins.line})")\n'
                f"{pad}edx = {destination} % {temp}\n"
                f"{pad}{destination} = {destination} // {temp}"
            )
        elif opcode == "push":
            text = f"stack.append({operands[0]})"
        elif opcode == "pop":
            text = f"{operands[0]} = stack.pop()"
        elif opcode == "call":
            target = ins.operands[0]
            if not isinstance(target, LabelRef) or target.name not in self._function_names:
                raise CannotStructure(f"Call on line {ins.line} has no structured subroutine")
            text = f"{self._function_names[target.name]}()"
        else:
            raise CannotStructure(
                f"Unsupported opcode {ins.opcode!r} on line {ins.line}"
            )
        self._update_known(ins, known)
        return f"{pad}{text}{note}"

    def _emit_sequence(
        self,
        start: int,
        end: int,
        indent: int,
        known: dict[str, int | None],
        function_ranges: dict[int, tuple[str, int]],
        in_function: bool = False,
        skip_loop_start: int | None = None,
    ) -> tuple[list[str], int]:
        output: list[str] = []
        index = start
        while index < end:
            if index in function_ranges:
                _, function_end = function_ranges[index]
                index = function_end + 1
                continue

            if index in self._loop_starts and index != skip_loop_start:
                jump_index = self._loop_starts[index]
                if jump_index >= end:
                    raise CannotStructure("Loop crosses a structured control-flow boundary")
                compare_index = jump_index - 1
                jump = self.instructions[jump_index]
                compare = self.instructions[compare_index]
                condition = self._condition(jump, compare)
                initial_condition = self._condition_value(jump, compare, known)
                body, next_index = self._emit_sequence(
                    index,
                    compare_index,
                    indent + 1,
                    known.copy(),
                    function_ranges,
                    in_function,
                    skip_loop_start=index,
                )
                if next_index != compare_index:
                    raise CannotStructure("Loop body contains an unsupported branch boundary")
                pad = "    " * indent
                if initial_condition is not True:
                    first_name = self._loop_first_names[index]
                    output.append(f"{pad}{first_name} = True")
                    output.append(f"{pad}while {first_name} or ({condition}):")
                    output.append(f"{pad}    {first_name} = False")
                    output.extend(body or [f"{pad}    pass"])
                else:
                    output.append(f"{pad}while {condition}:")
                    output.extend(body or [f"{pad}    pass"])
                for body_ins in self.instructions[index:compare_index]:
                    if body_ins.opcode.lower() in {"mov", "add", "sub", "mul", "inc", "dec"}:
                        dest = body_ins.operands[0]
                        if isinstance(dest, Register):
                            known[dest.name.lower()] = None
                index = jump_index + 1
                continue

            ins = self.instructions[index]
            opcode = ins.opcode.lower()
            if opcode in self.CONDITIONS:
                output_part, index, terminated = self._emit_forward_branch(
                    index, end, indent, known, function_ranges, in_function,
                    skip_loop_start,
                )
                output.extend(output_part)
                if terminated:
                    return output, end
                continue

            if opcode == "jmp":
                target = ins.operands[0]
                if not isinstance(target, LabelRef) or target.name not in self.labels:
                    raise CannotStructure(f"Unknown jump target on line {ins.line}")
                target_index = self.labels[target.name]
                if target_index <= index:
                    raise CannotStructure(
                        f"Backward unconditional jump on line {ins.line} "
                        "cannot be represented safely as structured control flow"
                    )
                if target_index > end:
                    raise CannotStructure(
                        f"Jump on line {ins.line} leaves its structured region"
                    )
                index = target_index
                continue

            if opcode == "hlt":
                if in_function:
                    raise CannotStructure(
                        f"hlt on line {ins.line} cannot be used inside a subroutine"
                    )
                return output, end
            if opcode == "ret":
                if not in_function:
                    raise CannotStructure(f"ret on line {ins.line} is outside a subroutine")
                return output, index

            emitted = self._emit_instruction(ins, indent, known)
            if emitted is not None:
                output.append(emitted)
            index += 1
        return output, index

    def _emit_forward_branch(
        self,
        jump_index: int,
        end: int,
        indent: int,
        known: dict[str, int | None],
        function_ranges: dict[int, tuple[str, int]],
        in_function: bool,
        skip_loop_start: int | None,
    ) -> tuple[list[str], int, bool]:
        jump = self.instructions[jump_index]
        target = jump.operands[0]
        if not isinstance(target, LabelRef) or target.name not in self.labels:
            raise CannotStructure(f"Unknown jump target on line {jump.line}")
        target_index = self.labels[target.name]
        if target_index <= jump_index or target_index > end:
            raise CannotStructure(
                f"Conditional branch on line {jump.line} has an invalid forward target"
            )
        if jump_index == 0 or self.instructions[jump_index - 1].opcode.lower() != "cmp":
            raise CannotStructure(
                f"Conditional jump on line {jump.line} must immediately follow cmp"
            )
        compare = self.instructions[jump_index - 1]
        condition = self._condition(jump, compare)
        pad = "    " * indent
        false_end = target_index - 1

        if false_end > jump_index and self.instructions[false_end].opcode.lower() == "jmp":
            false_jump = self.instructions[false_end]
            join_target = false_jump.operands[0]
            if not isinstance(join_target, LabelRef) or join_target.name not in self.labels:
                raise CannotStructure(f"Unknown join target on line {false_jump.line}")
            join_index = self.labels[join_target.name]
            if not target_index < join_index <= end:
                raise CannotStructure("Forward branch has an invalid if/else join")
            true_body, true_next = self._emit_sequence(
                target_index, join_index, indent + 1, known.copy(),
                function_ranges, in_function, skip_loop_start,
            )
            false_body, false_next = self._emit_sequence(
                jump_index + 1, false_end, indent + 1, known.copy(),
                function_ranges, in_function, skip_loop_start,
            )
            if true_next != join_index or false_next != false_end:
                raise CannotStructure("If/else branch does not reach its common join")
            output = [f"{pad}if {condition}:"]
            output.extend(true_body or [f"{pad}    pass"])
            output.append(f"{pad}else:")
            output.extend(false_body or [f"{pad}    pass"])
            self._invalidate_branch_registers(
                known, jump_index + 1, join_index
            )
            return output, join_index, False

        if false_end > jump_index and self.instructions[false_end].opcode.lower() == "hlt":
            if target_index >= end:
                raise CannotStructure("Conditional branch has no true branch body")
            true_hlt = next(
                (
                    index
                    for index in range(target_index, end)
                    if self.instructions[index].opcode.lower() == "hlt"
                ),
                None,
            )
            if true_hlt is None:
                raise CannotStructure(
                    "Conditional branch has one terminating arm and one continuing arm"
                )
            true_body, _ = self._emit_sequence(
                target_index, true_hlt, indent + 1, known.copy(),
                function_ranges, in_function, skip_loop_start,
            )
            false_body, false_next = self._emit_sequence(
                jump_index + 1, false_end, indent + 1, known.copy(),
                function_ranges, in_function, skip_loop_start,
            )
            if false_next != false_end:
                raise CannotStructure("False branch does not terminate as expected")
            output = [f"{pad}if {condition}:"]
            output.extend(true_body or [f"{pad}    pass"])
            output.append(f"{pad}else:")
            output.extend(false_body or [f"{pad}    pass"])
            self._invalidate_branch_registers(known, jump_index + 1, true_hlt)
            return output, end, True

        if any(
            self.instructions[index].opcode.lower() in {"hlt", "ret", "jmp"}
            for index in range(jump_index + 1, target_index)
        ):
            raise CannotStructure(
                f"Conditional branch on line {jump.line} has an unsupported branch shape"
            )
        false_body, false_next = self._emit_sequence(
            jump_index + 1, target_index, indent + 1, known.copy(),
            function_ranges, in_function, skip_loop_start,
        )
        if false_next != target_index:
            raise CannotStructure("Conditional branch does not reach its join")
        output = [f"{pad}if not ({condition}):"]
        output.extend(false_body or [f"{pad}    pass"])
        self._invalidate_branch_registers(known, jump_index + 1, target_index)
        return output, target_index, False

    def _invalidate_branch_registers(
        self, known: dict[str, int | None], start: int, end: int
    ) -> None:
        for ins in self.instructions[start:end]:
            if ins.opcode.lower() in {"mov", "add", "sub", "mul", "inc", "dec"}:
                destination = ins.operands[0]
                if isinstance(destination, Register):
                    known[destination.name.lower()] = None

    def generate(self) -> str:
        """Return Python code, or raise :class:`CannotStructure` for unsafe CFGs."""
        if not self.instructions:
            return "# Generated by asm2py (structured)\n"

        self._collect_functions()
        self._collect_loops()

        function_ranges = {
            start: (name, end)
            for name, (start, end) in self._functions.items()
        }
        output = ["# Generated by asm2py (structured)"]
        if self.registers:
            output.append(f"{' = '.join(self.registers)} = 0")
        if any(ins.opcode.lower() in {"push", "pop"} for ins in self.instructions):
            output.append("stack = []")

        for name, (start, end) in self._functions.items():
            function_name = self._function_names[name]
            output.append("")
            output.append(f"def {function_name}():")
            globals_used = {
                operand.name.lower()
                for ins in self.instructions[start : end + 1]
                for operand in ins.operands
                if isinstance(operand, Register)
            }
            if any(
                ins.opcode.lower() in {"push", "pop"}
                for ins in self.instructions[start : end + 1]
            ):
                globals_used.add("stack")
            if any(
                ins.opcode.lower() == "div"
                for ins in self.instructions[start : end + 1]
            ):
                globals_used.add("edx")
            output.append(
                f"    global {', '.join(sorted(globals_used))}"
                if globals_used
                else "    pass"
            )
            known = {register: None for register in self.registers}
            body, next_index = self._emit_sequence(
                start, end, 1, known, {}, in_function=True
            )
            if next_index != end:
                raise CannotStructure(
                    f"Subroutine {name!r} does not have one structured return path"
                )
            output.extend(body or ["    pass"])
            output.append("    return")

        known = {register: 0 for register in self.registers}
        body, _ = self._emit_sequence(
            0, len(self.instructions), 0, known, function_ranges
        )
        output.extend(body)
        return "\n".join(output) + "\n"
