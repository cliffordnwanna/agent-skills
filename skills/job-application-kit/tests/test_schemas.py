import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas.models import ApplicationPackage, DiscoveryResult  # noqa: E402

EX = Path(__file__).resolve().parent.parent / "examples"
PKG = json.loads((EX / "package.example.json").read_text())
DISC = json.loads((EX / "discovery.example.json").read_text())


def test_examples_are_valid():
    ApplicationPackage.model_validate(PKG)
    DiscoveryResult.model_validate(DISC)


def test_unconfirmed_figure_is_rejected():
    bad = copy.deepcopy(PKG)
    bad["cv"]["experience"][0]["bullets"][0]["text"] = "Cut response time by 30%."
    with pytest.raises(ValidationError, match="not confirmed"):
        ApplicationPackage.model_validate(bad)


def test_claim_without_evidence_is_rejected():
    bad = copy.deepcopy(PKG)
    bad["matches"][1].update(status="strong", evidence=[])
    with pytest.raises(ValidationError, match="cites no evidence"):
        ApplicationPackage.model_validate(bad)


def test_high_risk_blocks_outreach():
    bad = copy.deepcopy(PKG)
    bad["flags"].append({"check": "legitimacy", "level": "high_risk", "evidence": "Asks for a registration fee"})
    bad["outreach"] = "Hello"
    with pytest.raises(ValidationError, match="high-risk"):
        ApplicationPackage.model_validate(bad)


def test_flags_never_block_output():
    ok = copy.deepcopy(PKG)
    ok["flags"].append({"check": "pay", "level": "flag", "evidence": "Below your floor"})
    ApplicationPackage.model_validate(ok)


def test_unanswered_question_is_rejected():
    bad = copy.deepcopy(PKG)
    bad["answers"].pop()
    with pytest.raises(ValidationError, match="unanswered"):
        ApplicationPackage.model_validate(bad)


def test_leanness_limits():
    bad = copy.deepcopy(PKG)
    bad["improve_next"] = [{"kind": "cv_fix", "text": "x" * 5}] * 4
    with pytest.raises(ValidationError):
        ApplicationPackage.model_validate(bad)


def test_discovery_max_five_and_date_logic():
    bad = copy.deepcopy(DISC)
    bad["leads"] = bad["leads"] * 6
    with pytest.raises(ValidationError):
        DiscoveryResult.model_validate(bad)
    bad2 = copy.deepcopy(DISC)
    bad2["leads"][0].update(posted_date=None, date_verified=True)
    with pytest.raises(ValidationError, match="date_verified"):
        DiscoveryResult.model_validate(bad2)


# ------------------------------------------------------------ added limits
def test_next_steps_cap_is_five():
    ok = copy.deepcopy(PKG)
    ok["next_steps"] = ["step"] * 5
    ApplicationPackage.model_validate(ok)
    bad = copy.deepcopy(PKG)
    bad["next_steps"] = ["step"] * 6
    with pytest.raises(ValidationError):
        ApplicationPackage.model_validate(bad)


def test_cover_letter_word_limit_is_250():
    ok = copy.deepcopy(PKG)
    ok["cover_letter"] = " ".join(["word"] * 250)
    ApplicationPackage.model_validate(ok)
    bad = copy.deepcopy(PKG)
    bad["cover_letter"] = " ".join(["word"] * 251)
    with pytest.raises(ValidationError, match="250 words"):
        ApplicationPackage.model_validate(bad)


@pytest.mark.parametrize(
    "text",
    [
        "Cut response time by thirty percent.",
        "Doubled revenue across the team.",
        "Reduced costs by half.",
        "Tripled onboarding throughput.",
        "Served hundreds of customers each week.",
        "Achieved a tenfold speed-up.",
    ],
)
def test_number_words_need_confirmation(text):
    bad = copy.deepcopy(PKG)
    bad["cv"]["experience"][0]["bullets"][0]["text"] = text
    with pytest.raises(ValidationError, match="not confirmed"):
        ApplicationPackage.model_validate(bad)
    ok = copy.deepcopy(bad)
    ok["cv"]["experience"][0]["bullets"][0]["figure_confirmed"] = True
    ApplicationPackage.model_validate(ok)


def test_plain_prose_with_one_is_not_flagged():
    ok = copy.deepcopy(PKG)
    ok["cv"]["experience"][0]["bullets"][0]["text"] = "Wrote a one-page guide that new hires use."
    ApplicationPackage.model_validate(ok)


def test_known_limit_figure_flag_is_self_attested():
    """Documents the limit: the check trusts figure_confirmed, and misses 'one third'."""
    ok = copy.deepcopy(PKG)
    ok["cv"]["experience"][0]["bullets"][0].update(text="Cut response time by 30%.", figure_confirmed=True)
    ApplicationPackage.model_validate(ok)
    miss = copy.deepcopy(PKG)
    miss["cv"]["experience"][0]["bullets"][0]["text"] = "Cut response time by one third."
    ApplicationPackage.model_validate(miss)  # heuristic gap, stated in the README


def test_exported_schema_files_are_in_sync():
    for name, model in {"application_package": ApplicationPackage, "discovery_result": DiscoveryResult}.items():
        on_disk = json.loads((EX.parent / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))
        assert on_disk == model.model_json_schema(), f"run scripts/export_schemas.py ({name} is stale)"
