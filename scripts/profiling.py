"""Fase 7: profiling real (tiempo vs. tamaño de entrada) del lexer, el parser y el optimizador.

Uso:  python scripts/profiling.py [--rapido]

Genera en docs/generado/:
  profiling.csv            mediciones crudas
  profiling_ajustes.csv    pendiente log-log y ajuste por mínimos cuadrados de cada serie
  profiling_fases.pdf/png  lexer, parser y optimizador (caso típico y peor caso)
  coloreo_exacto.pdf/png   búsqueda exhaustiva vs. heurística de Chaitin
"""

from __future__ import annotations

import csv
import gc
import math
import platform
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from lcero.generator import clique_program, typical_program  # noqa: E402
from lcero.ir import generate  # noqa: E402
from lcero.lexer import Lexer  # noqa: E402
from lcero.parser import Parser  # noqa: E402
from lcero.regalloc import InterferenceGraph, allocate, chaitin_color, exact_coloring  # noqa: E402
from lcero.semantic import analyze  # noqa: E402

OUT = ROOT / "docs" / "generado"

# Paleta de referencia (slots categóricos 1-3, válidos para todos los pares) y tintas neutras.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def timed(fn, repeat: int) -> float:
    """Mediana de ``repeat`` ejecuciones, con el recolector de basura apagado."""
    samples = []
    for _ in range(repeat):
        gc.collect()
        gc.disable()
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
        gc.enable()
    return statistics.median(samples)


def loglog_slope(xs, ys) -> float:
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    mx, my = statistics.fmean(lx), statistics.fmean(ly)
    return sum((a - mx) * (b - my) for a, b in zip(lx, ly)) / sum((a - mx) ** 2 for a in lx)


def fit_through_origin(xs, ys, f) -> float:
    """c que minimiza Σ (y − c·f(x))²."""
    return sum(y * f(x) for x, y in zip(xs, ys)) / sum(f(x) ** 2 for x in xs)


def fit_entry(serie: str, x: str, modelo: str, xs, ys, f) -> dict:
    c = fit_through_origin(xs, ys, f)
    return {"serie": serie, "x": x, "modelo": modelo, "c": c,
            "pendiente_loglog": loglog_slope(xs, ys), "r2": r2(xs, ys, lambda v: c * f(v))}


def r2(xs, ys, model) -> float:
    my = statistics.fmean(ys)
    ss_res = sum((y - model(x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    return 1 - ss_res / ss_tot


def work(alloc) -> int:
    """Operaciones elementales del optimizador: instrucciones procesadas por la
    vivacidad + nodos + aristas, sumadas sobre todas las rondas."""
    return sum(r.liveness_work + r.nodes + r.edges + r.instructions for r in alloc.rounds)


def measure(quick: bool) -> list[dict]:
    rows = []
    lexer, parser = Lexer(), Parser()
    repeat = 3 if quick else 5
    sizes = [250, 500, 1000, 2000, 4000, 8000] if quick else [250, 500, 1000, 2000, 4000, 8000, 12000, 16000]
    for s in sizes:
        src = typical_program(s, seed=s)
        tokens = lexer.tokenize(src)
        prog = parser.parse(tokens)
        analyze(prog)
        tac = generate(prog)
        t_lex = timed(lambda: lexer.tokenize(src), repeat)
        t_par = timed(lambda: parser.parse(tokens), repeat)
        t_opt = timed(lambda: allocate(tac, 4), repeat)
        alloc = allocate(tac, 4)
        rows.append({
            "familia": "tipico", "sentencias": s, "caracteres": len(src), "tokens": len(tokens),
            "pasos_pda": parser.steps, "instrucciones_ri": len(tac), "nodos": alloc.rounds[0].nodes,
            "aristas": alloc.rounds[0].edges, "rondas": len(alloc.rounds), "trabajo_opt": work(alloc),
            "t_lexer": t_lex, "t_parser": t_par, "t_optimizador": t_opt,
        })
        print(f"típico  s={s:>6} tokens={len(tokens):>7} RI={len(tac):>6}  "
              f"lexer={t_lex:.3f}s parser={t_par:.3f}s opt={t_opt:.3f}s", flush=True)

    ms = [100, 200, 400, 600] if quick else [100, 200, 400, 600, 800, 1000, 1200, 1500]
    for m in ms:
        src = clique_program(m)
        prog = parser.parse(lexer.tokenize(src))
        analyze(prog)
        tac = generate(prog)
        t_opt = timed(lambda: allocate(tac, 8), repeat)
        alloc = allocate(tac, 8)
        rows.append({
            "familia": "peor_caso", "sentencias": 2 * m, "caracteres": len(src), "tokens": None,
            "pasos_pda": None, "instrucciones_ri": len(tac), "nodos": alloc.rounds[0].nodes,
            "aristas": alloc.rounds[0].edges, "rondas": len(alloc.rounds), "trabajo_opt": work(alloc),
            "t_lexer": None, "t_parser": None, "t_optimizador": t_opt,
        })
        print(f"peor    m={m:>6} RI={len(tac):>6} aristas={alloc.rounds[0].edges:>7}  opt={t_opt:.3f}s", flush=True)
    return rows


def measure_coloring(quick: bool) -> list[dict]:
    """Búsqueda exhaustiva vs. Chaitin sobre grafos aleatorios cerca del umbral de 3-coloreo."""
    rows = []
    sizes = list(range(20, 91, 10)) if quick else list(range(20, 111, 10))
    seeds = 5 if quick else 7
    budget = 1_000_000 if quick else 6_000_000
    for n in sizes:
        explored, t_exact, t_chaitin, timeouts = [], [], [], 0
        for seed in range(seeds):
            rng = random.Random(1000 * n + seed)
            p = 4.4 / n  # grado medio ≈ 4.4, cerca del umbral (≈ 4.69) donde 3-COL es más difícil
            adj = [set() for _ in range(n)]
            for i in range(n):
                for j in range(i + 1, n):
                    if rng.random() < p:
                        adj[i].add(j)
                        adj[j].add(i)
            t0 = time.perf_counter()
            try:
                _, e = exact_coloring(adj, 3, budget)
            except TimeoutError:
                e, timeouts = budget, timeouts + 1
            t_exact.append(time.perf_counter() - t0)
            explored.append(e)
            g = InterferenceGraph([str(i) for i in range(n)], {str(i): i for i in range(n)}, adj)
            t0 = time.perf_counter()
            chaitin_color(g, 3, [1.0] * n)
            t_chaitin.append(time.perf_counter() - t0)
        rows.append({
            "n": n, "nodos_explorados_mediana": statistics.median(explored), "nodos_explorados_max": max(explored),
            "t_exacto_mediana": statistics.median(t_exact), "t_exacto_max": max(t_exact),
            "t_chaitin_mediana": statistics.median(t_chaitin), "cortes_por_presupuesto": timeouts,
            "mediana_cortada": statistics.median(explored) >= budget, "presupuesto": budget,
        })
        print(f"coloreo n={n:>4} exacto: mediana {statistics.median(t_exact):.4f}s max {max(t_exact):.3f}s "
              f"({timeouts} cortes)  chaitin {statistics.median(t_chaitin) * 1e6:.0f}µs", flush=True)
    return rows


def style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, loc="left", fontsize=10.5, color=INK, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=9, color=INK2)
    ax.set_ylabel(ylabel, fontsize=9, color=INK2)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=INK2, labelsize=8)


def plot_series(ax, xs, ys, model_label: str, f, unit: float = 1e3) -> dict:
    c = fit_through_origin(xs, ys, f)
    slope = loglog_slope(xs, ys)
    det = r2(xs, ys, lambda x: c * f(x))
    grid = [min(xs) + (max(xs) - min(xs)) * i / 200 for i in range(201)]
    ax.plot(grid, [c * f(x) * unit for x in grid], color=ORANGE, linewidth=2, label=f"teórico: {model_label}")
    ax.plot(xs, [y * unit for y in ys], "o", color=BLUE, markersize=6, markeredgecolor="white",
            markeredgewidth=1.2, label="medido", zorder=3)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper left")
    ax.text(0.98, 0.04, f"pendiente log-log = {slope:.2f}\nR² = {det:.4f}", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8, color=INK2)
    return {"c": c, "pendiente_loglog": slope, "r2": det}


def plot_phases(rows: list[dict]) -> list[dict]:
    typ = [r for r in rows if r["familia"] == "tipico"]
    worst = [r for r in rows if r["familia"] == "peor_caso"]
    fits = []
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.4))
    plt.rcParams["font.family"] = "DejaVu Sans"

    n = [r["tokens"] for r in typ]
    ax = axes[0][0]
    style(ax, "Lexer (AFD mínimo)", "n = tokens de entrada", "tiempo (ms)")
    fits.append({"serie": "lexer", "x": "tokens", "modelo": "c·n", **plot_series(ax, n, [r["t_lexer"] for r in typ], "c·n", lambda x: x)})

    ax = axes[0][1]
    style(ax, "Parser LL(1) (autómata de pila)", "n = tokens de entrada", "tiempo (ms)")
    fits.append({"serie": "parser", "x": "tokens", "modelo": "c·n", **plot_series(ax, n, [r["t_parser"] for r in typ], "c·n", lambda x: x)})

    N = [r["instrucciones_ri"] for r in typ]
    ax = axes[1][0]
    style(ax, "Optimizador (Chaitin), programas típicos", "N = instrucciones de la RI", "tiempo (ms)")
    fits.append({"serie": "optimizador_tipico", "x": "instrucciones", "modelo": "c·N",
                 **plot_series(ax, N, [r["t_optimizador"] for r in typ], "c·N", lambda x: x)})

    Nw = [r["instrucciones_ri"] for r in worst]
    ax = axes[1][1]
    style(ax, "Optimizador, peor caso (interferencia = Kₘ)", "N = instrucciones de la RI", "tiempo (ms)")
    fits.append({"serie": "optimizador_peor", "x": "instrucciones", "modelo": "c·N²",
                 **plot_series(ax, Nw, [r["t_optimizador"] for r in worst], "c·N²", lambda x: x * x)})

    fig.tight_layout(h_pad=2.2, w_pad=2.0)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"profiling_fases.{ext}", dpi=170)
    plt.close(fig)
    return fits


def plot_before_after(rows: list[dict]) -> None:
    """Optimizador en programas típicos: primera versión (búsqueda lineal del
    candidato a derrame) contra la versión con montículo."""
    v1_path = OUT / "profiling_optimizador_v1.csv"
    if not v1_path.exists():
        return
    with v1_path.open(encoding="utf-8") as f:
        v1 = [(int(r["instrucciones_ri"]), float(r["t_optimizador_v1"])) for r in csv.DictReader(f)]
    typ = [(r["instrucciones_ri"], r["t_optimizador"]) for r in rows if r["familia"] == "tipico"]
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    style(ax, "Optimizador en programas típicos: antes y después del montículo", "N = instrucciones de la RI",
          "tiempo (s)")
    ax.plot([x for x, _ in v1], [y for _, y in v1], color=ORANGE, linewidth=2, marker="o", markersize=6,
            markeredgecolor="white", markeredgewidth=1.2, label=f"v1: candidato por recorrido lineal (pendiente {loglog_slope(*zip(*v1)):.2f})")
    ax.plot([x for x, _ in typ], [y for _, y in typ], color=BLUE, linewidth=2, marker="o", markersize=6,
            markeredgecolor="white", markeredgewidth=1.2, label=f"v2: montículo perezoso (pendiente {loglog_slope(*zip(*typ)):.2f})")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper left")
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"optimizador_antes_despues.{ext}", dpi=170)
    plt.close(fig)


def plot_coloring(rows: list[dict]) -> dict:
    """Tiempo de la búsqueda exhaustiva vs. Chaitin. Devuelve el ajuste exponencial."""
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    style(ax, "3-coloreo de grafos aleatorios: exacto vs. Chaitin", "|V| (vértices del grafo)",
          "tiempo (s, escala logarítmica)")
    ax.set_yscale("log")
    ns = [r["n"] for r in rows]
    ok = [r for r in rows if not r["mediana_cortada"]]
    # Ajuste t ≈ a·bⁿ sobre las medianas no cortadas por el presupuesto.
    xs, ly = [r["n"] for r in ok], [math.log(r["t_exacto_mediana"]) for r in ok]
    mx, my = statistics.fmean(xs), statistics.fmean(ly)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ly)) / sum((x - mx) ** 2 for x in xs)
    base = math.exp(slope)
    for key, color, label in (("t_exacto_max", ORANGE, "búsqueda exhaustiva, peor semilla"),
                              ("t_exacto_mediana", AQUA, "búsqueda exhaustiva, mediana")):
        ax.plot(ns, [r[key] for r in rows], color=color, linewidth=2, marker="o", markersize=6,
                markeredgecolor="white", markeredgewidth=1.2, label=label)
        full = [r for r in rows if not (r["cortes_por_presupuesto"] and (key == "t_exacto_max" or r["mediana_cortada"]))]
        cut = [r for r in rows if r not in full]
        ax.plot([r["n"] for r in cut], [r[key] for r in cut], "o", color="white", markersize=6,
                markeredgecolor=color, markeredgewidth=1.6)
    ax.plot(ns, [r["t_chaitin_mediana"] for r in rows], color=BLUE, linewidth=2, marker="o", markersize=6,
            markeredgecolor="white", markeredgewidth=1.2, label="heurística de Chaitin, mediana")
    ax.plot([], [], "o", color="white", markeredgecolor=INK2, markeredgewidth=1.6, label="cortado por presupuesto (≥)")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper left")
    ax.text(0.98, 0.04, f"mediana exacta $\\approx a \\cdot {base:.3f}^{{|V|}}$\n(se duplica cada {math.log(2) / slope:.1f} vértices)",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color=INK2)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"coloreo_exacto.{ext}", dpi=170)
    plt.close(fig)
    return {"serie": "coloreo_exacto_mediana", "x": "vertices", "modelo": "a·b^n", "c": base,
            "pendiente_loglog": slope, "r2": r2(xs, ly, lambda x: my + slope * (x - mx))}


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    quick = "--rapido" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Python {platform.python_version()} en {platform.machine()} ({platform.processor() or 'cpu desconocida'})")
    rows = measure(quick)
    write_csv(OUT / "profiling.csv", rows)
    fits = plot_phases(rows)
    plot_before_after(rows)
    typ = [r for r in rows if r["familia"] == "tipico"]
    fits.append(fit_entry("optimizador_trabajo", "instrucciones", "c·N",
                          [r["instrucciones_ri"] for r in typ], [r["trabajo_opt"] for r in typ], lambda x: x))
    fits.append(fit_entry("parser_pasos", "tokens", "c·n",
                          [r["tokens"] for r in typ], [r["pasos_pda"] for r in typ], lambda x: x))
    write_csv(OUT / "profiling_ajustes.csv", fits)
    for f in fits:
        print(f"{f['serie']:<20} modelo {f['modelo']:<5} pendiente log-log {f['pendiente_loglog']:.3f}  R² {f['r2']:.4f}")
    col = measure_coloring(quick)
    write_csv(OUT / "coloreo_exacto.csv", col)
    fits.append(plot_coloring(col))
    write_csv(OUT / "profiling_ajustes.csv", fits)
    print(f"coloreo exacto: mediana ≈ a·{fits[-1]['c']:.3f}^n, R² {fits[-1]['r2']:.3f}")


if __name__ == "__main__":
    main()
