"""Convierte ARTICULO_HERMES_HETZNER.md a un formato compatible con Medium.

Transformaciones:
1. Tablas markdown -> listas con bullets anidados
2. **negritas** -> Unicode sans-serif bold (visible como negrita en texto plano)
3. [texto](url) -> "texto (url)" o solo "texto" si es ancla interna
4. <https://...> -> https://... en texto plano
"""
import re
import unicodedata
from pathlib import Path

SRC = Path(__file__).parent / "ARTICULO_HERMES_HETZNER.md"
DST = Path(__file__).parent / "ARTICULO_HERMES_HETZNER_MEDIUM.md"

# --- Unicode bold sans-serif (Mathematical Sans-Serif Bold) ---
BOLD_MAP = {}
for i in range(26):
    BOLD_MAP[chr(ord("A") + i)] = chr(0x1D5D4 + i)
    BOLD_MAP[chr(ord("a") + i)] = chr(0x1D5EE + i)
for i in range(10):
    BOLD_MAP[chr(ord("0") + i)] = chr(0x1D7EC + i)


def to_bold(text: str) -> str:
    """Convierte texto a Unicode sans-serif bold.

    Para caracteres acentuados (no hay versiones bold en Unicode), se descompone
    el carácter, se transforma la base y se recompone con la marca de acento.
    Asi 'á' bold -> '𝗮́' (carácter base bold + diacrítico combinante).
    """
    out = []
    for ch in text:
        if ch in BOLD_MAP:
            out.append(BOLD_MAP[ch])
            continue
        # Intenta descomponer (NFD) y transformar la base
        decomp = unicodedata.normalize("NFD", ch)
        if len(decomp) > 1 and decomp[0] in BOLD_MAP:
            out.append(BOLD_MAP[decomp[0]])
            for combining in decomp[1:]:
                out.append(combining)
            continue
        # ñ -> n + tilde combinante (lo descompone NFD)
        # ü -> u + diéresis combinante (idem)
        # Si llega aquí es un carácter sin equivalente: lo dejamos tal cual
        out.append(ch)
    return "".join(out)


# --- Tablas ---
# Detecta bloques: header | sep | datos+
TABLE_RE = re.compile(
    r"(^\|[^\n]+\|[ \t]*\n\|[\s\-:|]+\|[ \t]*\n(?:\|[^\n]+\|[ \t]*\n?)+)",
    re.MULTILINE,
)


def split_cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def convert_table(match: re.Match) -> str:
    block = match.group(0)
    lines = [ln for ln in block.split("\n") if ln.strip()]
    if len(lines) < 3:
        return block
    headers = split_cells(lines[0])
    # lines[1] es separador
    out_lines = []
    for row in lines[2:]:
        cells = split_cells(row)
        if not any(cells):
            continue
        # Iguala longitudes
        while len(cells) < len(headers):
            cells.append("")
        # Primera celda como bullet principal
        out_lines.append(f"- {cells[0]}")
        for h, c in zip(headers[1:], cells[1:]):
            if not c:
                continue
            if h:
                out_lines.append(f"  - {h}: {c}")
            else:
                out_lines.append(f"  - {c}")
    return "\n".join(out_lines) + "\n"


# --- Enlaces ---
def convert_link(match: re.Match) -> str:
    text, url = match.group(1), match.group(2)
    if url.startswith("#"):
        return text  # ancla interna -> solo texto
    return f"{text} ({url})"


def bold_inner(text: str) -> str:
    """Procesa el contenido de un **...**: aplica Unicode bold al texto pero
    deja las URLs de los enlaces markdown intactas (en ASCII plano, para que
    Medium las pueda autodetectar como hipervínculos al pegar)."""
    pieces = re.split(r"(\[[^\]]+\]\([^)]+\))", text)
    out = []
    for p in pieces:
        m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", p)
        if m:
            linktext, url = m.group(1), m.group(2)
            out.append(f"{to_bold(linktext)} ({url})")
        else:
            out.append(to_bold(p))
    return "".join(out)


def transform(content: str) -> str:
    # 1) Tablas primero (para que las negritas y enlaces dentro se procesen luego)
    content = TABLE_RE.sub(convert_table, content)

    # 2) **negritas** -> Unicode bold (preservando URLs en su interior)
    #    Procesamos solo fuera de bloques ``` para no romper code samples.
    parts = re.split(r"(```.*?```)", content, flags=re.DOTALL)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(
            r"\*\*([^*\n]+)\*\*",
            lambda m: bold_inner(m.group(1)),
            parts[i],
        )
    content = "".join(parts)

    # 3) [texto](url) -> texto (url)  (links restantes, fuera de bold)
    content = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", convert_link, content)

    # 4) <https://...> y <http://...> -> URL plana
    content = re.sub(r"<(https?://[^>]+)>", r"\1", content)

    return content


def main() -> None:
    raw = SRC.read_text(encoding="utf-8")
    out = transform(raw)
    DST.write_text(out, encoding="utf-8")
    print(f"OK -> {DST}")
    print(f"   chars in:  {len(raw)}")
    print(f"   chars out: {len(out)}")


if __name__ == "__main__":
    main()
