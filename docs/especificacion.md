# Especificación del lenguaje L-Cero

L-Cero es un lenguaje imperativo mínimo con un único tipo de dato (enteros),
declaración y asignación de variables, condicionales `if`/`else`, bucles
`while`, aritmética básica y salida por `print`.

```c
// Máximo común divisor por el algoritmo de Euclides
int a = 1071;
int b = 462;
while (b != 0) {
    int r = a % b;
    a = b;
    b = r;
}
print(a);   // 21
```

---

## 1. Alfabeto Σ

Σ es el conjunto de caracteres que pueden aparecer en un archivo fuente:

| Subconjunto | Caracteres | Uso |
|---|---|---|
| Σ_L (letras) | `a`–`z`, `A`–`Z`, `_` | identificadores y palabras reservadas |
| Σ_D (dígitos) | `0`–`9` | literales numéricos e identificadores |
| Σ_S (símbolos) | `+ - * / % = ! < > ( ) { } ;` | operadores y delimitadores |
| Σ_W (blancos) | espacio, `\t`, `\r`, `\n` | separadores (se descartan) |
| Σ_O (otros) | cualquier otro carácter Unicode | **solo** dentro de comentarios |

Σ = Σ_L ∪ Σ_D ∪ Σ_S ∪ Σ_W ∪ Σ_O. Un carácter de Σ_O fuera de un comentario
(por ejemplo `@`, `ñ`, `"`, `&`) produce un error léxico.

**Clases de caracteres.** Para que la matriz δ sea manejable, Σ se particiona
en 30 clases mediante una función π : Σ → C. Dos caracteres van a la misma
clase si ninguna expresión regular de los tokens los distingue: las 11 letras
que aparecen en palabras reservadas (`e f h i l n p r s t w`) tienen clase
propia porque el autómata las sigue una por una; el resto de las letras forma
la clase `L`; los dígitos, la clase `D`; cada símbolo de Σ_S tiene su clase;
`esp` agrupa espacio, tabulación y retorno de carro; `\n` va aparte porque
termina los comentarios; `otro` es Σ_O. Como π es una congruencia respecto de
todas las ER, el autómata sobre C reconoce exactamente el mismo lenguaje que
sobre Σ.

## 2. Tokens y expresiones regulares

Notación: `letra = [a-zA-Z_]`, `dígito = [0-9]`. La prioridad resuelve los
empates de longitud (las reservadas le ganan a `id`); entre longitudes
distintas manda el **máximo bocado**.

| Token | Expresión regular | Ejemplos |
|---|---|---|
| `INT` `IF` `ELSE` `WHILE` `PRINT` | `int`, `if`, `else`, `while`, `print` | |
| `ID` | `letra (letra \| dígito)*` | `x`, `esPrimo`, `_tmp1`, `iff`, `whilex` |
| `NUM` | `dígito dígito*` | `0`, `42`, `007` |
| `EQ` `NEQ` `LE` `GE` | `==`, `!=`, `<=`, `>=` | |
| `ASSIGN` `LT` `GT` | `=`, `<`, `>` | |
| `PLUS` `MINUS` `STAR` `SLASH` `PERCENT` | `+`, `-`, `*`, `/`, `%` | |
| `LPAREN` `RPAREN` `LBRACE` `RBRACE` `SEMI` | `(`, `)`, `{`, `}`, `;` | |
| *comentario* (se descarta) | `// (Σ − {\n})*` | `// hasta el fin de línea` |
| *espacio* (se descarta) | `(esp \| \n)(esp \| \n)*` | |

Decisiones de diseño:

- Las palabras reservadas distinguen mayúsculas: `While` es un identificador.
- Los literales son naturales; los negativos se escriben con el menos unario
  (`-5` son dos tokens). Así `x-1` se tokeniza sin ambigüedad.
- `123abc` son dos tokens (`NUM ID`); el error, si corresponde, es sintáctico.
- No hay operadores lógicos (`&&`, `||`, `!`): un `!` que no forma `!=` es
  error léxico. Las condiciones compuestas se expresan anidando `if`.
- Solo hay comentarios de línea. `/* ... */` se tokeniza como `SLASH STAR ...`
  y lo rechaza el parser.

## 3. Sintaxis (EBNF)

Esta es la gramática de referencia, escrita para que sea legible. En la
Fase 2 se reescribe en BNF LL(1) (sin repeticiones ni opcionales) y se
demuestra que no es ambigua con los conjuntos First y Follow.

```ebnf
programa     = { sentencia } ;
sentencia    = declaracion | asignacion | si | mientras | imprimir | bloque ;
declaracion  = "int" id [ "=" expresion ] ";" ;
asignacion   = id "=" expresion ";" ;
si           = "if" "(" expresion ")" bloque [ "else" ( bloque | si ) ] ;
mientras     = "while" "(" expresion ")" bloque ;
imprimir     = "print" "(" expresion ")" ";" ;
bloque       = "{" { sentencia } "}" ;

expresion    = aritmetica [ relacional aritmetica ] ;
relacional   = "==" | "!=" | "<" | "<=" | ">" | ">=" ;
aritmetica   = termino { ( "+" | "-" ) termino } ;
termino      = factor { ( "*" | "/" | "%" ) factor } ;
factor       = num | id | "(" expresion ")" | "-" factor ;
```

Decisiones de diseño:

- **Los cuerpos de `if`, `else` y `while` son siempre bloques** `{ ... }`.
  Esto elimina el problema del *else colgante* de raíz y deja la gramática
  LL(1) sin reglas de desambiguación ad hoc. `else if` se admite como caso
  particular (`else` seguido de otro `si`).
- **Precedencia** (de menor a mayor): relacionales < `+ -` < `* / %` < menos
  unario < paréntesis. `+ - * / %` asocian a izquierda.
- **Los relacionales no son asociativos**: `1 < 2 < 3` es error sintáctico
  (en C significaría `(1 < 2) < 3`, casi nunca lo que se quiere).

## 4. Semántica

**Valores.** El único tipo es el entero matemático ℤ, sin límite de tamaño.
Esto es esencial para la Fase 5: con registros no acotados, una máquina de
registros con suma, resta y salto condicional es Turing-completa (Minsky).

**Aritmética.** `+ - *` son las de ℤ. `/` trunca hacia cero (`-7 / 3 = -2`)
y `%` cumple `a = (a / b) * b + a % b`, así que el resto toma el signo del
dividendo (`-7 % 3 = -1`), igual que en C y Java. Dividir por cero es un
error de ejecución.

**Relacionales.** Valen `1` si se cumplen y `0` si no, y se pueden usar como
cualquier entero (`print(3 < 5)` imprime `1`).

**Condiciones.** `if (e)` y `while (e)` toman una expresión entera: es
verdadera si su valor es distinto de cero.

**Variables y ámbitos** (se verifican estáticamente en la Fase 3):

1. Toda variable se declara con `int` antes de usarse.
2. El ámbito de una declaración va desde ella hasta el `}` del bloque que la
   contiene. Fuera de ese bloque el nombre no existe.
3. **Doble declaración:** no se puede declarar un nombre que ya es visible,
   ni en el mismo bloque ni en uno anidado (no hay sombreado, como en Java).
   Dos bloques hermanos sí pueden declarar el mismo nombre.
4. **Asignación definida:** una variable declarada sin inicializar no puede
   leerse hasta que se le asigne un valor en *todos* los caminos posibles.
   Un `if` con `else` la inicializa si ambas ramas lo hacen; un `if` sin
   `else` o el cuerpo de un `while` no cuentan para lo que viene después,
   porque podrían no ejecutarse.

**Salida.** `print(e)` escribe el valor de `e` seguido de un salto de línea.

**Ejecución.** Las sentencias se ejecutan en orden; el programa termina
cuando termina la última. Un `while` cuya condición nunca se vuelve cero no
termina: la Fase 6 demuestra que ningún análisis estático puede detectar
esto en general.

## 5. Errores

Cada fase informa el primer error que encuentra, con línea y columna:

| Fase | Ejemplos |
|---|---|
| Léxico | carácter fuera de Σ (`@`, `ñ`, `"`), `!` que no forma `!=` |
| Sintáctico | falta `;`, llave sin cerrar, `else` sin `if`, `1 < 2 < 3`, cuerpo sin llaves |
| Semántico | doble declaración, variable sin declarar, lectura sin inicializar, uso fuera de ámbito |
| Ejecución | división o resto por cero |

La suite de pruebas tiene un programa de ejemplo para cada uno, en
`tests/programas/`.
