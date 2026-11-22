import copy
import json
import sys
from datetime import date
from pathlib import Path

import pytest
from docx import Document

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import render_docs  # noqa: E402
from schemas.models import ApplicationPackage  # noqa: E402

PKG = json.loads((ROOT / "examples" / "package.example.json").read_text(encoding="utf-8"))
DAY = date(2026, 1, 2)


def _pkg(company="Acme", role="Engineer"):
    data = copy.deepcopy(PKG)
    data["posting"]["company"], data["posting"]["role"] = company, role
    return ApplicationPackage.model_validate(data)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('A/B: "Co"?', "A B Co"),
        ("Acme <Labs>|Inc*", "Acme Labs Inc"),
        ("  trailing dots...  ", "trailing dots"),
        ("", "untitled"),
        ("///", "untitled"),
        ("CON", "_CON"),
    ],
)
def test_safe_name(raw, expected):
    assert render_docs.safe_name(raw) == expected


def test_safe_name_has_no_illegal_characters():
    out = render_docs.safe_name("x<>:\"/" + chr(92) + "|?*" + chr(0) + chr(31) + "y")
    assert not set('<>:"/?*|') & set(out) and chr(92) not in out
    assert all(ord(c) >= 32 for c in out)


def test_file_stem_has_company_role_and_date():
    assert render_docs.file_stem(_pkg(), DAY) == "Acme - Engineer - 2026-01-02"


def test_render_writes_three_separate_dated_docx_files(tmp_path):
    files = render_docs.render(_pkg("A/B: Co?", "Lead*"), tmp_path, DAY)
    names = sorted(p.name for p in files)
    assert names == [
        "A B Co - Lead - 2026-01-02 - Answers.docx",
        "A B Co - Lead - 2026-01-02 - CV.docx",
        "A B Co - Lead - 2026-01-02 - Cover letter.docx",
    ]
    for p in files:
        assert p.exists() and len(Document(p).paragraphs) > 0
    assert not list(tmp_path.glob("*.zip"))


def test_pdf_flag_prints_notice_when_libreoffice_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(render_docs.shutil, "which", lambda _name: None)
    files = render_docs.render(_pkg(), tmp_path, DAY)
    assert render_docs.convert_to_pdf(files, tmp_path) == []
    assert "LibreOffice" in capsys.readouterr().err
    assert all(p.exists() for p in files)  # DOCX still delivered


def test_cli_validates_before_rendering(tmp_path):
    bad = copy.deepcopy(PKG)
    bad["cv"]["experience"][0]["bullets"][0]["text"] = "Cut costs by 30%."
    src = tmp_path / "bad.json"
    src.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(Exception, match="not confirmed"):
        render_docs.main([str(src), str(tmp_path / "out")])
    assert not (tmp_path / "out").exists()
