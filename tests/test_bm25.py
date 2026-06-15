"""Tests for Modus Querens corpus_utils and BM25 edge cases."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "modus-querens" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from corpus_utils import (  # noqa: E402
    flatten_tree_doc,
    normalize_text,
    own_body_lines,
    read_corpus_lines,
    tokenize,
    walk_nodes,
)

rank_bm25 = pytest.importorskip("rank_bm25")
from rank_bm25 import BM25Okapi  # noqa: E402


class TestEncoding:
    def test_utf8_sig_strips_bom(self, tmp_path: Path):
        p = tmp_path / "bom.md"
        p.write_bytes(b"\xef\xbb\xbf# Title\nbody")
        lines = read_corpus_lines(p)
        assert lines[0] == "# Title"

    def test_nfc_casefold_parity(self):
        nfc = "caf\u00e9"
        nfd = "cafe\u0301"
        assert normalize_text(nfc) == normalize_text(nfd)

    def test_nfkc_fullwidth_latin(self):
        assert "abc123" in tokenize("ＡＢＣ１２３ notes")

    def test_cjk_token(self):
        toks = tokenize("机器学习 notes")
        assert "机器学习" in toks
        assert "notes" in toks

    def test_crlf_line_count(self, tmp_path: Path):
        p = tmp_path / "crlf.md"
        p.write_bytes(b"# A\r\nline\r\n")
        assert len(read_corpus_lines(p)) == 2


class TestMultilingual:
    def test_japanese_mixed(self):
        toks = tokenize("機械学習とデータ分析")
        assert "機械学習" in toks
        assert "データ" in toks

    def test_korean(self):
        toks = tokenize("안녕하세요 세계")
        assert "안녕하세요" in toks
        assert "세계" in toks

    def test_cyrillic(self):
        toks = tokenize("машинное обучение notes")
        assert "машинное" in toks
        assert "notes" in toks

    def test_greek(self):
        toks = tokenize("μηχανική μάθηση")
        assert "μηχανική" in toks

    def test_arabic(self):
        toks = tokenize("تعلم الآلة")
        assert "تعلم" in toks

    def test_thai(self):
        toks = tokenize("การเรียนรู้ของเครื่อง")
        assert "การเรียนรู้ของเครื่อง" in toks

    def test_cjk_bigram_recall(self):
        doc = tokenize("机器学习模型", query=False)
        bm25 = BM25Okapi([doc])
        # partial / bigram overlap should still rank the doc
        q = tokenize("机器 学习", query=True)
        assert bm25.get_scores(q)[0] != 0.0

    def test_cjk_single_char_query(self):
        assert tokenize("学", query=True)

    def test_latin_single_char_query_rejected(self):
        assert tokenize("a", query=True) == []


class TestTokenization:
    DOCS = [
        "Residual streams in transformers connect forward pass to gradient flow.",
        "See https://example.com/paper and user@host.com",
        "Version v1.2.3 broke the state-of-the-art baseline.",
        "# How I fixed the bug\nDon't use foo with C++.",
        "café naïve résumé",
    ]

    def test_empty_query(self):
        assert tokenize("", query=True) == []
        assert tokenize("   ", query=True) == []

    def test_case_insensitive_match(self):
        tok_docs = [tokenize(d) for d in self.DOCS]
        bm25 = BM25Okapi(tok_docs)
        s1 = bm25.get_scores(tokenize("Residual", query=True))
        s2 = bm25.get_scores(tokenize("residual", query=True))
        assert s1[0] == s2[0]

    def test_url_and_version(self):
        tok_docs = [tokenize(d) for d in self.DOCS]
        bm25 = BM25Okapi(tok_docs)
        assert bm25.get_scores(tokenize("https://example.com/paper", query=True))[1] > 0
        assert bm25.get_scores(tokenize("v1.2.3", query=True))[2] > 0

    def test_long_probe_strips_stopwords(self):
        probe = (
            "How do my notes connect residual streams to gradient flow "
            "in transformer training and backpropagation?"
        )
        q = tokenize(probe, query=True)
        assert "residual" in q
        assert "gradient" in q
        assert len(q) <= 12

    def test_query_dedupes_tokens(self):
        assert tokenize("alpha alpha", query=True) == ["alpha"]

    def test_single_char_latin_query_rejected(self):
        assert tokenize("a", query=True) == []


class TestTreeIntegration:
    def test_own_body_excludes_child_span(self):
        lines = [
            "# Parent",
            "intro",
            "## Child",
            "child body",
            "# Next",
        ]
        tree = {
            "structure": [{
                "node_id": "0001",
                "title": "Parent",
                "line_start": 1,
                "line_end": 4,
                "summary": "",
                "nodes": [{
                    "node_id": "0002",
                    "title": "Child",
                    "line_start": 3,
                    "line_end": 4,
                    "summary": "",
                    "nodes": [],
                }],
            }]
        }
        parent = next(walk_nodes(tree["structure"]))
        body = "\n".join(own_body_lines(parent, lines))
        assert "intro" in body
        assert "child body" not in body

    def test_flatten_skips_empty_nodes(self):
        tree = {
            "doc_slug": "x",
            "doc_path": "x.md",
            "structure": [{
                "node_id": "0001",
                "title": "   ",
                "line_start": 1,
                "line_end": 1,
                "summary": "",
                "nodes": [],
            }],
        }
        rows = flatten_tree_doc(tree, ["   "])
        assert rows == []


class TestBM25Critical:
    def test_empty_corpus_guard(self):
        with pytest.raises(ZeroDivisionError):
            BM25Okapi([])

    def test_all_empty_after_tokenize_raises_or_skips(self):
        with pytest.raises(ZeroDivisionError):
            BM25Okapi([[], []])

    def test_empty_query_scores_zero(self):
        bm25 = BM25Okapi([tokenize("hello world")])
        scores = bm25.get_scores([])
        assert scores.max() == 0.0


class TestSecurity:
    def test_null_bytes_stripped(self, tmp_path: Path):
        p = tmp_path / "null.md"
        p.write_bytes(b"hello\x00world")
        text = "\n".join(read_corpus_lines(p))
        assert "\x00" not in text


class TestBuildBm25Script:
    def test_build_and_search_roundtrip(self, tmp_path: Path):
        corpus = tmp_path / "corpus"
        corpus.mkdir()
        (corpus / "note.md").write_text(
            "# Residual streams\n\nGradient flow through layers.\n",
            encoding="utf-8",
        )
        index = tmp_path / "index"
        index.mkdir()

        build_tree = SCRIPTS / "build_tree.py"
        build_bm25 = SCRIPTS / "build_bm25.py"
        search_bm25 = SCRIPTS / "search_bm25.py"

        import subprocess

        subprocess.run([sys.executable, str(build_tree), str(corpus), "--out", str(index)], check=True)
        subprocess.run(
            [sys.executable, str(build_bm25), str(corpus), "--index", str(index)],
            check=True,
        )

        meta = json.loads((index / "_bm25_meta.json").read_text(encoding="utf-8"))
        assert meta["node_count"] >= 1
        assert (index / "_bm25.pkl").is_file()

        out = subprocess.run(
            [sys.executable, str(search_bm25), "residual gradient", "--index", str(index)],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "residual" in out.stdout.lower() or "gradient" in out.stdout.lower()
