"""Typed contracts for the Job Application Kit (Pydantic v2).

Every stage of the workflow produces JSON that must validate against these
models before documents are generated. The models encode the skill's rules in
code, so a rule can fail loudly instead of being forgotten:

* truth rule (a HEURISTIC, not a guarantee): every CV bullet names its evidence;
  any digit or common number word must be marked confirmed. The check cannot
  detect every quantity (e.g. "one third") and `figure_confirmed` is set by
  whoever builds the JSON, so it is only as strong as that step.
* flag-don't-block: flags are data, never a reason to refuse output
* high-risk postings: no outreach may be attached
* leanness: at most 3 improve-next items, at most 5 next steps, letter <= 250 words
* discovery: at most 5 leads, each with a verified-or-not posting date
"""
from __future__ import annotations

import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

# ---------------------------------------------------------------- posting
class Pay(BaseModel):
    stated: bool
    minimum: Optional[float] = Field(None, ge=0)
    maximum: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(None, min_length=3, max_length=3, description="ISO 4217, e.g. USD")
    unit: Optional[Literal["hour", "month", "year", "task", "project"]] = None

    @model_validator(mode="after")
    def _consistent(self) -> "Pay":
        if self.stated and (self.currency is None or self.unit is None):
            raise ValueError("stated pay needs currency and unit")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum exceeds maximum")
        return self


class Requirement(BaseModel):
    text: str = Field(min_length=3)
    kind: Literal["must", "nice"] = "must"


class Posting(BaseModel):
    company: str = Field(min_length=1)
    role: str = Field(min_length=1)
    url: Optional[HttpUrl] = None
    posted_date: Optional[date] = None
    employment_type: Optional[Literal["employee", "contractor", "gig", "unknown"]] = "unknown"
    location_rule: Optional[str] = Field(None, description="Quote of the posting's location restriction")
    visa_text: Optional[str] = None
    pay: Pay
    requirements: list[Requirement] = Field(min_length=1)
    questions: list[str] = Field(default_factory=list, description="Every question the posting or form asks")
    deadline: Optional[date] = None


# ---------------------------------------------------------------- screening
class Flag(BaseModel):
    check: Literal["eligibility", "legitimacy", "pay", "currency", "timezone", "other"]
    level: Literal["ok", "unknown", "flag", "high_risk"]
    evidence: str = Field(min_length=3, description="The deciding line from the posting, or the source")
    source_url: Optional[HttpUrl] = None

    @model_validator(mode="after")
    def _risk_needs_evidence_source(self) -> "Flag":
        if self.level == "high_risk" and self.check != "legitimacy":
            raise ValueError("high_risk is reserved for legitimacy findings")
        return self


class Match(BaseModel):
    requirement: str
    status: Literal["strong", "transferable", "gap"]
    evidence: list[str] = Field(default_factory=list, description="Portfolio or CV items that support it")
    framing: Optional[str] = Field(None, description="True wording in the posting's language")

    @model_validator(mode="after")
    def _no_claim_without_evidence(self) -> "Match":
        if self.status in ("strong", "transferable") and not self.evidence:
            raise ValueError(f"'{self.requirement}' is marked {self.status} but cites no evidence")
        return self


# ---------------------------------------------------------------- documents
_HAS_DIGIT = re.compile(r"\d")
# Common spelled-out quantities. Deliberately conservative: a false positive only
# means the builder must confirm the figure. "one" is excluded because it is far
# too common in ordinary prose ("one of", "one-page"). This is a heuristic and
# will miss things like "one third".
_NUMBER_WORDS = re.compile(
    r"\b(?:per ?cent|percent(?:age)?|half|double[ds]?|doubling|triple[ds]?|tripling|"
    r"quadruple[ds]?|twice|thrice|\w+fold|zero|two|three|four|five|six|seven|eight|nine|"
    r"ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|dozens?|hundreds?|"
    r"thousands?|millions?|billions?)\b",
    re.IGNORECASE,
)


def _mentions_figure(text: str) -> bool:
    return bool(_HAS_DIGIT.search(text) or _NUMBER_WORDS.search(text))


class Bullet(BaseModel):
    text: str = Field(min_length=5)
    evidence: str = Field(min_length=2, description="Portfolio item or user statement this comes from")
    figure_confirmed: bool = Field(False, description="True only if the user supplied or confirmed any number")

    @model_validator(mode="after")
    def _truth_rule(self) -> "Bullet":
        if _mentions_figure(self.text) and not self.figure_confirmed:
            raise ValueError(f"bullet contains a figure the user has not confirmed: {self.text!r}")
        return self


class Role(BaseModel):
    title: str
    organisation: str
    period: str
    bullets: list[Bullet] = Field(min_length=1, max_length=6)


class CV(BaseModel):
    name: str
    email: Optional[str] = None
    location: Optional[str] = None
    links: list[str] = Field(default_factory=list)
    summary: str = Field(max_length=500)
    experience: list[Role]
    projects: list[Role] = Field(default_factory=list)
    skills: list[str]
    education: list[str] = Field(default_factory=list)


class Answer(BaseModel):
    question: str
    answer: str
    fill_in: list[str] = Field(default_factory=list, description="Facts the user must supply")


class ImproveItem(BaseModel):
    kind: Literal["skill_to_learn", "cv_fix", "portfolio_fix", "evidence_needed"]
    text: str


class ApplicationPackage(BaseModel):
    posting: Posting
    flags: list[Flag] = Field(default_factory=list)
    matches: list[Match]
    answers: list[Answer]
    cv: CV
    cover_letter: str
    missing_info: list[str] = Field(default_factory=list)
    improve_next: list[ImproveItem] = Field(default_factory=list, max_length=3)
    next_steps: list[str] = Field(default_factory=list, max_length=5)
    outreach: Optional[str] = None

    @field_validator("cover_letter")
    @classmethod
    def _letter_length(cls, v: str) -> str:
        if len(v.split()) > 250:
            raise ValueError("cover letter exceeds 250 words")
        return v

    @model_validator(mode="after")
    def _rules(self) -> "ApplicationPackage":
        if any(f.level == "high_risk" for f in self.flags) and self.outreach:
            raise ValueError("outreach must not be drafted for a high-risk posting")
        asked = {q.strip().lower() for q in self.posting.questions}
        answered = {a.question.strip().lower() for a in self.answers}
        missing = asked - answered
        if missing:
            raise ValueError(f"unanswered posting questions: {sorted(missing)}")
        return self


# ---------------------------------------------------------------- discovery
class JobLead(BaseModel):
    company: str
    role: str
    url: HttpUrl
    posted_date: Optional[date] = None
    date_verified: bool = Field(False, description="True only if the date was read from the posting page itself")
    why_match: str = Field(min_length=10, description="Requirement-to-evidence reasoning, not keyword overlap")
    flags: list[Flag] = Field(default_factory=list)

    @model_validator(mode="after")
    def _date_logic(self) -> "JobLead":
        if self.date_verified and self.posted_date is None:
            raise ValueError("date_verified without a posted_date")
        return self


class DiscoveryResult(BaseModel):
    searched_on: date
    terms_used: list[str] = Field(min_length=1)
    leads: list[JobLead] = Field(max_length=5)
