"""Shared corpus I/O, tokenization, and tree helpers for Modus Querens scripts.

Stdlib only — safe for build_tree.py. BM25 scripts add rank-bm25 separately.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Iterator

DEFAULT_ENCODING = "utf-8-sig"

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_FILE_LINES = 200_000
MAX_TOKENS_PER_NODE = 2_048
MAX_CHARS_PER_NODE = 16_384
MIN_TOKENS_TO_INDEX = 1
MAX_INDEXED_NODES = 250_000
MAX_PATH_DEPTH = 64
TOKENIZER_VERSION = "mq_v2"

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")

# Multilingual span patterns (order matters — longer/specific first).
_SPAN_RE = re.compile(
    r"https?://\S+"
    r"|[\w.+-]+@[\w-]+\.[\w.-]+"
    r"|v?\d+(?:\.\d+)+"
    r"|[a-z0-9_]+(?:-[a-z0-9_]+)*"
    r"|[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+"  # CJK ideographs
    r"|[\u3040-\u309f]+"  # Hiragana
    r"|[\u30a0-\u30ff]+"  # Katakana
    r"|[\uac00-\ud7af]+"  # Hangul syllables
    r"|[\u0e00-\u0e7f]+"  # Thai
    r"|[\u0400-\u04ff\u0500-\u052f]+"  # Cyrillic (+ extensions)
    r"|[\u0600-\u06ff\u0750-\u077f]+"  # Arabic
    r"|[\u0900-\u097f]+"  # Devanagari
    r"|[\u0370-\u03ff]+"  # Greek
    r"|[\u0590-\u05ff]+"  # Hebrew
    r"|[\u0100-\u024f\u1e00-\u1eff]+(?:'[a-z0-9]+)?"  # Latin extended + apostrophe
)

_DENSE_SCRIPTS = frozenset({"cjk", "hiragana", "katakana", "hangul", "thai", "arabic", "devanagari", "hebrew"})
_LATIN_SCRIPTS = frozenset({"latin", "latin_ext"})

_MD_INLINE_RE = re.compile(r"[*_`~\[\]()#]+")

# Query-side only — high-frequency function words (Latin scripts). Never strip from index.
MINIMAL_STOP = frozenset({
    # English
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for",
    "is", "are", "was", "were", "be", "been", "with", "as", "at", "by",
    "it", "this", "that", "my", "how", "what", "when", "where", "which",
    # French
    "le", "la", "les", "de", "du", "des", "et", "est", "un", "une", "dans", "pour",
    # German
    "der", "die", "das", "und", "ist", "ein", "eine", "für", "mit", "von",
    # Spanish
    "el", "los", "las", "y", "en", "del", "al", "por", "con", "una", "uno",
})


def resolve_corpus(corpus_dir: str | Path) -> Path:
    root = Path(corpus_dir).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"corpus_dir must be an existing directory: {root}")
    return root


def is_under_corpus(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def safe_rel_path(path: Path, root: Path) -> str:
    rel = path.resolve().relative_to(root.resolve())
    if ".." in rel.parts:
        raise ValueError(f"path escapes corpus: {path}")
    return rel.as_posix()


def iter_corpus_files(
    root: Path,
    exts: set[str],
    *,
    follow_symlinks: bool = False,
) -> list[Path]:
    out: list[Path] = []
    try:
        paths = root.rglob("*", follow_symlinks=follow_symlinks)
    except TypeError:
        paths = root.rglob("*")
    for path in paths:
        if not path.is_file():
            continue
        if path.is_symlink():
            continue
        if path.suffix.lower() not in exts:
            continue
        if not is_under_corpus(path, root):
            continue
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if len(rel.parts) > MAX_PATH_DEPTH:
            continue
        out.append(path)
    return sorted(out)


def read_corpus_lines(
    path: Path,
    *,
    encoding: str = DEFAULT_ENCODING,
    errors: str = "replace",
) -> list[str]:
    """Read source lines — must stay aligned with build_tree.py line numbers."""
    text = path.read_text(encoding=encoding, errors=errors)
    if "\x00" in text:
        text = text.replace("\x00", "")
    return text.splitlines()


def read_corpus_lines_bounded(
    path: Path,
    *,
    encoding: str = DEFAULT_ENCODING,
    errors: str = "strict",
) -> tuple[list[str] | None, str | None]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, f"os_error:{path}:{exc}"
    if size > MAX_FILE_BYTES:
        return None, f"oversize_file:{path}:{size}"
    try:
        lines = read_corpus_lines(path, encoding=encoding, errors=errors)
    except UnicodeDecodeError:
        return None, f"decode_error:{path}"
    except OSError as exc:
        return None, f"os_error:{path}:{exc}"
    if len(lines) > MAX_FILE_LINES:
        return None, f"oversize_lines:{path}:{len(lines)}"
    return lines, None


def normalize_text(text: str, *, casefold: bool = True) -> str:
    """NFKC + NFC so fullwidth Latin/digits and composed forms match across scripts."""
    text = unicodedata.normalize("NFKC", text)
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\ufeff", "")
    return text.casefold() if casefold else text


def strip_markdown_prose(text: str) -> str:
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(_MD_INLINE_RE.sub(" ", line))
    return "\n".join(out)


def _classify_span(span: str) -> str:
    if span.startswith("http://") or span.startswith("https://"):
        return "url"
    if "@" in span and "." in span:
        return "email"
    if re.fullmatch(r"v?\d+(?:\.\d+)+", span):
        return "version"
    if re.fullmatch(r"[a-z0-9_]+(?:-[a-z0-9_]+)*", span):
        return "latin"
    if re.fullmatch(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+", span):
        return "cjk"
    if re.fullmatch(r"[\u3040-\u309f]+", span):
        return "hiragana"
    if re.fullmatch(r"[\u30a0-\u30ff]+", span):
        return "katakana"
    if re.fullmatch(r"[\uac00-\ud7af]+", span):
        return "hangul"
    if re.fullmatch(r"[\u0e00-\u0e7f]+", span):
        return "thai"
    if re.fullmatch(r"[\u0400-\u04ff\u0500-\u052f]+", span):
        return "cyrillic"
    if re.fullmatch(r"[\u0600-\u06ff\u0750-\u077f]+", span):
        return "arabic"
    if re.fullmatch(r"[\u0900-\u097f]+", span):
        return "devanagari"
    if re.fullmatch(r"[\u0370-\u03ff]+", span):
        return "greek"
    if re.fullmatch(r"[\u0590-\u05ff]+", span):
        return "hebrew"
    return "latin_ext"


def _is_dense_script(kind: str) -> bool:
    return kind in _DENSE_SCRIPTS


def _accept_token(tok: str, *, kind: str) -> bool:
    if not tok:
        return False
    if tok.isdigit() or re.fullmatch(r"v?\d+(?:\.\d+)+", tok):
        return True
    if _is_dense_script(kind):
        return len(tok) >= 1
    if kind in _LATIN_SCRIPTS or kind in {"cyrillic", "greek"}:
        return len(tok) >= 2
    return len(tok) >= 2


def _dense_tokens(chunk: str, *, query: bool, max_bigrams: int = 128) -> list[str]:
    """Whole run + capped bigrams; unigrams for short spans or queries."""
    out: list[str] = [chunk]
    if query or len(chunk) <= 6:
        out.extend(chunk)
    if len(chunk) >= 2:
        limit = len(chunk) - 1 if query else min(len(chunk) - 1, max_bigrams)
        for i in range(limit):
            out.append(chunk[i : i + 2])
    return out


def _expand_span(span: str, *, query: bool) -> list[str]:
    kind = _classify_span(span)
    if _is_dense_script(kind):
        raw = _dense_tokens(span, query=query)
    elif kind == "hangul":
        raw = _dense_tokens(span, query=query)
    else:
        raw = [span]
    return [t for t in raw if _accept_token(t, kind=kind)]


def tokenize(text: str, *, query: bool = False, min_len: int = 2) -> list[str]:
    del min_len  # kept for API stability; script-aware rules live in _accept_token
    text = normalize_text(strip_markdown_prose(text))
    tokens: list[str] = []

    for match in _SPAN_RE.finditer(text):
        tokens.extend(_expand_span(match.group(0), query=query))

    if query and len(tokens) > 10:
        tokens = [t for t in tokens if t not in MINIMAL_STOP]

    seen: set[str] = set()
    deduped: list[str] = []
    for t in tokens:
        if not t or t in seen:
            continue
        seen.add(t)
        deduped.append(t)
    return deduped


def truncate_for_index(text: str) -> tuple[str, bool]:
    truncated = False
    if len(text) > MAX_CHARS_PER_NODE:
        text = text[:MAX_CHARS_PER_NODE]
        truncated = True
    toks = tokenize(text, query=False)
    if len(toks) > MAX_TOKENS_PER_NODE:
        ratio = MAX_TOKENS_PER_NODE / max(len(toks), 1)
        cut = max(1, int(len(text) * ratio))
        text = text[:cut]
        truncated = True
    return text, truncated


def walk_nodes(nodes: list[dict]) -> Iterator[dict]:
    for node in nodes:
        yield node
        yield from walk_nodes(node.get("nodes", []))


def own_body_lines(node: dict, lines: list[str]) -> list[str]:
    start = node.get("line_start", 1)
    end = node.get("line_end", len(lines))
    if start < 1 or end < start:
        return []
    children = node.get("nodes") or []
    body_end = end
    if children:
        first_child = min(c.get("line_start", end + 1) for c in children)
        body_end = min(end, first_child - 1)
    if body_end < start:
        return []
    return lines[start - 1 : body_end]


def is_leaf(node: dict) -> bool:
    return not bool(node.get("nodes"))


def node_index_text(node: dict, lines: list[str]) -> tuple[str, bool]:
    title = node.get("title", "")
    summary = node.get("summary", "")
    body = "\n".join(own_body_lines(node, lines))
    parts = [title, title, summary, body] if title else [summary, body]
    raw = "\n".join(p for p in parts if p)
    return truncate_for_index(raw)


def flatten_tree_doc(tree: dict, lines: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    doc_slug = tree["doc_slug"]
    doc_path = tree["doc_path"]
    for node in walk_nodes(tree.get("structure", [])):
        text, truncated = node_index_text(node, lines)
        toks = tokenize(text, query=False)
        if len(toks) < MIN_TOKENS_TO_INDEX:
            continue
        rows.append({
            "doc_slug": doc_slug,
            "doc_path": doc_path,
            "node_id": node.get("node_id", ""),
            "title": node.get("title", ""),
            "line_start": node.get("line_start", 1),
            "line_end": node.get("line_end", 1),
            "leaf": is_leaf(node),
            "truncated": truncated,
            "token_count": len(toks),
            "tokens": toks,
        })
    return rows
