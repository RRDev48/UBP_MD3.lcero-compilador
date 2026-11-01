"""Reducción k-COLOREO ≤p ASIGNACIÓN-DE-REGISTROS (Fase 8).

Dado un grafo G = (V, E), ``graph_to_lcero`` construye en tiempo polinomial
un programa L-Cero P_G cuyo grafo de interferencia, restringido a las
variables v_i, es exactamente G. Por lo tanto

    G es k-coloreable  ⟺  las variables de P_G caben en k registros sin derrames,

y como k-COLOREO es NP-completo para k ≥ 3 (Karp, 1972), la asignación de
registros también lo es (Chaitin et al., 1981).

Construcción: una variable ``v_i`` por vértice y una rama por arista. En la
rama de la arista {u, v} se asignan u y v y se imprime u + v: cuando se
define v, u está viva (se usa en la suma) → interfieren. Cada variable solo
vive dentro de las ramas de sus aristas, así que dos vértices no adyacentes
nunca están vivos a la vez. El análisis de vivacidad es conservador (recorre
todos los caminos del grafo de flujo sin evaluar las condiciones), así que
todas las ramas cuentan, cualquiera sea el valor del selector.
"""

from __future__ import annotations

from collections.abc import Sequence


def graph_to_lcero(n: int, edges: Sequence[tuple[int, int]], selector: int = 0) -> str:
    lines = [
        f"// P_G para un grafo con {n} vértices y {len(edges)} aristas",
        f"int sel = {selector};",
    ]
    lines += [f"int v{i};" for i in range(n)]
    for j, (u, v) in enumerate(edges):
        kw = "if" if j == 0 else "} else if"
        lines += [
            f"{kw} (sel == {j}) {{",
            f"    v{u} = {j + 1};",
            f"    v{v} = {j + 2};",
            f"    print(v{u} + v{v});",
        ]
    if edges:
        lines.append("}")
    return "\n".join(lines) + "\n"


def vertex_subgraph(graph, n: int) -> set[frozenset[int]]:
    """Aristas del grafo de interferencia entre las variables v0..v{n-1}."""
    names = {f"v{i}": i for i in range(n)}
    out = set()
    for a, b in graph.edges():
        if a in names and b in names:
            out.add(frozenset((names[a], names[b])))
    return out


# Grafos de ejemplo -------------------------------------------------------------

def cycle(n: int) -> list[tuple[int, int]]:
    return [(i, (i + 1) % n) for i in range(n)]


def complete(n: int) -> list[tuple[int, int]]:
    return [(i, j) for i in range(n) for j in range(i + 1, n)]


PETERSEN: list[tuple[int, int]] = (
    [(i, (i + 1) % 5) for i in range(5)]
    + [(i, i + 5) for i in range(5)]
    + [(5 + i, 5 + (i + 2) % 5) for i in range(5)]
)
