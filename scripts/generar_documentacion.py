"""Regenera los artefactos formales del informe a partir del código.

Uso:  python scripts/generar_documentacion.py

Escribe:
  docs/generado/            Markdown, CSV y diagramas (para leer en el repositorio)
  docs/informe/generado/    fragmentos LaTeX y textos que \\input-ea el informe

Ningún número ni tabla del informe se escribe a mano: todo sale de acá.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from lcero import report  # noqa: E402
from lcero.alphabet import CLASS_DESCRIPTION, CLASSES  # noqa: E402
from lcero.compiler import compile_source  # noqa: E402
from lcero.grammar import END, EPSILON  # noqa: E402
from lcero.ir import format_tac  # noqa: E402
from lcero.lcero_grammar import lcero_grammar  # noqa: E402
from lcero.lexer import lexer_automata, tokenize  # noqa: E402
from lcero.lexer_spec import TOKEN_SPECS  # noqa: E402
from lcero.parser import Parser, TraceRow  # noqa: E402
from lcero.reductions import PETERSEN, graph_to_lcero, vertex_subgraph  # noqa: E402
from lcero.regalloc import exact_coloring, interference_graph, liveness  # noqa: E402
from lcero.vm import format_program  # noqa: E402
from programas_util import programs  # noqa: E402

OUT_MD = ROOT / "docs" / "generado"
OUT_TEX = ROOT / "docs" / "informe" / "generado"
NUMBERS: dict[str, object] = {}
HAS_DOT = shutil.which("dot") is not None

# Paleta de referencia (slots categóricos) para colorear grafos.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]


# --- utilidades LaTeX -----------------------------------------------------------


def tex(s: str) -> str:
    out = []
    for ch in s:
        out.append({
            "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "_": r"\_", "%": r"\%", "#": r"\#",
            "&": r"\&", "$": r"\$", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
        }.get(ch, ch))
    return "".join(out)


def sym(x: str) -> str:
    """Símbolo de la gramática: no terminal en cursiva, terminal en monoespaciado."""
    g = lcero_grammar()
    if x == EPSILON:
        return r"$\varepsilon$"
    if x == END:
        return r"\tm{\$}"
    if x in g.by_lhs:
        return rf"\nt{{{x}}}"
    return rf"\tm{{{tex(x)}}}"


def symset(s, sort_key=None) -> str:
    g = lcero_grammar()
    order = {t: i for i, t in enumerate(g.terminals)}
    items = sorted(s, key=lambda x: (x == EPSILON, order.get(x, -1)))
    return r"$\{$" + ", ".join(sym(x) for x in items) + r"$\}$"


def dot(*args: str) -> None:
    """Renderiza con Graphviz; sin `dot` en el PATH se conservan los diagramas existentes."""
    if HAS_DOT:
        subprocess.run(["dot", *args], check=True)


def write(name: str, text: str) -> None:
    (OUT_TEX / name).write_text(text, encoding="utf-8")


def number(name: str, value) -> None:
    NUMBERS[name] = value


# --- Fase 1 -------------------------------------------------------------------------


def fase1() -> None:
    auto = lexer_automata()
    m = auto.min_dfa
    rows = report.state_rows(auto)
    number("NAFN", auto.nfa.n_states)
    number("NAFD", auto.dfa.n_states)
    number("NMin", m.n_states)
    number("NFinales", len(m.accepting))
    number("NClases", len(CLASSES))
    number("NTokens", len(TOKEN_SPECS))
    number("NCeldasDelta", m.n_states * len(CLASSES))
    number("AgrupaIdent", rows[2]["agrupa"])
    number("AgrupaComent", rows[27]["agrupa"])
    assert rows[2]["rol"] == "identificador general" and rows[27]["token"] == "COMMENT"
    # Hechos sobre la matriz que usa la demostración de linealidad del lexer (Teorema 9.1).
    nonfinal = [q for q in range(m.n_states) if q not in m.accepting]
    assert nonfinal == [m.start, 13, m.sink], nonfinal
    assert not any(m.start in row for row in m.trans), "ninguna transición entra a q0"
    assert [q for q, row in enumerate(m.trans) if 13 in row] == [m.start], "a q13 solo se llega desde q0"

    # Markdown y CSV para el repositorio
    OUT_MD.mkdir(parents=True, exist_ok=True)
    (OUT_MD / "afd_minimo_delta.csv").write_text(report.delta_csv(m), encoding="utf-8")
    (OUT_MD / "afd_minimo.dot").write_text(report.dfa_dot(m), encoding="utf-8")
    md = [
        "# Fase 1 — Artefactos generados del AFD mínimo", "",
        "> Archivo generado por `scripts/generar_documentacion.py`. No editar a mano.", "",
        "| Autómata | Estados |", "|---|---|",
        f"| AFN-ε (Thompson) | {auto.nfa.n_states} |", f"| AFD (subconjuntos) | {auto.dfa.n_states} |",
        f"| AFD mínimo (Hopcroft) | {m.n_states} |", "",
        "## Estados del AFD mínimo", "",
        "| Estado | Testigo | λ | Rol | Agrupa |", "|---|---|---|---|---|",
        *[f"| {r['estado']} | `{r['testigo']}` | {r['token']} | {r['rol']} | {r['agrupa']} |" for r in rows],
        "", "## Matriz de transición δ", "", "`→` inicial · `*` final · `·` sumidero.", "",
        report.delta_markdown(m), "",
    ]
    (OUT_MD / "fase1_afd_minimo.md").write_text("\n".join(md), encoding="utf-8")
    for fmt in ("svg", "png", "pdf"):
        dot(f"-T{fmt}", "-Gdpi=150", str(OUT_MD / "afd_minimo.dot"), "-o", str(OUT_MD / f"afd_minimo.{fmt}"))
    for part in ("palabras", "simbolos"):
        path = OUT_TEX / f"afd_{part}.dot"
        path.write_text(report.dfa_dot(m, part), encoding="utf-8")
        dot("-Tpdf", str(path), "-o", str(OUT_TEX / f"afd_{part}.pdf"))
        dot("-Tpng", "-Gdpi=110", str(path), "-o", str(OUT_MD / f"afd_{part}.png"))

    # Clases de caracteres
    write("f1_clases.tex", "\n".join(
        rf"\texttt{{{tex(report.COLUMN_LABEL[c])}}} & {tex(CLASS_DESCRIPTION[c])} \\" for c in CLASSES) + "\n")

    # Expresiones regulares
    def er(s: str) -> str:
        s = tex(s)
        s = s.replace("letra", r"\textit{letra}").replace("dígito", r"\textit{dígito}")
        s = s.replace("Σ − \\{\\textbackslash{}n\\}", r"$(\Sigma - \{\backslash n\})$")
        s = s.replace("*", r"$^{*}$").replace("|", r"$\mid$")
        return s

    lines = []
    for i, spec in enumerate(TOKEN_SPECS):
        e = spec.er
        if spec.type.name == "COMMENT":
            body = r"\texttt{//}\,$(\Sigma - \{\backslash\texttt{n}\})^{*}$"
        elif spec.type.name == "WS":
            body = r"$(\textit{esp} \mid \backslash\texttt{n})(\textit{esp} \mid \backslash\texttt{n})^{*}$"
        elif spec.type.name == "ID":
            body = r"$\textit{letra}\,(\textit{letra} \mid \textit{dígito})^{*}$"
        elif spec.type.name == "NUM":
            body = r"$\textit{dígito}\,\textit{dígito}^{*}$"
        else:
            body = rf"\texttt{{{tex(e)}}}"
        name = {"COMMENT": "\\textit{comentario}", "WS": "\\textit{espacio}"}.get(spec.type.name, rf"\texttt{{{spec.type.name}}}")
        lines.append(rf"{i} & {name} & {body} \\")
    write("f1_er.tex", "\n".join(lines) + "\n")

    # Estados
    def wit(w: str) -> str:
        return r"$\varepsilon$" if w == "ε" else ("---" if w == "—" else rf"\texttt{{{tex(w)}}}")

    def st(name: str) -> str:
        return r"$q_\emptyset$" if name == "q∅" else rf"$q_{{{name[1:]}}}$"

    def rol(texto: str) -> str:
        # Las palabras entre «» van en monoespaciado. (Fuera del f-string: Python < 3.12
        # no admite barras invertidas dentro de las expresiones de un f-string.)
        return tex(texto).replace("«", "«" + "\\texttt{").replace("»", "}»")

    write("f1_estados.tex", "\n".join(
        rf"{st(r['estado'])} & {wit(r['testigo'])} & {tex(r['token']) if r['token'] != '—' else '---'} & "
        rf"{rol(r['rol'])} & {r['agrupa']} \\"
        for r in rows) + "\n")

    # Matriz δ (longtable apaisada)
    head = " & ".join([r"$\delta$"] + [rf"\texttt{{{tex(report.COLUMN_LABEL[c])}}}" for c in CLASSES])
    out = [rf"\begin{{longtable}}{{@{{}}l|*{{{len(CLASSES)}}}{{c}}@{{}}}}",
           r"\toprule", head + r" \\", r"\midrule", r"\endhead",
           r"\bottomrule", r"\endfoot"]
    for q, row in enumerate(m.trans):
        name = st(report.state_name(q, m))
        if q == m.start:
            name = r"$\rightarrow$" + name
        if q in m.accepting:
            name = r"$\ast$" + name
        cells = [r"$\cdot$" if t == m.sink else str(t) for t in row]
        out.append(" & ".join([name] + cells) + r" \\")
    out.append(r"\end{longtable}")
    write("f1_delta.tex", "\n".join(out) + "\n")


# --- Fase 2 -------------------------------------------------------------------------


def fase2() -> None:
    g = lcero_grammar()
    table, conflicts = g.ll1_table()
    assert not conflicts
    number("NProd", len(g.productions))
    number("NNoTerm", len(g.nonterminals))
    number("NTerm", len(g.terminals))
    number("NCeldasLL", len(table))
    number("NAnulables", len(g.nullable))
    number("NConAlternativas", sum(1 for A in g.nonterminals if len(g.by_lhs[A]) > 1))

    def rhs(p):
        return " ".join(sym(x) for x in p.rhs) if p.rhs else r"$\varepsilon$"

    # Versión compacta de la gramática: una fila por no terminal, alternativas con su número.
    lines = []
    for A in g.nonterminals:
        alts = [rf"{rhs(p)}\,{{\scriptsize({p.index})}}" for p in g.by_lhs[A]]
        lines.append(rf"{sym(A)} & $\rightarrow$ & " + r" $\mid$ ".join(alts) + r" \\")
    write("f2_gramatica_compacta.tex", "\n".join(lines) + "\n")

    # Predict compacto: solo los no terminales con alternativas, una fila cada uno.
    lines = []
    for A in g.nonterminals:
        prods = g.by_lhs[A]
        if len(prods) < 2:
            continue
        parts = [rf"({p.index})\,{symset(g.predict(p))}" for p in prods]
        lines.append(rf"{sym(A)} & " + r"\quad ".join(parts) + r" \\")
    write("f2_predict_compacto.tex", "\n".join(lines) + "\n")

    write("f2_producciones.tex", "\n".join(
        rf"({p.index}) & {sym(p.lhs)} & $\rightarrow$ & {rhs(p)} \\" for p in g.productions) + "\n")

    write("f2_first_follow.tex", "\n".join(
        rf"{sym(A)} & {'sí' if A in g.nullable else 'no'} & {symset(g.first[A])} & {symset(g.follow[A])} \\"
        for A in g.nonterminals) + "\n")

    # Cálculo explícito de First: First(A) = ∪ First(α) por cada A → α
    lines = []
    for A in g.nonterminals:
        prods = g.by_lhs[A]
        for i, p in enumerate(prods):
            lead = sym(A) if i == 0 else ""
            lines.append(rf"{lead} & ({p.index}) {rhs(p)} & {symset(g.first_of(p.rhs))} \\")
        lines.append(r"\midrule")
    write("f2_first_calculo.tex", "\n".join(lines[:-1]) + "\n")

    # Cálculo explícito de Follow: cada regla aplicada
    lines = []
    rules = g.follow_rules()
    for B in g.nonterminals:
        contrib = []
        if B == g.start:
            contrib.append(r"regla 1 ($B$ es el símbolo inicial) & \{\tm{\$}\}")
        for c in rules:
            if c.target != B:
                continue
            if c.kind == "first":
                contrib.append(rf"({c.production.index}) regla 2: $\mathrm{{First}}(\beta)-\{{\varepsilon\}}$ & {symset(c.symbols)}")
            else:
                contrib.append(rf"({c.production.index}) regla 3: $\beta \Rightarrow^{{*}} \varepsilon$ & $\mathrm{{Follow}}$({sym(c.production.lhs)})")
        for i, c in enumerate(contrib):
            lines.append(rf"{sym(B) if i == 0 else ''} & {c} \\")
        lines.append(rf" & \textbf{{resultado}} & \textbf{{{symset(g.follow[B])}}} \\")
        lines.append(r"\midrule")
    write("f2_follow_calculo.tex", "\n".join(lines[:-1]) + "\n")

    # Predict y condición LL(1)
    lines = []
    for A in g.nonterminals:
        prods = g.by_lhs[A]
        if len(prods) < 2:
            continue
        for i, p in enumerate(prods):
            lead = sym(A) if i == 0 else ""
            lines.append(rf"{lead} & ({p.index}) {rhs(p)} & {symset(g.predict(p))} \\")
        lines.append(rf" & \multicolumn{{2}}{{l}}{{\textit{{disjuntos dos a dos}} \checkmark}} \\")
        lines.append(r"\midrule")
    write("f2_predict.tex", "\n".join(lines[:-1]) + "\n")

    # Tabla LL(1)
    terms = list(g.terminals)
    head = " & ".join([""] + [rf"\rotatebox{{90}}{{{sym(t)}}}" for t in terms])
    out = [rf"\begin{{tabular}}{{@{{}}l|*{{{len(terms)}}}{{c}}@{{}}}}", r"\toprule", head + r" \\", r"\midrule"]
    for A in g.nonterminals:
        cells = [str(table[(A, t)].index) if (A, t) in table else "" for t in terms]
        out.append(" & ".join([sym(A)] + cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}"]
    write("f2_tabla_ll1.tex", "\n".join(out) + "\n")

    # Traza del autómata de pila
    sample = "x = a * 2;"
    trace: list[TraceRow] = []
    Parser().parse_tree(tokenize(sample), trace)
    number("TrazaPasos", len(trace))
    write("f2_traza_fuente.tex", rf"\texttt{{{tex(sample)}}}")

    def seq(s: str) -> str:
        return " ".join(sym(x) for x in s.split())

    lines = []
    for i, r in enumerate(trace):
        act = r.action
        mt = re.match(r"\((\d+)\) (.*)", act)
        if mt:
            p = g.productions[int(mt.group(1)) - 1]
            act = rf"({p.index}) {sym(p.lhs)} $\rightarrow$ {rhs(p)}"
        elif act.startswith("emparejar"):
            act = "emparejar " + sym(act.split()[1])
        lines.append(rf"{i + 1} & {seq(r.stack)} & {seq(r.input)} & {act} \\")
    write("f2_traza.tex", "\n".join(lines) + "\n")


# --- Fases 4, 5 y 8 -------------------------------------------------------------------


def programa(nombre: str) -> str:
    return (ROOT / "tests" / "programas" / "validos" / f"{nombre}.l0").read_text(encoding="utf-8")


def fases_4_5_8() -> None:
    src = programa("factorial")
    c4 = compile_source(src, 4)
    c2 = compile_source(src, 2)
    write("factorial_ri.txt", format_tac(c4.tac) + "\n")
    write("factorial_k4_maquina.txt", format_program(c4.program) + "\n")
    write("factorial_k2_fisico.txt", format_tac(c2.allocation.code) + "\n")
    write("factorial_k2_maquina.txt", format_program(c2.program) + "\n")
    number("FactorialSlots", ", ".join(c2.allocation.slots))

    # Traza con movimiento del cabezal
    trace_src = "int a = 7;\nint b = 5;\nint c = 2;\nprint(a * b - c);\nprint(a + b + c);\n"
    ct = compile_source(trace_src, 2)
    write("traza_fuente.txt", trace_src)
    write("traza_maquina.txt", format_program(ct.program) + "\n")
    trace: list[str] = []
    r = ct.machine().run(trace=trace)
    number("TrazaVMPasos", r.steps)
    write("traza_configuraciones.txt", "\n".join(f"C{i:<3} {t}" for i, t in enumerate(trace)) + "\n")

    # Resultados de la asignación por programa
    lines = []
    for p in programs("validos"):
        c = compile_source(p.source, 4)
        g = c.allocation.rounds[0]
        cells = []
        for k in (2, 3, 4):
            ck = compile_source(p.source, k)
            spills = [n for n in ck.allocation.slots]
            cells.append(str(len(spills)) + (f" ({len(ck.allocation.rounds)})" if len(ck.allocation.rounds) > 1 else ""))
        lines.append(rf"\texttt{{{tex(p.path.stem)}}} & {len(c.tac)} & {g.nodes} & {g.edges} & {g.max_degree} & "
                     + " & ".join(cells) + r" \\")
    write("f8_resultados.tex", "\n".join(lines) + "\n")

    # Grafo de interferencia coloreado de fibonacci con k = 3
    cf = compile_source(programa("fibonacci"), 3)
    alloc = cf.allocation
    write("fibonacci_k3_fisico.txt", format_tac(alloc.physical()) + "\n")
    number("FibSlots", ", ".join(alloc.slots))
    dot_graph(alloc.graph, alloc.register, "fibonacci_k3_interferencia", spilled_note=alloc.slots)

    # Grafo de interferencia del primer intento (antes de derramar)
    c16 = compile_source(programa("fibonacci"), 16)
    dot_graph(c16.allocation.graph, c16.allocation.register, "fibonacci_k16_interferencia")
    number("FibNodos", c16.allocation.rounds[0].nodes)
    number("FibAristas", c16.allocation.rounds[0].edges)

    # Reducción: P_G para el grafo de Petersen
    n = 10
    src_pg = graph_to_lcero(n, PETERSEN)
    write("petersen_pg.txt", src_pg)
    cpg = compile_source(src_pg, 3)
    code = cpg.tac
    full = interference_graph(code, liveness(code))
    assert vertex_subgraph(full, n) == {frozenset(e) for e in PETERSEN}
    # Componentes del resto del grafo (no vértices): deben ser bipartitos y disjuntos de G
    others = [v for v, name in enumerate(full.names) if not re.fullmatch(r"v\d+", name)]
    touching = any(full.names[u].startswith("v") and re.fullmatch(r"v\d+", full.names[u])
                   for v in others for u in full.adj[v])
    assert not touching
    # El resto del grafo (selector y temporales) es 2-coloreable: χ(G(P_G)) = max(χ(G), 2).
    idx = {v: i for i, v in enumerate(others)}
    sub = [{idx[u] for u in full.adj[v] if u in idx} for v in others]
    assert exact_coloring(sub, 2)[0] is not None
    number("PGOtrosNodos", len(others))
    number("PGOtrasAristas", sum(len(a) for a in sub) // 2)
    number("PGSpillsChaitin", ", ".join(cpg.allocation.slots) or "ninguno")
    adj = [set() for _ in range(n)]
    for u, v in PETERSEN:
        adj[u].add(v)
        adj[v].add(u)
    colors, explored = exact_coloring(adj, 3)
    number("PetersenExplorados", explored)
    dot_petersen(colors)


def dot_graph(graph, register: dict[str, int], name: str, spilled_note=None) -> None:
    lines = ["graph G {", '  layout=neato; overlap=false; sep="+18"; splines=true;',
             '  node [shape=circle, style=filled, fontname="Helvetica", fontsize=15, fontcolor=white, width=0.75, fixedsize=true, color=white, penwidth=2];',
             '  edge [color="#9a9893", penwidth=1.4];']
    for i, n in enumerate(graph.names):
        reg = register.get(n)
        fill = PALETTE[reg % len(PALETTE)] if reg is not None else "#c3c2b7"
        label = n.replace("$", "")
        lines.append(f'  n{i} [label="{label}\\nR{reg}", fillcolor="{fill}"];')
    for u, v in graph.edges():
        lines.append(f"  n{graph.index[u]} -- n{graph.index[v]};")
    lines.append("}")
    path = OUT_TEX / f"{name}.dot"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    dot("-Kneato", "-Tpdf", str(path), "-o", str(OUT_TEX / f"{name}.pdf"))
    dot("-Kneato", "-Tpng", "-Gdpi=150", str(path), "-o", str(OUT_MD / f"{name}.png"))


def dot_petersen(colors: dict[int, int]) -> None:
    import math
    lines = ["graph P {", "  layout=neato;",
             '  node [shape=circle, style=filled, fontname="Helvetica", fontsize=11, fontcolor=white, width=0.45, fixedsize=true, color=white, penwidth=2];',
             '  edge [color="#52514e", penwidth=1.3];']
    for i in range(10):
        r = 2.0 if i < 5 else 1.0
        a = math.pi / 2 + 2 * math.pi * (i % 5) / 5
        lines.append(f'  v{i} [label="v{i}", pos="{r * math.cos(a):.3f},{r * math.sin(a):.3f}!", fillcolor="{PALETTE[colors[i]]}"];')
    for u, v in PETERSEN:
        lines.append(f"  v{u} -- v{v};")
    lines.append("}")
    path = OUT_TEX / "petersen.dot"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    dot("-Kneato", "-Tpdf", str(path), "-o", str(OUT_TEX / "petersen.pdf"))
    dot("-Kneato", "-Tpng", "-Gdpi=150", str(path), "-o", str(OUT_MD / "petersen.png"))


# --- Fase 7 -------------------------------------------------------------------------


def fase7() -> None:
    import csv
    ajustes = OUT_MD / "profiling_ajustes.csv"
    if not ajustes.exists():
        print("Fase 7: falta docs/generado/profiling_ajustes.csv (correr scripts/profiling.py)")
        return
    with ajustes.open(encoding="utf-8") as f:
        fits = {r["serie"]: r for r in csv.DictReader(f)}
    for key, macro in (("lexer", "Lexer"), ("parser", "Parser"), ("optimizador_tipico", "OptTipico"),
                       ("optimizador_peor", "OptPeor"), ("optimizador_trabajo", "OptTrabajo"),
                       ("parser_pasos", "ParserPasos")):
        if key in fits:
            number(f"Pend{macro}", f"{float(fits[key]['pendiente_loglog']):.2f}")
            number(f"Rdos{macro}", f"{float(fits[key]['r2']):.4f}")
    if "parser_pasos" in fits:
        number("PasosPorToken", f"{float(fits['parser_pasos']['c']):.2f}")
    if "coloreo_exacto_mediana" in fits:
        import math
        base = float(fits["coloreo_exacto_mediana"]["c"])
        number("ColoreoBase", f"{base:.3f}")
        number("ColoreoDuplica", f"{math.log(2) / math.log(base):.1f}")
        number("ColoreoRdos", f"{float(fits['coloreo_exacto_mediana']['r2']):.3f}")
    with (OUT_MD / "profiling.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    typ = [r for r in rows if r["familia"] == "tipico"]
    worst = [r for r in rows if r["familia"] == "peor_caso"]
    number("ProfMaxTokens", miles(int(typ[-1]['tokens'])))
    number("ProfMaxRI", miles(int(typ[-1]['instrucciones_ri'])))
    number("ProfPeorMaxAristas", miles(int(worst[-1]['aristas'])))
    lines = []
    for r in typ:
        lines.append(rf"{r['sentencias']} & {r['caracteres']} & {r['tokens']} & {r['instrucciones_ri']} & "
                     rf"{float(r['t_lexer']) * 1e3:.1f} & {float(r['t_parser']) * 1e3:.1f} & {float(r['t_optimizador']) * 1e3:.0f} \\")
    write("f7_mediciones.tex", "\n".join(lines) + "\n")
    lines = []
    for r in typ:
        N, w, t = int(r["instrucciones_ri"]), int(r["trabajo_opt"]), float(r["t_optimizador"])
        lines.append(rf"{r['sentencias']} & {N} & {r['rondas']} & {w} & {w / N:.1f} & {t / w * 1e9:.0f} \\")
    write("f7_optimizador.tex", "\n".join(lines) + "\n")
    ratios = [float(r["t_optimizador"]) / int(r["trabajo_opt"]) for r in typ]
    number("NsPorOpMin", f"{min(ratios) * 1e9:.0f}")
    number("NsPorOpMax", f"{max(ratios) * 1e9:.0f}")
    v1 = OUT_MD / "profiling_optimizador_v1.csv"
    if v1.exists():
        with v1.open(encoding="utf-8") as f:
            r1 = list(csv.DictReader(f))
        number("OptVUnoMax", f"{float(r1[-1]['t_optimizador_v1']):.1f}")
        number("OptVDosMax", f"{float(typ[-1]['t_optimizador']):.1f}")
        number("OptVUnoPend", f"{loglog([int(r['instrucciones_ri']) for r in r1], [float(r['t_optimizador_v1']) for r in r1]):.2f}")
    for name in ("profiling_fases.pdf", "coloreo_exacto.pdf", "optimizador_antes_despues.pdf"):
        if (OUT_MD / name).exists():
            shutil.copy(OUT_MD / name, OUT_TEX / name)


# --- Pruebas ----------------------------------------------------------------------


def pruebas() -> None:
    cats = ["validos", "error_lexico", "error_sintactico", "error_semantico", "bucle_infinito"]
    for c in cats:
        number("NProg" + c.replace("_", "").capitalize(), len(programs(c)))
    number("NProgramas", sum(len(programs(c)) for c in cats))
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "--collect-only"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    m = re.search(r"(\d+) tests? collected", out)
    number("NTests", m.group(1) if m else "?")


def miles(n: int) -> str:
    """Separador de miles con espacio fino (sin ambigüedad con el punto decimal)."""
    return f"{n:,}".replace(",", "\u2009")


def loglog(xs, ys) -> float:
    import math
    import statistics
    lx, ly = [math.log(x) for x in xs], [math.log(y) for y in ys]
    mx, my = statistics.fmean(lx), statistics.fmean(ly)
    return sum((a - mx) * (b - my) for a, b in zip(lx, ly)) / sum((a - mx) ** 2 for a in lx)


def gridify(*names: str) -> None:
    """Versión "con grilla" de un fragmento de tabla: una línea horizontal después
    de cada fila (estilo de tabla de Word de la plantilla UBP)."""
    for name in names:
        src = (OUT_TEX / f"{name}.tex").read_text(encoding="utf-8").splitlines()
        out = []
        for line in src:
            if line.strip() in (r"\midrule", r"\toprule", r"\bottomrule"):
                continue
            out.append(line + r" \hline" if line.rstrip().endswith("\\\\") else line)
        (OUT_TEX / f"{name}_grid.tex").write_text("\n".join(out) + "\n", encoding="utf-8")


def write_numbers() -> None:
    lines = ["% Generado por scripts/generar_documentacion.py"]
    for k, v in NUMBERS.items():
        lines.append(rf"\newcommand{{\{k}}}{{{tex(str(v)).replace(chr(0x2009), chr(92) + ',')}}}")
    write("numeros.tex", "\n".join(lines) + "\n")


if __name__ == "__main__":
    OUT_TEX.mkdir(parents=True, exist_ok=True)
    OUT_MD.mkdir(parents=True, exist_ok=True)
    if not HAS_DOT:
        print("Aviso: Graphviz (dot) no está en el PATH; se conservan los diagramas existentes.",
              file=sys.stderr)
    fase1()
    fase2()
    fases_4_5_8()
    fase7()
    pruebas()
    gridify("f2_first_follow", "f2_predict_compacto", "f2_traza", "f8_resultados")
    write_numbers()
    print("\n".join(f"{k} = {v}" for k, v in NUMBERS.items()))
