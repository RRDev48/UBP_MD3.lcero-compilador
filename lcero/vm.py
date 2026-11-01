"""Máquina virtual abstracta: máquina de registros con cinta (Fase 5).

Modelo formal. La máquina es M = (Q, k, Γ, δ, q₀, q_f) donde:

* Q = {q₀, …, q_{m−1}} ∪ {q_f}: estados de control, uno por instrucción del
  programa más el estado de parada q_f. El "programa" es la tabla de δ.
* k registros R₀ … R_{k−1}, cada uno con un entero de ℤ (sin cota).
* Una cinta infinita hacia la derecha, de celdas indexadas por ℕ, cada una
  con un entero (Γ = ℤ; el blanco es 0), y un cabezal que la recorre
  moviéndose **una celda por transición** (I = izquierda, D = derecha).
* Una cinta de salida de solo escritura (``print``).

Una configuración es C = (q, ρ, h, τ, ω): estado, contenido de los
registros, posición del cabezal, contenido de la cinta y salida emitida.
δ: C ↦ C' está definida por la instrucción asociada al estado q (ver
``Machine.delta``). En particular, ``load``/``store`` a la celda a mueven el
cabezal de a una celda hacia a y recién cuando h = a leen o escriben: el
acceso a la cinta cuesta |h − a| + 1 transiciones, como en una MT.

Conjunto de instrucciones (A y B son registros o constantes inmediatas):

    mov  Rd, A            Rd ← A
    add|sub|mul|div|mod|eq|ne|lt|le|gt|ge  Rd, A, B
    neg  Rd, A            Rd ← −A
    load Rd, [a]          Rd ← τ(a)
    store [a], A          τ(a) ← A
    jmp  q                salto incondicional
    jz   A, q             si A = 0 salta a q
    print A               ω ← ω · A
    halt                  pasa a q_f
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .arith import DivisionByZero, apply
from .errors import VMError
from .ir import TAC

HALT = -1

_BIN = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "mod",
        "==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}
_SYM = {v: k for k, v in _BIN.items()}


@dataclass(frozen=True)
class Reg:
    i: int

    def __str__(self) -> str:
        return f"R{self.i}"


@dataclass(frozen=True)
class Imm:
    v: int

    def __str__(self) -> str:
        return str(self.v)


Arg = Reg | Imm


@dataclass(frozen=True)
class Instr:
    op: str
    d: int | None = None  # registro destino
    a: Arg | None = None
    b: Arg | None = None
    addr: int | None = None  # celda de la cinta (load/store)
    target: int | None = None  # estado destino (jmp/jz)
    line: int = 0  # línea del fuente, para los errores

    def __str__(self) -> str:
        match self.op:
            case "mov" | "neg":
                return f"{self.op:<5} R{self.d}, {self.a}"
            case "load":
                return f"load  R{self.d}, [{self.addr}]"
            case "store":
                return f"store [{self.addr}], {self.a}"
            case "jmp":
                return f"jmp   q{self.target}"
            case "jz":
                return f"jz    {self.a}, q{self.target}"
            case "print":
                return f"print {self.a}"
            case "halt":
                return "halt"
        return f"{self.op:<5} R{self.d}, {self.a}, {self.b}"


def _arg(x: str | int) -> Arg:
    if isinstance(x, int):
        return Imm(x)
    assert x.startswith("R"), f"operando sin registro físico: {x}"
    return Reg(int(x[1:]))


def assemble(code: list[TAC]) -> list[Instr]:
    """Código de tres direcciones con registros físicos → programa de la máquina.

    Las etiquetas desaparecen: cada salto apunta al estado (índice) de la
    instrucción que sigue a la etiqueta.
    """
    target: dict[str, int] = {}
    count = 0
    for ins in code:
        if ins.op == "label":
            target[ins.label] = count
        else:
            count += 1
    def reg(x: str) -> int:
        return int(x[1:])

    prog: list[Instr] = []
    for ins in code:
        match ins.op:
            case "label":
                continue
            case "bin":
                prog.append(Instr(_BIN[ins.binop], reg(ins.dst), _arg(ins.a), _arg(ins.b), line=ins.line))
            case "neg":
                prog.append(Instr("neg", reg(ins.dst), _arg(ins.a), line=ins.line))
            case "copy":
                prog.append(Instr("mov", reg(ins.dst), _arg(ins.a), line=ins.line))
            case "load":
                prog.append(Instr("load", reg(ins.dst), addr=ins.slot, line=ins.line))
            case "store":
                prog.append(Instr("store", a=_arg(ins.a), addr=ins.slot, line=ins.line))
            case "goto":
                prog.append(Instr("jmp", target=target[ins.label], line=ins.line))
            case "ifz":
                prog.append(Instr("jz", a=_arg(ins.a), target=target[ins.label], line=ins.line))
            case "print":
                prog.append(Instr("print", a=_arg(ins.a), line=ins.line))
            case "halt":
                prog.append(Instr("halt", line=ins.line))
            case _:
                raise ValueError(ins.op)
    return prog


def format_program(prog: list[Instr]) -> str:
    return "\n".join(f"q{i:<4} {ins}" for i, ins in enumerate(prog))


@dataclass
class Config:
    """Configuración instantánea C = (q, ρ, h, τ, ω)."""

    q: int
    R: list[int]
    h: int = 0
    tape: dict[int, int] = field(default_factory=dict)  # soporte finito; el resto es blanco (0)
    out: list[int] = field(default_factory=list)
    steps: int = 0

    def snapshot(self) -> str:
        cells = ", ".join(f"{a}:{v}" for a, v in sorted(self.tape.items()))
        q = "q_f" if self.q == HALT else f"q{self.q}"
        return f"({q}, R={self.R}, h={self.h}, τ={{{cells}}}, ω={self.out})"


@dataclass
class RunResult:
    output: list[int]
    halted: bool
    steps: int
    config: Config


class Machine:
    def __init__(self, program: list[Instr], k: int) -> None:
        if not program or program[-1].op != "halt":
            raise ValueError("el programa debe terminar en halt")
        self.program = program
        self.k = k

    def initial(self) -> Config:
        return Config(q=0, R=[0] * self.k)

    def _val(self, c: Config, x: Arg) -> int:
        return c.R[x.i] if isinstance(x, Reg) else x.v

    def delta(self, c: Config) -> None:
        """Función de transición δ: aplica un paso a la configuración ``c``."""
        ins = self.program[c.q]
        c.steps += 1
        op = ins.op
        if op == "mov":
            c.R[ins.d] = self._val(c, ins.a)
            c.q += 1
        elif op in _SYM:
            try:
                c.R[ins.d] = apply(_SYM[op], self._val(c, ins.a), self._val(c, ins.b))
            except DivisionByZero:
                raise VMError("división por cero" if op == "div" else "resto por cero", ins.line, None) from None
            c.q += 1
        elif op == "jz":
            c.q = ins.target if self._val(c, ins.a) == 0 else c.q + 1
        elif op == "jmp":
            c.q = ins.target
        elif op == "neg":
            c.R[ins.d] = -self._val(c, ins.a)
            c.q += 1
        elif op in ("load", "store"):
            # El cabezal se mueve una celda por transición hasta la dirección pedida.
            if c.h < ins.addr:
                c.h += 1
            elif c.h > ins.addr:
                c.h -= 1
            elif op == "load":
                c.R[ins.d] = c.tape.get(c.h, 0)
                c.q += 1
            else:
                c.tape[c.h] = self._val(c, ins.a)
                c.q += 1
        elif op == "print":
            c.out.append(self._val(c, ins.a))
            c.q += 1
        elif op == "halt":
            c.q = HALT
        else:
            raise VMError(f"instrucción desconocida {op}", ins.line, None)

    def run(self, max_steps: int | None = None, trace: list[str] | None = None) -> RunResult:
        """Itera δ desde la configuración inicial hasta q_f o hasta ``max_steps``.

        Con ``max_steps`` es un *semidecisor*: si la máquina se detiene, lo
        informa; si no, solo sabemos que no lo hizo en esa cantidad de pasos.
        """
        c = self.initial()
        while c.q != HALT:
            if max_steps is not None and c.steps >= max_steps:
                return RunResult(c.out, False, c.steps, c)
            if trace is not None:
                trace.append(c.snapshot())
            self.delta(c)
        if trace is not None:
            trace.append(c.snapshot())
        return RunResult(c.out, True, c.steps, c)
