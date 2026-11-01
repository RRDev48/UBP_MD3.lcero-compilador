"""Interfaz de línea de comandos.

    python -m lcero ejecutar programa.l0 [-k 4] [--max-pasos N]   compila y ejecuta
    python -m lcero avisos programa.l0                            Fase 3: avisos del compilador
    python -m lcero tokens programa.l0                            Fase 1: tokens
    python -m lcero afd                                           Fase 1: autómatas y matriz δ
    python -m lcero gramatica                                     Fase 2: First, Follow y tabla LL(1)
    python -m lcero ast programa.l0                               Fases 2-3: AST validado
    python -m lcero ri programa.l0                                Fase 4: código de tres direcciones
    python -m lcero registros programa.l0 [-k 4]                  Fase 8: interferencia y coloreo
    python -m lcero maquina programa.l0 [-k 4]                    Fase 5: programa de la máquina
    python -m lcero traza programa.l0 [-k 4] [--max-pasos N]      Fase 5: configuraciones de la máquina
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .alphabet import CLASSES
from .ast import dump
from .compiler import DEFAULT_REGISTERS, compile_source
from .errors import LCeroError
from .grammar import EPSILON
from .ir import format_tac
from .lcero_grammar import lcero_grammar
from .lexer import lexer_automata, tokenize
from .parser import Parser
from .report import COLUMN_LABEL, state_name
from .semantic import analyze
from .vm import format_program


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def cmd_ejecutar(args: argparse.Namespace) -> int:
    c = compile_source(_read(args.archivo), args.k)
    if not args.sin_avisos:
        for w in c.warnings:
            print(w, file=sys.stderr)
    r = c.machine().run(args.max_pasos)
    for v in r.output:
        print(v)
    if not r.halted:
        print(f"[la máquina no se detuvo en {r.steps} pasos]", file=sys.stderr)
        return 2
    if args.estadisticas:
        print(f"[{r.steps} pasos, {len(c.program)} instrucciones, k={args.k}, "
              f"derrames: {', '.join(c.allocation.slots) or 'ninguno'}]", file=sys.stderr)
    return 0


def cmd_avisos(args: argparse.Namespace) -> int:
    warnings = compile_source(_read(args.archivo)).warnings
    for w in warnings:
        print(w)
    print({0: "sin avisos", 1: "1 aviso"}.get(len(warnings), f"{len(warnings)} avisos"))
    return 0


def cmd_tokens(args: argparse.Namespace) -> int:
    for tok in tokenize(_read(args.archivo)):
        print(f"{tok.line:>4}:{tok.col:<4} {tok.type.name:<8} {tok.lexeme}")
    return 0


def cmd_afd(_: argparse.Namespace) -> int:
    a = lexer_automata()
    m = a.min_dfa
    print(f"AFN-ε (Thompson):        {a.nfa.n_states:>4} estados")
    print(f"AFD (subconjuntos):      {a.dfa.n_states:>4} estados")
    print(f"AFD mínimo (Hopcroft):   {m.n_states:>4} estados ({len(m.accepting)} finales)\n")
    w = 5
    print(" " * 7 + "".join(f"{COLUMN_LABEL[c]:>{w}}" for c in CLASSES))
    for q, row in enumerate(m.trans):
        mark = ("→" if q == m.start else " ") + ("*" if q in m.accepting else " ")
        cells = "".join(f"{'·' if t == m.sink else t:>{w}}" for t in row)
        print(f"{mark}{state_name(q, m):<5}{cells}")
    return 0


def cmd_gramatica(_: argparse.Namespace) -> int:
    g = lcero_grammar()
    print("Producciones:")
    for p in g.productions:
        print(f"  ({p.index:>2}) {p}")

    def fmt(s):
        return "{ " + ", ".join(sorted(s, key=lambda x: (x == EPSILON, x))) + " }"

    print("\nFirst / Follow:")
    for A in g.nonterminals:
        print(f"  {A:<11} First = {fmt(g.first[A])}")
        print(f"  {'':<11} Follow = {fmt(g.follow[A])}")
    table, conflicts = g.ll1_table()
    print(f"\nTabla LL(1): {len(table)} celdas, {len(conflicts)} conflictos → "
          f"{'la gramática es LL(1)' if not conflicts else 'NO es LL(1)'}")
    return 0


def cmd_ast(args: argparse.Namespace) -> int:
    prog = Parser().parse(tokenize(_read(args.archivo)))
    syms = analyze(prog)
    print(dump(prog))
    print("\nTabla de símbolos: " + ", ".join(f"{s.uid} (línea {s.line})" for s in syms))
    return 0


def cmd_ri(args: argparse.Namespace) -> int:
    print(format_tac(compile_source(_read(args.archivo)).tac))
    return 0


def cmd_registros(args: argparse.Namespace) -> int:
    alloc = compile_source(_read(args.archivo), args.k).allocation
    for i, r in enumerate(alloc.rounds, 1):
        print(f"Ronda {i}: {r.nodes} nodos, {r.edges} aristas, grado máximo {r.max_degree}, "
              f"derrames: {', '.join(r.spilled) or 'ninguno'}")
    print("\nAristas del grafo de interferencia (última ronda):")
    for a, b in alloc.graph.edges():
        print(f"  {a} — {b}")
    print("\nAsignación:")
    for name, reg in sorted(alloc.register.items(), key=lambda x: (x[1], x[0])):
        print(f"  R{reg} ← {name}")
    for name, slot in alloc.slots.items():
        print(f"  cinta[{slot}] ← {name} (derramada)")
    print("\nCódigo con registros físicos:")
    print(format_tac(alloc.physical()))
    return 0


def cmd_maquina(args: argparse.Namespace) -> int:
    print(format_program(compile_source(_read(args.archivo), args.k).program))
    return 0


def cmd_traza(args: argparse.Namespace) -> int:
    trace: list[str] = []
    r = compile_source(_read(args.archivo), args.k).machine().run(args.max_pasos, trace)
    for i, conf in enumerate(trace):
        print(f"C{i:<5} {conf}")
    return 0 if r.halted else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lcero", description="Compilador y máquina virtual de L-Cero")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sin_pasos = object()

    def add(name, func, help_, archivo=True, k=False, pasos=sin_pasos):
        p = sub.add_parser(name, help=help_)
        if archivo:
            p.add_argument("archivo")
        if k:
            p.add_argument("-k", type=int, default=DEFAULT_REGISTERS, help="registros físicos (≥ 2)")
        if pasos is not sin_pasos:
            p.add_argument("--max-pasos", type=int, default=pasos, help="corta la ejecución a los N pasos")
        p.set_defaults(func=func)
        return p

    p = add("ejecutar", cmd_ejecutar, "compila y ejecuta un programa", k=True, pasos=None)
    p.add_argument("--estadisticas", action="store_true", help="muestra pasos, instrucciones y derrames")
    p.add_argument("--sin-avisos", action="store_true", help="no muestra los avisos del compilador")
    add("avisos", cmd_avisos, "Fase 3: avisos del compilador (variables sin leer, bucles, código inalcanzable)")
    add("tokens", cmd_tokens, "Fase 1: lista los tokens")
    add("afd", cmd_afd, "Fase 1: autómatas del lexer y matriz δ", archivo=False)
    add("gramatica", cmd_gramatica, "Fase 2: First, Follow y tabla LL(1)", archivo=False)
    add("ast", cmd_ast, "Fases 2-3: AST validado y tabla de símbolos")
    add("ri", cmd_ri, "Fase 4: código de tres direcciones")
    add("registros", cmd_registros, "Fase 8: grafo de interferencia y coloreo", k=True)
    add("maquina", cmd_maquina, "Fase 5: programa de la máquina", k=True)
    add("traza", cmd_traza, "Fase 5: secuencia de configuraciones", k=True, pasos=200)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except LCeroError as e:
        for err in e.errores:
            print(err, file=sys.stderr)
        if len(e.errores) > 1:
            print(f"{len(e.errores)} errores", file=sys.stderr)
        return 1
    except (OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
