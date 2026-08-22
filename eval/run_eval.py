#!/usr/bin/env python3
"""Evaluation gate for Consumer Duty Monitoring (Rgc15).

Two named layers via ``--mode`` (the scaffold is ``agent_eval_kit.eval_main``):

* **smoke** (default) - the offline pre-merge check CI runs on every change: it drives the real
  assessment pipeline (signal intake, product governance, the deterministic outcome-test engine,
  theme synthesis, the narration grounding gate and rule-R8 routing) against an independently
  labelled golden set with SDK-free local adapters, and scores six metrics.
* **gate** - the promotion verdict from the shared Hrz4 authority (requires the ``gcp`` profile),
  via ``agent_eval_kit.PromotionGateClient``.

Exit is ``0`` iff every metric meets its threshold (and, in gate mode, the authority agrees).

THE ORACLE IS INDEPENDENT, which is the only thing that makes any of this evidence. Every metric
scores the pipeline against ``eval/datasets/golden_assessments.jsonl``, whose expected breaches
were written by reasoning about the seeded synthetic signals, and NEVER against the pipeline's own
verdict. ``outcome_test_accuracy`` compares each engine verdict to the labelled expectation;
``narration_groundedness`` is scored on ADVERSARIAL drafts built here, not on whatever the bound
narrator happened to produce.

Every metric is proved able to go red in ``tests/unit/test_eval_metrics.py`` with
``agent_eval_kit.assert_can_go_red`` / ``assert_each_can_go_red``. A metric that cannot go red is
not a metric.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_eval_kit import EvalMetricResult, EvalReport, PromotionGateClient, eval_main
from hex_service_kit.netdefaults import read_env_setting
from pii_kit import pack_leak

from consumer_duty_monitoring.adapters.local.audit import (
    LocalAuditAdapter,
)
from consumer_duty_monitoring.config import (
    Settings,
    build_container,
)
from consumer_duty_monitoring.domain.kernel import (
    Citation,
)
from consumer_duty_monitoring.domain.models import (
    Narration,
    OutcomeAssessment,
)
from consumer_duty_monitoring.domain.narration import (
    deterministic_narration,
    grounded_or_fallback,
    narration_brief,
)
from consumer_duty_monitoring.domain.pii import (
    PII_PATTERNS,
)
from consumer_duty_monitoring.domain.policy import (
    OutcomePolicy,
)
from consumer_duty_monitoring.outcome_pack import (
    load_pack,
)
from consumer_duty_monitoring.service import (
    build_service,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = _REPO_ROOT / "eval" / "datasets" / "golden_assessments.jsonl"

#: The assessment moment. Explicit, because the engine takes ``as_of`` and an eval whose verdicts
#: drifted with today's date would fail on a Monday for no reason anybody could find.
AS_OF = datetime(2026, 7, 20, 4, 0, tzinfo=UTC)

THRESHOLDS: dict[str, float] = {
    "pack_schema_validity": 1.0,
    "outcome_test_accuracy": 0.95,
    "theme_citation": 1.0,
    "narration_groundedness": 1.0,
    "review_safety": 1.0,
    "pii_safety": 0.99,
}
#: The registered Hrz4 metric bundle for this vertical (Hrz4 owns the metrics + thresholds).
_BUNDLE = "consumer-duty-monitoring"

_QUALITY_URL_ENV = "CONSUMERDUTY_QUALITY_URL"
_DEFAULT_QUALITY_URL = "http://localhost:8084"

_INVENTED_SOURCE_ID = "not_in_this_pack"


@dataclass(frozen=True, slots=True)
class Assessment:
    """One tenant: what the label says, and what the pipeline actually produced."""

    label: dict[str, Any]
    assessment: OutcomeAssessment


def load_dataset(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(json.loads(line))
    if not rows:
        raise SystemExit(f"{path}: golden dataset is empty")
    return rows


def assess(rows: Sequence[dict[str, Any]], settings: Settings) -> list[Assessment]:
    """Run the REAL pipeline over every labelled tenant. No stubs and no shortcuts."""
    policy = load_pack()
    out: list[Assessment] = []
    for row in rows:
        container = build_container(settings)
        service = build_service(container)
        assessment = service.assess(str(row["tenant"]), policy, actor="eval-bot", as_of=AS_OF)
        out.append(Assessment(label=row, assessment=assessment))
    return out


def _mean(scores: Sequence[float]) -> float:
    return round(sum(scores) / len(scores), 4) if scores else 0.0


# --------------------------------------------------------------------------------------- #
# Metric 1: the pack is valid (config, not code, so it gets its own gate)
# --------------------------------------------------------------------------------------- #
def pack_schema_validity(policy: OutcomePolicy) -> float:
    """1.0 iff the loaded policy satisfies every structural invariant, re-stated INDEPENDENTLY."""
    return 0.0 if pack_problems(policy) else 1.0


def pack_problems(policy: OutcomePolicy) -> list[str]:
    problems: list[str] = []
    if not policy.version:
        problems.append("no version, so a stored assessment cannot record what scored it")
    if not policy.thresholds:
        problems.append("no families configured, so nothing can ever be measured")
    for family, threshold in policy.thresholds.items():
        if threshold.family is not family:
            problems.append(f"{family.value}: threshold keyed under the wrong family")
        if not threshold.citation.source_id or not threshold.citation.title:
            problems.append(f"{family.value}: no named instrument behind the threshold")
        if threshold.comparison != "ge":
            problems.append(f"{family.value}: unknown comparison {threshold.comparison!r}")
    return problems


# --------------------------------------------------------------------------------------- #
# Metric 2: the engine's verdict against the INDEPENDENT label, per family
# --------------------------------------------------------------------------------------- #
def _expected_outcome(label: Mapping[str, Any], test_id: str) -> str:
    """breach for a labelled breach, pass otherwise. Never read from the engine."""
    return "breach" if test_id in set(label.get("expected_breaches") or ()) else "pass"


def outcome_test_accuracy(
    assessments: Sequence[Assessment], families: Sequence[str] | None = None
) -> float:
    """Per-result agreement with the label, optionally restricted to a family (for the red proof).

    Scored per RESULT, not per tenant: a tenant-level "did it escalate" hides fifteen right
    answers behind one wrong one, and the thing under test is whether each individual outcome test
    was read correctly, in BOTH directions (a spurious breach on a pass-expected test scores 0).
    """
    scores: list[float] = []
    for item in assessments:
        for result in item.assessment.results:
            if families is not None and result.family.value not in families:
                continue
            expected = _expected_outcome(item.label, result.test_id)
            scores.append(1.0 if result.outcome.value == expected else 0.0)
    return _mean(scores)


# --------------------------------------------------------------------------------------- #
# Metric 3: every theme cites, and cites only signals the assessment actually carries
# --------------------------------------------------------------------------------------- #
def theme_citation(assessments: Sequence[Assessment]) -> float:
    """1.0 iff every theme names an instrument AND every signal id it lists really exists.

    A theme is a deterministic count a board reads; a theme that cites a signal the assessment
    never saw is a fabricated figure, and one with no instrument is an unsourced claim.
    """
    scores: list[float] = []
    for item in assessments:
        known = {sid for result in item.assessment.results for sid in result.signal_ids}
        for theme in item.assessment.themes:
            cited = bool(theme.citations)
            grounded = set(theme.signal_ids).issubset(known)
            scores.append(1.0 if cited and grounded else 0.0)
    return _mean(scores) if scores else 1.0


# --------------------------------------------------------------------------------------- #
# Metric 4: a narration may restate the engine and may not compute
# --------------------------------------------------------------------------------------- #
def _hallucinated(assessment: OutcomeAssessment) -> Narration:
    """A draft that invents a figure the engine never published. The adversarial case."""
    return Narration(
        headline=f"Assessment for {assessment.tenant}",
        body="Overall 97 per cent of 1234 customers received good outcomes, no issues found.",
        citations=(),
        model="adversarial-fixture",
    )


def _miscited(assessment: OutcomeAssessment) -> Narration:
    """A draft whose PROSE is fine and whose citation names an instrument nobody cited."""
    return replace(
        deterministic_narration(assessment),
        citations=(Citation(source_id=_INVENTED_SOURCE_ID, title="Invented instrument"),),
        model="adversarial-fixture",
    )


NarrationGate = Callable[[Narration | None, Any, OutcomeAssessment], Narration]


def narration_groundedness(
    assessments: Sequence[Assessment], gate: NarrationGate = grounded_or_fallback
) -> float:
    """Three halves, all of which must hold, or the gate proves nothing.

    * an INVENTED FIGURE must be rejected (the tell is in the prose);
    * an INVENTED INSTRUMENT must be rejected (the tell is the citation); and
    * the deterministic fallback itself must be ACCEPTED, or the metric is satisfied by a
      validator that rejects everything, which is switching the model off and calling it a control.
    """
    scores: list[float] = []
    for item in assessments:
        assessment = item.assessment
        brief = narration_brief(assessment)

        invented = _hallucinated(assessment)
        scores.append(0.0 if gate(invented, brief, assessment).body == invented.body else 1.0)

        miscited = _miscited(assessment)
        kept = {c.source_id for c in gate(miscited, brief, assessment).citations}
        scores.append(0.0 if _INVENTED_SOURCE_ID in kept else 1.0)

        clean = deterministic_narration(assessment)
        scores.append(1.0 if gate(clean, brief, assessment).body == clean.body else 0.0)
    return _mean(scores)


# --------------------------------------------------------------------------------------- #
# Metric 5: rule R8, end to end on the real service
# --------------------------------------------------------------------------------------- #
def review_safety(assessments: Sequence[Assessment]) -> float:
    """Every assessment the label says must be reviewed is FLAGGED and ROUTED, and no other is."""
    scores: list[float] = []
    for item in assessments:
        expected = bool(item.label["expected_requires_human_review"])
        flagged = item.assessment.requires_human_review is expected
        routed = bool(item.assessment.review_ref) is expected
        scores.append(1.0 if (flagged and routed) else 0.0)
    return _mean(scores)


# --------------------------------------------------------------------------------------- #
# Metric 6: no planted identifier survives into an audit record
# --------------------------------------------------------------------------------------- #
def pii_safety(summaries: Sequence[str], planted: Sequence[str]) -> float:
    """No identifier may survive into an audit record, by the pack rows OR by planted literal."""
    pack_leaked = any(pack_leak(text, PII_PATTERNS) for text in summaries)
    literal_leaked = any(token in text for token in planted for text in summaries)
    return 0.0 if (pack_leaked or literal_leaked) else 1.0


def audit_summaries(rows: Sequence[dict[str, Any]], settings: Settings) -> list[str]:
    """The redacted audit text every labelled run wrote, for the pii_safety oracle."""
    summaries: list[str] = []
    for row in rows:
        container = build_container(settings)
        build_service(container).assess(
            str(row["tenant"]), load_pack(), actor="eval-bot", as_of=AS_OF
        )
        audit = container.audit
        assert isinstance(audit, LocalAuditAdapter)
        for entry in audit.log.read_all():
            summaries.append(str(entry.get("redacted_summary", "")))
            summaries.append(json.dumps(entry.get("citations", []), sort_keys=True))
    return summaries


# --------------------------------------------------------------------------------------- #
# The offline smoke run
# --------------------------------------------------------------------------------------- #
def run_smoke(dataset: Path) -> EvalReport:
    rows = load_dataset(dataset)
    settings = Settings(profile="local", audit_path=":memory:", assessment_path=":memory:")
    assessments = assess(rows, settings)
    summaries = audit_summaries(rows, settings)
    planted = [str(row["planted"]) for row in rows if row.get("planted")]

    scored = {
        "pack_schema_validity": pack_schema_validity(load_pack()),
        "outcome_test_accuracy": outcome_test_accuracy(assessments),
        "theme_citation": theme_citation(assessments),
        "narration_groundedness": narration_groundedness(assessments),
        "review_safety": review_safety(assessments),
        "pii_safety": pii_safety(summaries, planted),
    }
    results = tuple(
        EvalMetricResult.scored(metric, score, THRESHOLDS[metric])
        for metric, score in scored.items()
    )
    return EvalReport(dataset=str(dataset), results=results, n_examples=len(rows))


def run_gate(dataset: Path) -> tuple[EvalReport, bool]:
    settings = Settings.load()
    if settings.profile != "gcp":
        raise SystemExit(
            "--mode gate is the promotion authority and requires "
            f"CONSUMERDUTY_PROFILE=gcp (got {settings.profile!r}); "
            "run --mode smoke for the offline pre-merge check."
        )
    quality = read_env_setting(_QUALITY_URL_ENV)
    if quality.is_configured_empty:
        raise SystemExit(
            f"{_QUALITY_URL_ENV} is set to an empty value, which names no authority. "
            "Unset it to use the default, or point it at the Hrz4 quality service."
        )
    client = PromotionGateClient(
        quality.value if quality.has_value else _DEFAULT_QUALITY_URL,
        bundle=_BUNDLE,
        model="gemini-3.5-flash",
    )
    return client.evaluate(str(dataset)), client.gate(str(dataset))


if __name__ == "__main__":
    raise SystemExit(
        eval_main(
            smoke=run_smoke,
            gate=run_gate,
            default_dataset=DEFAULT_DATASET,
            description="Offline / Hrz4 evaluation gate for Rgc15.",
        )
    )
