"""Carga de los programas de prueba y de sus expectativas.

Cada archivo ``.l0`` declara en su primera línea lo que se espera de él:

    // SALIDA: 1 2 3          → programa válido; valores que imprime, en orden
    // ERROR: léxico 3:11     → falla en esa fase, en esa línea y columna
    // BUCLE                  → programa válido que no termina
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROGRAMS_DIR = Path(__file__).parent / "programas"


@dataclass(frozen=True)
class Program:
    path: Path
    source: str
    category: str  # carpeta: validos, error_lexico, error_sintactico, ...
    expected_output: tuple[int, ...] | None = None
    error_phase: str | None = None
    error_pos: tuple[int, int] | None = None
    infinite: bool = False

    @property
    def id(self) -> str:
        return f"{self.category}/{self.path.stem}"


def load(path: Path) -> Program:
    source = path.read_text(encoding="utf-8")
    header = source.splitlines()[0].removeprefix("//").strip()
    category = path.parent.name
    if header.startswith("SALIDA:"):
        values = tuple(int(v) for v in header.removeprefix("SALIDA:").split())
        return Program(path, source, category, expected_output=values)
    if header.startswith("ERROR:"):
        phase, pos = header.removeprefix("ERROR:").split()
        line, col = (int(x) for x in pos.split(":"))
        return Program(path, source, category, error_phase=phase, error_pos=(line, col))
    if header.startswith("BUCLE"):
        return Program(path, source, category, infinite=True)
    raise ValueError(f"{path}: encabezado de prueba inválido: {header!r}")


def programs(*categories: str) -> list[Program]:
    dirs = categories or tuple(sorted(p.name for p in PROGRAMS_DIR.iterdir() if p.is_dir()))
    return [load(p) for c in dirs for p in sorted((PROGRAMS_DIR / c).glob("*.l0"))]
