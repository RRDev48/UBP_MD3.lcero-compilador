"""Asignación de registros por coloreo de grafos: heurística de Chaitin (Fase 8).

Entrada: código de tres direcciones con registros virtuales ilimitados.
Salida: el mismo código usando solo k registros físicos R0..R(k-1); las
variables que no entran se *derraman* a la cinta de la máquina.

Pasos (se repiten mientras haya derrames):

1. **Vivacidad** (análisis de flujo de datos hacia atrás sobre el GFC):
   in[i] = use[i] ∪ (out[i] − def[i]),   out[i] = ∪ in[s] para s ∈ succ(i).
2. **Grafo de interferencia** G = (V, E): {x, y} ∈ E si x se define en un
   punto donde y está viva (para una copia x = y no se agrega {x, y}).
3. **Simplificar:** mientras exista un nodo con grado < k, quitarlo y
   apilarlo (siempre se podrá colorear: tiene a lo sumo k−1 vecinos).
   Si todos tienen grado ≥ k, elegir para derramar el de menor
   costo/grado, con costo(v) = Σ 10^profundidad_de_bucle por cada uso o
   definición, y quitarlo.
4. **Seleccionar:** desapilar y dar a cada nodo el menor color libre.
5. **Derramar:** si hubo derrames, insertar ``load`` antes de cada uso y
   ``store`` después de cada definición, y volver a 1.

Decidir si G es k-coloreable es NP-completo (k ≥ 3); la heurística corre en
tiempo polinomial y nunca asigna mal, pero puede derramar de más. Para
comparar, ``exact_coloring`` resuelve el problema exacto por búsqueda
exhaustiva (exponencial).
"""

from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass, field, replace

from .ir import TAC

INF = float("inf")


# ---------------------------------------------------------------------------
# Vivacidad
# ---------------------------------------------------------------------------


def successors(code: list[TAC]) -> list[list[int]]:
    where = {ins.label: i for i, ins in enumerate(code) if ins.op == "label"}
    succ: list[list[int]] = []
    n = len(code)
    for i, ins in enumerate(code):
        if ins.op == "goto":
            succ.append([where[ins.label]])
        elif ins.op == "ifz":
            succ.append(([i + 1] if i + 1 < n else []) + [where[ins.label]])
        elif ins.op == "halt":
            succ.append([])
        else:
            succ.append([i + 1] if i + 1 < n else [])
    return succ


@dataclass
class Liveness:
    live_in: list[set[str]]
    live_out: list[set[str]]
    iterations: int  # instrucciones procesadas por el algoritmo de lista de trabajo


def liveness(code: list[TAC]) -> Liveness:
    """Vivacidad por instrucción con lista de trabajo (punto fijo)."""
    n = len(code)
    succ = successors(code)
    pred: list[list[int]] = [[] for _ in range(n)]
    for i, ss in enumerate(succ):
        for s in ss:
            pred[s].append(i)
    uses = [set(ins.uses()) for ins in code]
    defs = [set(ins.defs()) for ins in code]
    live_in: list[set[str]] = [set() for _ in range(n)]
    live_out: list[set[str]] = [set() for _ in range(n)]

    work = deque(range(n - 1, -1, -1))
    queued = [True] * n
    processed = 0
    while work:
        i = work.popleft()
        queued[i] = False
        processed += 1
        out: set[str] = set()
        for s in succ[i]:
            out |= live_in[s]
        live_out[i] = out
        new_in = uses[i] | (out - defs[i])
        if new_in != live_in[i]:
            live_in[i] = new_in
            for p in pred[i]:
                if not queued[p]:
                    queued[p] = True
                    work.append(p)
    return Liveness(live_in, live_out, processed)


# ---------------------------------------------------------------------------
# Grafo de interferencia
# ---------------------------------------------------------------------------


@dataclass
class InterferenceGraph:
    names: list[str]  # nodo i ↔ names[i] (orden de primera aparición: determinista)
    index: dict[str, int]
    adj: list[set[int]]

    @property
    def n_edges(self) -> int:
        return sum(len(a) for a in self.adj) // 2

    def edges(self) -> list[tuple[str, str]]:
        return [(self.names[u], self.names[v]) for u in range(len(self.adj)) for v in sorted(self.adj[u]) if u < v]

    def neighbors(self, name: str) -> set[str]:
        return {self.names[v] for v in self.adj[self.index[name]]}


def interference_graph(code: list[TAC], live: Liveness) -> InterferenceGraph:
    names: list[str] = []
    index: dict[str, int] = {}
    for ins in code:
        for x in ins.defs() + ins.uses():
            if x not in index:
                index[x] = len(names)
                names.append(x)
    adj: list[set[int]] = [set() for _ in names]
    for i, ins in enumerate(code):
        for d in ins.defs():
            u = index[d]
            for v_name in live.live_out[i]:
                if v_name == d or (ins.op == "copy" and v_name == ins.a):
                    continue
                v = index[v_name]
                adj[u].add(v)
                adj[v].add(u)
    return InterferenceGraph(names, index, adj)


# ---------------------------------------------------------------------------
# Coloreo: heurística de Chaitin
# ---------------------------------------------------------------------------


def spill_costs(code: list[TAC], g: InterferenceGraph) -> list[float]:
    """Costo de derrame de Chaitin: Σ 10^profundidad por cada uso o definición.

    Costo infinito (no derramable) para los nombres cuyo rango vivo ya es
    mínimo: una única definición seguida inmediatamente de su único uso, y
    los temporales de derrame ``$s``. Derramarlos crearía otro temporal con
    el mismo rango vivo, sin bajar la presión de registros.
    """
    cost = [0.0] * len(g.names)
    where: list[list[int]] = [[] for _ in g.names]
    for i, ins in enumerate(code):
        w = 10.0 ** ins.depth
        for x in ins.uses() + ins.defs():
            cost[g.index[x]] += w
            where[g.index[x]].append(i)
    for v, name in enumerate(g.names):
        pos = where[v]
        if name.startswith("$s") or (len(pos) == 2 and pos[1] == pos[0] + 1 and code[pos[0]].dst == name):
            cost[v] = INF
    return cost


@dataclass
class ColoringResult:
    colors: dict[int, int]  # nodo -> color (vacío si hubo derrames)
    spilled: list[int]  # nodos elegidos para derramar
    order: list[int]  # orden de simplificación (pila)


def chaitin_color(g: InterferenceGraph, k: int, cost: list[float]) -> ColoringResult:
    """Simplificar + seleccionar. Costo O((V + E)·log V).

    Los candidatos a derrame están en un montículo ordenado por costo/grado.
    Como los grados solo bajan, la clave de un nodo solo sube: una entrada
    vieja tiene clave menor o igual a la real, así que al sacarla se compara
    con la clave actual y, si cambió, se reinserta (actualización perezosa).
    Cada arista provoca a lo sumo una reinserción.
    """
    n = len(g.names)
    degree = [len(a) for a in g.adj]
    removed = [False] * n
    low = [v for v in range(n - 1, -1, -1) if degree[v] < k]  # pila de candidatos de grado < k
    in_low = [degree[v] < k for v in range(n)]
    stack: list[int] = []
    spilled: list[int] = []
    remaining = n
    heap = [(cost[v] / degree[v] if degree[v] else INF, v) for v in range(n)]
    heapq.heapify(heap)

    def remove(v: int) -> None:
        nonlocal remaining
        removed[v] = True
        remaining -= 1
        for u in g.adj[v]:
            if not removed[u]:
                degree[u] -= 1
                if degree[u] < k and not in_low[u]:
                    in_low[u] = True
                    low.append(u)

    while remaining:
        while low and removed[low[-1]]:
            low.pop()
        if low:
            v = low.pop()
            stack.append(v)
            remove(v)
            continue
        # Bloqueado: todos los nodos restantes tienen grado ≥ k > 0.
        # Se derrama el de menor costo/grado.
        while True:
            key, v = heapq.heappop(heap)
            if removed[v]:
                continue
            current = cost[v] / degree[v]
            if current != key:
                heapq.heappush(heap, (current, v))
                continue
            break
        if cost[v] == INF:
            raise RuntimeError(f"no se puede asignar con k={k}: solo quedan temporales de derrame")
        spilled.append(v)
        remove(v)

    if spilled:
        return ColoringResult({}, spilled, stack)

    colors: dict[int, int] = {}
    for v in reversed(stack):
        taken = {colors[u] for u in g.adj[v] if u in colors}
        colors[v] = next(c for c in range(k) if c not in taken)
    return ColoringResult(colors, [], stack)


def exact_coloring(adj: list[set[int]], k: int, budget: int | None = None) -> tuple[dict[int, int] | None, int]:
    """¿Es el grafo k-coloreable? Búsqueda exhaustiva con vuelta atrás.

    Devuelve (coloreo o None, nodos explorados). En el peor caso explora
    O(k^|V|) asignaciones: es la alternativa que la heurística evita.
    """
    n = len(adj)
    order = sorted(range(n), key=lambda v: -len(adj[v]))
    colors: dict[int, int] = {}
    explored = 0

    def bt(i: int) -> bool:
        nonlocal explored
        if i == n:
            return True
        explored += 1
        if budget is not None and explored > budget:
            raise TimeoutError
        v = order[i]
        taken = {colors[u] for u in adj[v] if u in colors}
        for c in range(k):
            if c not in taken:
                colors[v] = c
                if bt(i + 1):
                    return True
                del colors[v]
        return False

    return (dict(colors) if bt(0) else None), explored


# ---------------------------------------------------------------------------
# Código de derrame y bucle principal
# ---------------------------------------------------------------------------


def insert_spill_code(code: list[TAC], slots: dict[str, int], counter: list[int]) -> list[TAC]:
    out: list[TAC] = []

    def fresh() -> str:
        counter[0] += 1
        return f"$s{counter[0]}"

    for ins in code:
        loaded: dict[str, str] = {}
        new = replace(ins)
        for field_name in ("a", "b"):
            x = getattr(ins, field_name)
            if isinstance(x, str) and x in slots:
                if x not in loaded:
                    loaded[x] = fresh()
                    out.append(TAC("load", dst=loaded[x], slot=slots[x], line=ins.line, depth=ins.depth))
                setattr(new, field_name, loaded[x])
        post = None
        if ins.dst is not None and ins.dst in slots:
            t = fresh()
            post = TAC("store", a=t, slot=slots[ins.dst], line=ins.line, depth=ins.depth)
            new.dst = t
        out.append(new)
        if post is not None:
            out.append(post)
    return out


@dataclass
class RoundStats:
    instructions: int
    nodes: int
    edges: int
    max_degree: int
    spilled: list[str]
    liveness_work: int


@dataclass
class Allocation:
    k: int
    code: list[TAC]  # código final con nombres virtuales (incluye derrames)
    graph: InterferenceGraph  # grafo de la última ronda
    register: dict[str, int]  # nombre virtual -> registro físico
    slots: dict[str, int]  # variable derramada -> celda de la cinta
    rounds: list[RoundStats] = field(default_factory=list)

    def physical(self) -> list[TAC]:
        """Código con registros físicos ``R0..R(k-1)``; elimina copias Ri = Ri."""
        out = []
        for ins in self.code:
            new = replace(ins)
            for f in ("dst", "a", "b"):
                x = getattr(ins, f)
                if isinstance(x, str):
                    setattr(new, f, f"R{self.register[x]}")
            if new.op == "copy" and new.dst == new.a:
                continue
            out.append(new)
        return out


def allocate(code: list[TAC], k: int) -> Allocation:
    if k < 2:
        raise ValueError("se necesitan al menos 2 registros (una instrucción lee dos operandos)")
    slots: dict[str, int] = {}
    counter = [0]
    rounds: list[RoundStats] = []
    while True:
        live = liveness(code)
        g = interference_graph(code, live)
        result = chaitin_color(g, k, spill_costs(code, g))
        rounds.append(RoundStats(
            len(code), len(g.names), g.n_edges, max((len(a) for a in g.adj), default=0),
            [g.names[v] for v in result.spilled], live.iterations,
        ))
        if not result.spilled:
            register = {g.names[v]: c for v, c in result.colors.items()}
            return Allocation(k, code, g, register, slots, rounds)
        for v in result.spilled:
            slots[g.names[v]] = len(slots)
        code = insert_spill_code(code, {g.names[v]: slots[g.names[v]] for v in result.spilled}, counter)
