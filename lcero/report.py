"""Exportación de los artefactos formales para el informe técnico.

Fase 1: matriz de transición δ del AFD mínimo (Markdown, CSV y LaTeX),
tabla de estados con su cadena testigo y diagrama Graphviz.
"""

from __future__ import annotations

from collections import defaultdict

from .alphabet import CLASSES, KEYWORD_LETTERS, KEYWORDS, REPRESENTATIVE
from .automata import DFA, shortest_witnesses
from .lexer import LexerAutomata
from .tokens import TokenType

_LETTERS = frozenset(KEYWORD_LETTERS) | {"LET"}
_ALL = frozenset(CLASSES)

#: Encabezados de columna legibles para la matriz.
COLUMN_LABEL = {**{c: c for c in CLASSES}, "LET": "L", "DIG": "D", "ESP": "esp", "NL": "\\n", "OTRO": "otro"}


def state_name(q: int, dfa: DFA) -> str:
    return "q∅" if q == dfa.sink else f"q{q}"


def witness_text(word: list[int]) -> str:
    s = "".join(REPRESENTATIVE[CLASSES[a]] for a in word)
    return s.replace("\n", "\\n") if s else "ε"


def state_role(q: int, m: DFA, witness: str) -> str:
    """Descripción en palabras de qué "recuerda" cada estado."""
    label = m.accepting.get(q)
    if q == m.sink:
        return "sumidero: ningún token puede continuar"
    if q == m.start:
        return "inicial"
    if label is TokenType.ID:
        kws = [k for k in KEYWORDS if k.startswith(witness) and k != witness]
        return "prefijo de " + ", ".join(f"«{k}»" for k in kws) if kws else "identificador general"
    if label in KEYWORDS.values():
        return "palabra reservada completa"
    if label is None:
        return f"prefijo incompleto («{witness}» solo no es token)"
    return "token completo"


def state_rows(auto: LexerAutomata) -> list[dict]:
    """Una fila por estado del AFD mínimo, con lo necesario para el informe."""
    m = auto.min_dfa
    wit = shortest_witnesses(m)
    rows = []
    for q in range(m.n_states):
        label = m.accepting.get(q)
        w = witness_text(wit[q])
        rows.append(
            {
                "estado": state_name(q, m),
                "testigo": "—" if q == m.sink else w,
                "token": label.name if label else "—",
                "rol": state_role(q, m, w),
                "final": label is not None,
                "agrupa": len(auto.blocks[q]),
            }
        )
    return rows


# --- Matriz δ -----------------------------------------------------------------


def delta_markdown(m: DFA) -> str:
    head = "| δ | " + " | ".join(f"`{COLUMN_LABEL[c]}`" for c in CLASSES) + " |"
    sep = "|---|" + "---|" * len(CLASSES)
    lines = [head, sep]
    for q, row in enumerate(m.trans):
        name = state_name(q, m)
        if q == m.start:
            name = "→" + name
        if q in m.accepting:
            name = "*" + name
        cells = ["·" if t == m.sink else state_name(t, m) for t in row]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def delta_csv(m: DFA) -> str:
    lines = ["estado," + ",".join(f'"{COLUMN_LABEL[c]}"' for c in CLASSES)]
    for q, row in enumerate(m.trans):
        lines.append(state_name(q, m) + "," + ",".join(state_name(t, m) for t in row))
    return "\n".join(lines) + "\n"


def delta_latex(m: DFA) -> str:
    """Tabla LaTeX (longtable) con la matriz completa; el sumidero se muestra como ·."""

    def tex(s: str) -> str:
        return (s.replace("\\", "\\textbackslash{}").replace("%", "\\%").replace("{", "\\{")
                .replace("}", "\\}").replace("_", "\\_").replace("∅", "$\\emptyset$"))

    cols = "l|" + "c" * len(CLASSES)
    head = " & ".join(["$\\delta$"] + [f"\\texttt{{{tex(COLUMN_LABEL[c])}}}" for c in CLASSES]) + " \\\\ \\hline"
    out = [f"\\begin{{longtable}}{{{cols}}}", head, "\\endhead"]
    for q, row in enumerate(m.trans):
        name = tex(state_name(q, m))
        if q == m.start:
            name = "$\\rightarrow$" + name
        if q in m.accepting:
            name = "*" + name
        cells = ["$\\cdot$" if t == m.sink else tex(state_name(t, m))[1:] for t in row]
        out.append(" & ".join([name] + cells) + " \\\\")
    out.append("\\end{longtable}")
    return "\n".join(out) + "\n"


# --- Diagrama -----------------------------------------------------------------


def compress_label(classes: set[str]) -> str:
    """Etiqueta compacta para un conjunto de clases (p. ej. «letra−{t}, dígito»)."""
    s = set(classes)
    if s == _ALL - {"NL"}:
        return "Σ−{\\\\n}"
    parts = []
    letters = s & _LETTERS
    if len(letters) > len(_LETTERS) / 2:
        missing = sorted(_LETTERS - letters)
        parts.append("letra" if not missing else "letra−{" + ",".join(missing) + "}")
        s -= letters
    if "DIG" in s:
        parts.append("dígito")
        s.discard("DIG")
    parts += [COLUMN_LABEL[c].replace("\\", "\\\\") for c in CLASSES if c in s]
    return ", ".join(parts)


def dfa_dot(m: DFA, part: str | None = None) -> str:
    """Diagrama Graphviz del AFD mínimo, sin el sumidero.

    ``part`` permite dibujar solo una parte para que sea legible:
    ``"palabras"`` (identificadores, palabras reservadas y números) u
    ``"simbolos"`` (operadores, delimitadores, comentarios y espacios).
    El estado inicial aparece en ambas.
    """
    wit = shortest_witnesses(m)
    word_classes = _LETTERS | {"DIG"}

    def in_part(q: int) -> bool:
        if q == m.sink:
            return False
        if part is None or q == m.start:
            return True
        is_word = CLASSES[wit[q][0]] in word_classes
        return is_word if part == "palabras" else not is_word

    lines = [
        "digraph AFD {",
        '  rankdir=LR; nodesep=0.22; ranksep=0.5;' if part != "simbolos" else
        '  rankdir=LR; nodesep=0.08; ranksep=2.2;',
        '  node [shape=circle, fontname="Helvetica", fontsize=12, width=0.5, fixedsize=false];' if part != "simbolos" else
        '  node [shape=circle, fontname="Helvetica", fontsize=11, width=0.98, height=0.98, fixedsize=true];',
        '  edge [fontname="Helvetica", fontsize=10, arrowsize=0.6];',
        '  inicio [shape=point, width=0.08];',
        f"  inicio -> q{m.start};",
    ]
    for q in range(m.n_states):
        if not in_part(q):
            continue
        label = m.accepting.get(q)
        if label is not None:
            lines.append(f'  q{q} [shape=doublecircle, label="q{q}\\n{label.name}"];')
        else:
            lines.append(f'  q{q} [label="q{q}"];')
    edges: dict[tuple[int, int], set[str]] = defaultdict(set)
    for q, row in enumerate(m.trans):
        for a, t in enumerate(row):
            if in_part(q) and in_part(t):
                edges[(q, t)].add(CLASSES[a])
    for (q, t), cls in sorted(edges.items()):
        lines.append(f'  q{q} -> q{t} [label="{compress_label(cls)}"];')
    lines.append("}")
    return "\n".join(lines) + "\n"
