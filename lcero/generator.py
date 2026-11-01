"""Generadores de programas L-Cero válidos para las mediciones de la Fase 7."""

from __future__ import annotations

import random


def typical_program(n_statements: int, n_vars: int = 10, seed: int = 0, max_depth: int = 3) -> str:
    """Programa "típico": pocas variables, sentencias variadas, anidamiento acotado.

    Siempre es léxica, sintáctica y semánticamente válido (todas las
    variables se declaran inicializadas al principio).
    """
    rng = random.Random(seed)
    names = [f"v{i}" for i in range(n_vars)]
    out = [f"int {v} = {i + 1};" for i, v in enumerate(names)]
    budget = [n_statements]

    def expr(depth: int = 0) -> str:
        r = rng.random()
        if depth > 2 or r < 0.35:
            return rng.choice(names) if rng.random() < 0.7 else str(rng.randint(0, 99))
        if r < 0.45:
            return f"({expr(depth + 1)})"
        if r < 0.5:
            return f"-{expr(depth + 1)}"
        op = rng.choice("+-*+-*/%")
        right = str(rng.randint(1, 9)) if op in "/%" else expr(depth + 1)
        return f"{expr(depth + 1)} {op} {right}"

    def cond() -> str:
        return f"{expr(1)} {rng.choice(['<', '<=', '>', '>=', '==', '!='])} {expr(1)}"

    def block(depth: int, indent: str) -> None:
        count = rng.randint(1, 4)
        for _ in range(count):
            if budget[0] <= 0:
                return
            stmt(depth, indent)

    def stmt(depth: int, indent: str) -> None:
        budget[0] -= 1
        r = rng.random()
        if depth < max_depth and r < 0.12:
            out.append(f"{indent}if ({cond()}) {{")
            block(depth + 1, indent + "    ")
            if rng.random() < 0.5:
                out.append(f"{indent}}} else {{")
                block(depth + 1, indent + "    ")
            out.append(f"{indent}}}")
        elif depth < max_depth and r < 0.2:
            out.append(f"{indent}while ({cond()}) {{")
            block(depth + 1, indent + "    ")
            out.append(f"{indent}}}")
        elif r < 0.3:
            out.append(f"{indent}print({expr()});")
        else:
            out.append(f"{indent}{rng.choice(names)} = {expr()};")

    while budget[0] > 0:
        stmt(0, "")
    return "\n".join(out) + "\n"


def clique_program(m: int) -> str:
    """Peor caso del optimizador: m variables vivas a la vez (interferencia = K_m).

    Se definen todas y recién después se usan todas, así que en el punto
    medio del programa las m están vivas simultáneamente.
    """
    out = [f"int v{i} = {i};" for i in range(m)]
    out += [f"print(v{i});" for i in range(m)]
    return "\n".join(out) + "\n"
