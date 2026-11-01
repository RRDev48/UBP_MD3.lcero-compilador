"""Máquinas de Turing y su traducción a L-Cero (Fases 5 y 6).

``to_lcero`` es la función computable f de la reducción del informe:

    f(⟨M, w⟩) = P_{M,w},   con   M se detiene con entrada w  ⟺  P_{M,w} termina en la VM.

La simulación codifica la cinta de M con tres enteros, como dos pilas en
base b (b = |Γ|):

* ``cur``: el símbolo bajo el cabezal;
* ``izq``: la parte a la izquierda del cabezal; su dígito menos
  significativo es la celda inmediatamente a la izquierda;
* ``der``: la parte a la derecha, con el mismo convenio.

Mover a la derecha:  izq ← izq·b + cur;  cur ← der mod b;  der ← der div b.
Mover a la izquierda: simétrico. Como los enteros de L-Cero no tienen
cota, la cinta tampoco la tiene: por eso L-Cero es Turing-completo.
"""

from __future__ import annotations

from dataclasses import dataclass

L, R, N = "L", "R", "N"


@dataclass(frozen=True)
class TuringMachine:
    """MT determinista M = (Q, Γ, b, δ, q₀, F) con Γ = {0, …, symbols−1} y blanco 0.

    ``delta[(q, s)] = (q', s', mov)``. Si no hay transición para (q, s), M se
    detiene (esto incluye los estados de parada).
    """

    name: str
    states: tuple[str, ...]
    symbols: int
    delta: dict[tuple[str, int], tuple[str, int, str]]
    start: str

    @property
    def halt_index(self) -> int:
        return len(self.states)


@dataclass
class TMRun:
    halted: bool
    steps: int
    ones: int  # celdas no blancas al final
    tape: dict[int, int]


def simulate(tm: TuringMachine, w: list[int], max_steps: int) -> TMRun:
    """Simulación directa de M (referencia para verificar la traducción)."""
    tape = {i: s for i, s in enumerate(w) if s}
    q, h, steps = tm.start, 0, 0
    while steps < max_steps:
        key = (q, tape.get(h, 0))
        if key not in tm.delta:
            return TMRun(True, steps, sum(1 for v in tape.values() if v), tape)
        q, s, mov = tm.delta[key]
        if s:
            tape[h] = s
        else:
            tape.pop(h, None)
        h += 1 if mov == R else -1 if mov == L else 0
        steps += 1
    return TMRun(False, steps, sum(1 for v in tape.values() if v), tape)


def encode_right(w: list[int], b: int) -> int:
    """w[0] es el dígito menos significativo."""
    value = 0
    for s in reversed(w):
        value = value * b + s
    return value


def to_lcero(tm: TuringMachine, w: list[int], report: bool = True) -> str:
    """Programa L-Cero que simula M con entrada w.

    Si ``report``, al detenerse imprime la cantidad de símbolos no blancos y
    de pasos (útil para verificar). La reducción no lo necesita.
    """
    b = tm.symbols
    idx = {q: i for i, q in enumerate(tm.states)}
    H = tm.halt_index
    cur = w[0] if w else 0
    der = encode_right(w[1:], b)
    out = [
        f"// Simulación de la máquina de Turing «{tm.name}» con entrada w = {''.join(map(str, w)) or 'ε'}",
        f"// Estados: {', '.join(f'{q}={i}' for q, i in idx.items())}; parada = {H}. Alfabeto de cinta: 0..{b - 1}.",
        f"int estado = {idx[tm.start]};",
        f"int cur = {cur};",
        "int izq = 0;",
        f"int der = {der};",
        "int pasos = 0;",
        f"while (estado != {H}) {{",
    ]
    for qi, q in enumerate(tm.states):
        kw = "if" if qi == 0 else "} else if"
        out.append(f"    {kw} (estado == {qi}) {{")
        for s in range(b):
            kw2 = "if" if s == 0 else "} else if"
            out.append(f"        {kw2} (cur == {s}) {{")
            if (q, s) in tm.delta:
                q2, s2, mov = tm.delta[(q, s)]
                out.append(f"            // δ({q}, {s}) = ({q2}, {s2}, {mov})")
                out.append(f"            cur = {s2};")
                if mov == R:
                    out += [f"            izq = izq * {b} + cur;", f"            cur = der % {b};", f"            der = der / {b};"]
                elif mov == L:
                    out += [f"            der = der * {b} + cur;", f"            cur = izq % {b};", f"            izq = izq / {b};"]
                out.append(f"            estado = {idx[q2] if q2 in idx else H};")
                out.append("            pasos = pasos + 1;")
            else:
                out.append(f"            estado = {H}; // sin transición: M se detiene")
        out.append("        }")
    out.append("    }")
    out.append("}")
    if report:
        out += [
            "int unos = 0;",
            "if (cur != 0) {", "    unos = 1;", "}",
            "while (izq != 0) {",
            f"    if (izq % {b} != 0) {{", "        unos = unos + 1;", "    }",
            f"    izq = izq / {b};",
            "}",
            "while (der != 0) {",
            f"    if (der % {b} != 0) {{", "        unos = unos + 1;", "    }",
            f"    der = der / {b};",
            "}",
            "print(unos);",
            "print(pasos);",
        ]
    return "\n".join(out) + "\n"


# --- Máquinas de ejemplo ------------------------------------------------------

#: Castor afanoso de 2 estados: escribe 4 unos en 6 pasos y se detiene.
BUSY_BEAVER_2 = TuringMachine(
    "castor afanoso de 2 estados", ("A", "B"), 2,
    {("A", 0): ("B", 1, R), ("A", 1): ("B", 1, L), ("B", 0): ("A", 1, L), ("B", 1): ("H", 1, R)},
    "A",
)

#: Castor afanoso de 3 estados: escribe 6 unos en 14 pasos (campeón de Σ(3)).
BUSY_BEAVER_3 = TuringMachine(
    "castor afanoso de 3 estados", ("A", "B", "C"), 2,
    {
        ("A", 0): ("B", 1, R), ("A", 1): ("H", 1, R),
        ("B", 0): ("C", 0, R), ("B", 1): ("B", 1, R),
        ("C", 0): ("C", 1, L), ("C", 1): ("A", 1, L),
    },
    "A",
)

#: Incremento binario: la entrada es un número en binario con el bit menos
#: significativo a la derecha; el cabezal arranca en el bit más significativo.
BINARY_INCREMENT = TuringMachine(
    "incremento binario", ("ir_al_final", "sumar"), 3,  # símbolos: 0 blanco, 1 = bit 0, 2 = bit 1
    {
        ("ir_al_final", 1): ("ir_al_final", 1, R),
        ("ir_al_final", 2): ("ir_al_final", 2, R),
        ("ir_al_final", 0): ("sumar", 0, L),
        ("sumar", 2): ("sumar", 1, L),  # 1 + acarreo = 0, sigue el acarreo
        ("sumar", 1): ("H", 2, N),  # 0 + acarreo = 1, termina
        ("sumar", 0): ("H", 2, N),  # desborde: nuevo bit 1 a la izquierda
    },
    "ir_al_final",
)

#: Nunca se detiene: avanza a la derecha sobre blancos para siempre.
RUNAWAY = TuringMachine("fuga a la derecha", ("A",), 2, {("A", 0): ("A", 0, R)}, "A")

#: Nunca se detiene: rebota entre dos celdas.
PING_PONG = TuringMachine(
    "ping-pong", ("A", "B"), 2, {("A", 0): ("B", 0, R), ("B", 0): ("A", 0, L)}, "A",
)
