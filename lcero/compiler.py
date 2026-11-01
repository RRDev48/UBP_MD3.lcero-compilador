"""Orquestación de todas las fases.

    fuente ─lexer─▶ tokens ─parser─▶ árbol de derivación ─▶ AST
           ─semántico─▶ AST anotado (+ avisos) ─RI─▶ código de 3 direcciones (registros virtuales)
           ─Chaitin─▶ código con k registros físicos ─ensamblador─▶ programa de la máquina
"""

from __future__ import annotations

from dataclasses import dataclass

from . import ast as A
from .ir import TAC, generate
from .lexer import Lexer
from .lint import Aviso, lint
from .parser import Parser
from .regalloc import Allocation, allocate
from .semantic import Symbol, analyze
from .tokens import Token
from .vm import Instr, Machine, RunResult, assemble

DEFAULT_REGISTERS = 4


@dataclass
class Compilation:
    tokens: list[Token]
    ast: A.Program
    symbols: list[Symbol]
    tac: list[TAC]  # RI con registros virtuales
    allocation: Allocation
    program: list[Instr]  # RI final que ejecuta la máquina
    warnings: list[Aviso]

    def machine(self) -> Machine:
        return Machine(self.program, self.allocation.k)


def compile_source(source: str, registers: int = DEFAULT_REGISTERS) -> Compilation:
    """Compila ``source``. Lanza la subclase de ``LCeroError`` de la fase que falle."""
    tokens = Lexer().tokenize(source)
    program = Parser().parse(tokens)
    symbols = analyze(program)
    warnings = lint(program)
    tac = generate(program)
    allocation = allocate(tac, registers)
    return Compilation(tokens, program, symbols, tac, allocation, assemble(allocation.physical()), warnings)


def run_source(source: str, registers: int = DEFAULT_REGISTERS, max_steps: int | None = None) -> RunResult:
    return compile_source(source, registers).machine().run(max_steps)
