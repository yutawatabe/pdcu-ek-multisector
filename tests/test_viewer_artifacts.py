from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class _Parser(HTMLParser):
    pass


def test_viewer_artifacts_are_structurally_complete_and_current() -> None:
    viewer = ROOT / "viewer/model_viewer.html"
    annotated = ROOT / "viewer/model_annotated.py"
    manifest_path = ROOT / "viewer/manifest.json"
    quiz_path = ROOT / "viewer/quiz.json"

    html = viewer.read_text(encoding="utf-8")
    compile(annotated.read_text(encoding="utf-8"), str(annotated), "exec")
    _Parser().feed(html)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    quiz = json.loads(quiz_path.read_text(encoding="utf-8"))

    assert manifest["verification_passed"] is True
    assert manifest["step_count"] == 9
    assert manifest["flow_group_count"] == 3
    assert manifest["math_node_count"] >= 9
    assert len(quiz) == 8
    assert len({question["id"] for question in quiz}) == 8
    assert "$$" not in html
    assert "&#x20;" not in html
    assert "reader-oriented implementation" in html

    for relative_path, expected_hash in manifest["production_source_sha256"].items():
        actual_hash = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        assert actual_hash == expected_hash
