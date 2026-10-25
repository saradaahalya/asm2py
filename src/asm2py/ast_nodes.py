"""Abstract syntax tree nodes for the assembly language compiler."""

from dataclasses import dataclass, field
from enum import Enum, auto


class TokenType(Enum):
    """The kinds of tokens produced by the lexer."""

    INSTRUCTION = auto()
    REGISTER = auto()
    NUMBER = auto()
    IDENTIFIER = auto()
    LABEL_DEF = auto()
    COMMA = auto()
    NEWLINE = auto()
    EOF = auto()


@dataclass
class Token:
    """A lexical token and its position in the source."""

    type: TokenType
    value: str
    line: int
    column: int


class Operand:
    """Base class for operands accepted by an instruction."""


@dataclass
class Register(Operand):
    """A CPU register operand."""

    name: str


@dataclass
class Immediate(Operand):
    """An integer literal operand."""

    value: int


@dataclass
class LabelRef(Operand):
    """A reference to an instruction label."""

    name: str


@dataclass
class Instruction:
    """An assembly instruction and its source location."""

    opcode: str
    operands: list[Operand] = field(default_factory=list)
    line: int = 0
    label: str | None = None


@dataclass
class Program:
    """A complete assembly program.

    ``labels`` maps each label name to the corresponding instruction index
    in ``instructions``.
    """

    instructions: list[Instruction] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)


class AsmSyntaxError(Exception):
    """Raised when source text does not follow the assembly grammar."""

    def __init__(self, message: str, line: int) -> None:
        self.message = message
        self.line = line
        super().__init__(f"{message} (line {line})")


class AsmSemanticError(Exception):
    """Raised when syntactically valid assembly has invalid meaning."""

    def __init__(self, message: str, line: int) -> None:
        self.message = message
        self.line = line
        super().__init__(f"{message} (line {line})")
