#!/usr/bin/env python3
"""Render a validated package into separate DOCX files (CV, cover letter, answers).

Usage: python scripts/render_docs.py package.json outdir [--pdf] [--date YYYY-MM-DD]

Requires python-docx. Each document is its own file. Nothing is zipped.
Files are named "<Company> - <Role> - <YYYY-MM-DD> - <Document>.docx", with
characters that are illegal in file names on Windows or Linux removed.

--pdf converts each DOCX with LibreOffice (`soffice`) if it is installed. If it
is not, a notice is printed and the DOCX files are still written. PDF output has
not been verified on every machine: check the files exist before relying on them.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from docx import Document  # noqa: E402
from docx.shared import Pt  # noqa: E402
from schemas.models import ApplicationPackage  # noqa: E402

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_name(text: str, limit: int = 60) -> str:
    """Make text safe as part of a file name on Windows and Linux."""
    cleaned = _ILLEGAL.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")[:limit].strip(" .")
    if not cleaned:
        cleaned = "untitled"
    if cleaned.split(".")[0].upper() in _RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned


def file_stem(pkg: ApplicationPackage, on: date) -> str:
    return f"{safe_name(pkg.posting.company)} - {safe_name(pkg.posting.role)} - {on.isoformat()}"


def _doc() -> Document:
    d = Document()
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    return d


def render(pkg: ApplicationPackage, outdir: Path, on: date | None = None) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    stem = file_stem(pkg, on or date.today())
    cv, files = pkg.cv, []

    d = _doc()
    d.add_heading(cv.name, 0)
    d.add_paragraph(" | ".join(x for x in [cv.email, cv.location, *cv.links] if x))
    d.add_heading("Summary", 1)
    d.add_paragraph(cv.summary)
    for title, roles in (("Experience", cv.experience), ("Projects", cv.projects)):
        if roles:
            d.add_heading(title, 1)
            for r in roles:
                d.add_paragraph(f"{r.title}, {r.organisation} ({r.period})").runs[0].bold = True
                for b in r.bullets:
                    d.add_paragraph(b.text, style="List Bullet")
    d.add_heading("Skills", 1)
    d.add_paragraph(", ".join(cv.skills))
    if cv.education:
        d.add_heading("Education", 1)
        for e in cv.education:
            d.add_paragraph(e, style="List Bullet")
    p = outdir / f"{stem} - CV.docx"
    d.save(p)
    files.append(p)

    d = _doc()
    d.add_paragraph(cv.name).runs[0].bold = True
    for para in pkg.cover_letter.split("\n\n"):
        d.add_paragraph(para)
    p = outdir / f"{stem} - Cover letter.docx"
    d.save(p)
    files.append(p)

    d = _doc()
    d.add_heading("Application answers", 1)
    for a in pkg.answers:
        d.add_paragraph(a.question).runs[0].bold = True
        d.add_paragraph(a.answer)
    p = outdir / f"{stem} - Answers.docx"
    d.save(p)
    files.append(p)
    return files


def convert_to_pdf(docx_files: list[Path], outdir: Path) -> list[Path]:
    """Convert DOCX files with LibreOffice. Prints a notice and returns [] if it is missing."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice is None:
        print(
            "NOTICE: --pdf requested but LibreOffice (soffice) was not found. "
            "DOCX files were written; install LibreOffice to get PDFs.",
            file=sys.stderr,
        )
        return []
    pdfs: list[Path] = []
    for f in docx_files:
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(f)],
            capture_output=True, text=True, timeout=180,
        )
        pdf = f.with_suffix(".pdf")
        if result.returncode == 0 and pdf.exists():
            pdfs.append(pdf)
        else:
            print(f"NOTICE: PDF conversion failed for {f.name}: {result.stderr.strip() or 'no output'}", file=sys.stderr)
    return pdfs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render a validated package to DOCX (and optionally PDF).")
    ap.add_argument("package", type=Path)
    ap.add_argument("outdir", type=Path)
    ap.add_argument("--pdf", action="store_true", help="also convert to PDF if LibreOffice is installed")
    ap.add_argument("--date", type=date.fromisoformat, default=None, help="date for file names (default: today)")
    args = ap.parse_args(argv)
    pkg = ApplicationPackage.model_validate(json.loads(args.package.read_text(encoding="utf-8")))
    files = render(pkg, args.outdir, args.date)
    for f in files:
        print("wrote", f)
    if args.pdf:
        for f in convert_to_pdf(files, args.outdir):
            print("wrote", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
