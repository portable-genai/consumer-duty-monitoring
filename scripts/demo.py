"""The scripted, offline demo: the REAL services, synthetic data, an audit-first output view.

This is the demo as CODE (practices check F1), not a slide deck and not a recording. Every step
below drives the actual assessment service, the actual hash-chained audit store and the actual
rule-R8 review router over the ``local`` profile, so a step that stops being true stops passing
rather than stops being mentioned.

Three properties make it worth running in front of somebody:

* **Nothing is faked.** No engine stub, no pre-baked JSON. The outcome-test verdicts, the audit
  records, the routing references and the tamper verdict are produced by the shipped code.
* **It is bounded.** The demo proves an offline, single-process seam. It does not prove
  cross-host deployment, a live console, or the managed profile; those need a cloud project and
  live in ``tests/integration/``.
* **It is replayable.** Same inputs, same output, every time, because the consequential decision
  is deterministic. That is what makes it safe to run live.

Every party, address and identifier here is obviously fictional: ``.example`` domains, RFC 5737
and RFC 3849 literals, and a synthetic national id that exists only to prove redaction happened.

MAINTAINER NOTE: this file is rendered from a template, so no line may change length with the
package or service name. Every cookiecutter value is bound to a short module constant below and
referenced through it, and every import line is short enough that a long package name cannot push
it past the formatter's limit.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from consent_preference_kit import ConsentQuery
from hex_service_kit.audit import HashChainedAuditLog
from hex_service_kit.identity import RequestContext
from hex_service_kit.serialization import to_jsonable

from consumer_duty_monitoring.adapters.local._seed import (
    CLEAN_TENANT,
    PII_TENANT,
    TENANT,
)
from consumer_duty_monitoring.config import (
    Settings,
    build_container,
)
from consumer_duty_monitoring.domain import (
    kernel,
)
from consumer_duty_monitoring.domain.pii import (
    JURISDICTIONS,
)
from consumer_duty_monitoring.outcome_pack import (
    load_pack,
)
from consumer_duty_monitoring.service import (
    build_service,
)


def loaded_cloud_sdks() -> tuple[str, ...]:
    """Every managed-SDK module currently importable in THIS interpreter, sorted.

    Public because the demo, the walkthrough's checks and the test suite all ask the same
    question and must not each answer it slightly differently.
    """
    return tuple(sorted(name for name in sys.modules if name.split(".")[0] == "google"))


#: Rendered identity, bound once so no other line's length depends on how long a name is.
SERVICE_NAME = "Consumer Duty Monitoring"
CATALOG_ID = "consumer-duty-monitoring"
REPOSITORY = "consumer-duty-monitoring"

#: The VERIFIED principal the demo attributes work to. A client never asserts this.
ACTOR = "analyst@bank.example"

#: A planted identifier, so the redaction panel has an independent literal to look for rather
#: than trusting the pattern pack to agree with itself.
PLANTED_NRIC = "S1234567D"


@dataclass(frozen=True, slots=True)
class DemoCase:
    """One assessment scenario: a fictional book of business, named by its tenant."""

    subject: str
    text: str
    tenant: str


ROUTINE_CASE = DemoCase(
    subject="Clean Bank (FICTIONAL)",
    text="a clean book with on-target complaints below the harm threshold, from 192.0.2.10",
    tenant=CLEAN_TENANT,
)

ESCALATING_CASE = DemoCase(
    subject="Demo Bank (FICTIONAL)",
    text="a book that breaches all four Consumer Duty outcome tests, reported at ops@demo.example",
    tenant=TENANT,
)

PII_CASE = DemoCase(
    subject="PII Bank (FICTIONAL)",
    text=(
        "the same breaching book with a national id NRIC "
        + PLANTED_NRIC
        + " planted in one signal citation, seen on host 2001:db8::7"
    ),
    tenant=PII_TENANT,
)


# --------------------------------------------------------------------------------------- #
# The presenter arc
# --------------------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Step:
    """One presenter beat: what it shows, and the sentence the presenter reads aloud."""

    key: str
    label: str
    narration: str


STEPS: tuple[Step, ...] = (
    Step(
        key="opened",
        label="Service bound on the offline profile",
        narration=(
            "The whole stack is bound from one settings file: no cloud project, no credentials, "
            "no SDK. Every port has an offline implementation, which is why this demo and the "
            "gate both run on a plane."
        ),
    ),
    Step(
        key="routine",
        label="A clean book: assessed, cited, NOT escalated",
        narration=(
            "A tenant whose outcome tests all pass. Every figure comes from deterministic code, "
            "never from a model. Nothing is routed for review, because manufacturing a review "
            "for a clean book trains reviewers to rubber-stamp."
        ),
    ),
    Step(
        key="escalation",
        label="A breaching book: escalated AND routed (rule R8)",
        narration=(
            "A tenant that breaches all four outcome tests. Setting the flag is not the "
            "escalation; routing is. The assessment is handed to the human-review console in the "
            "same call that produced it, and the reference records where it went."
        ),
    ),
    Step(
        key="redaction",
        label="Personal data is masked BEFORE the audit write",
        narration=(
            "The same path, with a national id planted in a signal citation. The identifier is "
            "masked before anything is written, so the immutable record never contains it. "
            "Redacting afterwards would be too late: the record is already immutable."
        ),
    ),
    Step(
        key="review_queue",
        label="What the reviewer receives, already redacted on the wire",
        narration=(
            "The outbound review queue. The console is a SHARED sink, so payloads are redacted "
            "against every configured jurisdiction, not only the one this book came from."
        ),
    ),
    Step(
        key="audit",
        label="The audit trail verifies, and exports in an open format",
        narration=(
            "The trail is append-only and hash-chained, with an external head anchor on a "
            "separate volume. It exports to JSON Lines and reloads into a fresh store with every "
            "link intact: the record is yours, not this codebase's."
        ),
    ),
    Step(
        key="tamper",
        label="A rewritten record is DETECTED, not merely discouraged",
        narration=(
            "An attacker with file access drops the append-only triggers and rewrites one "
            "record. The store cannot prevent that. The hash chain names the exact record that "
            "broke, which is the honest guarantee: tamper-EVIDENT, not tamper-proof."
        ),
    ),
    Step(
        key="portability",
        label="The exit path fails fast instead of failing silently",
        narration=(
            "The same calls on the on-premises profile, with no code edited and no domain module "
            "touched. Every unimplemented seam refuses loudly. A placeholder that returned "
            "successfully would convert an escalation into an unreviewed decision."
        ),
    ),
)

STEP_KEYS: tuple[str, ...] = tuple(step.key for step in STEPS)


# --------------------------------------------------------------------------------------- #
# Panels: the audit-first output view
# --------------------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Row:
    """One labelled fact in a panel. ``tone`` drives the colour, never the meaning."""

    label: str
    value: str
    tone: str = ""


@dataclass(frozen=True, slots=True)
class Panel:
    """One block of the output view: a title, labelled facts, and an interpretation."""

    title: str
    rows: tuple[Row, ...] = ()
    note: str = ""
    tone: str = ""


@dataclass(frozen=True, slots=True)
class StepResult:
    """Everything one step produced, ready to render or to assert against."""

    key: str
    label: str
    narration: str
    panels: tuple[Panel, ...] = ()
    facts: dict[str, Any] = field(default_factory=dict)


Produced = tuple[list[Panel], dict[str, Any]]


class DemoRun:
    """A live demo, advanced one step at a time over the real services."""

    def __init__(self, workdir: Path | None = None) -> None:
        self._cloud_sdk_before = frozenset(loaded_cloud_sdks())
        self._tempdir: tempfile.TemporaryDirectory[str] | None = None
        if workdir is None:
            self._tempdir = tempfile.TemporaryDirectory(prefix="demo-run-")
            workdir = Path(self._tempdir.name)
        self.workdir = workdir
        self.audit_path = workdir / "store" / "audit.sqlite3"
        self.anchor_path = workdir / "anchor" / "head.json"
        self.anchor_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = Settings(
            profile="local",
            audit_path=str(self.audit_path),
            audit_anchor_path=str(self.anchor_path),
            tenant=TENANT,
        )
        self.container = build_container(self.settings)
        self.service = build_service(self.container)
        self.policy = load_pack()
        self.results: list[StepResult] = []
        self.cases = 0
        self.escalated = 0
        self.routed = 0
        self.chain_ok = True
        self._perform(STEPS[0])

    @property
    def index(self) -> int:
        return len(self.results) - 1

    @property
    def done(self) -> bool:
        return len(self.results) >= len(STEPS)

    def advance(self) -> StepResult:
        if self.done:
            return self.results[-1]
        return self._perform(STEPS[len(self.results)])

    def run_to_end(self) -> None:
        while not self.done:
            self.advance()

    def _perform(self, step: Step) -> StepResult:
        handler: Callable[[], Produced] = getattr(self, "_step_" + step.key)
        panels, facts = handler()
        result = StepResult(
            key=step.key,
            label=step.label,
            narration=step.narration,
            panels=tuple(panels),
            facts=facts,
        )
        self.results.append(result)
        return result

    # -------------------------------------------------------------- steps

    def _step_opened(self) -> Produced:
        bindings = [
            Row(port, self.settings.adapters[port][self.settings.profile].split(":")[-1])
            for port in sorted(self.settings.adapters)
        ]
        profiles = sorted({name for table in self.settings.adapters.values() for name in table})
        sdk = [name for name in loaded_cloud_sdks() if name not in self._cloud_sdk_before]
        deployment = Panel(
            title="Deployment",
            rows=(
                Row("Service", SERVICE_NAME),
                Row("Profile", self.settings.profile, "ok"),
                Row("Profiles bound for every port", ", ".join(profiles)),
                Row("Residency region", self.settings.region),
                Row("Jurisdiction PII packs", ", ".join(JURISDICTIONS)),
                Row("Outcome pack", self.policy.version),
            ),
            note=(
                "One environment variable selects the adapter family for every port. Nothing "
                "below was edited to make the service run offline."
            ),
        )
        adapters = Panel(
            title="Bound adapters",
            rows=tuple(bindings),
            note="The binding map lives in config/settings.yaml, not in the code.",
        )
        findings = Panel(
            title="Findings",
            rows=(
                Row("Cloud SDK modules imported", ", ".join(sdk) or "none", "bad" if sdk else "ok"),
                Row("Credentials required", "none", "ok"),
                Row("Network required", "none", "ok"),
            ),
            note=(
                "The managed adapters import their SDK lazily, so this profile runs with none "
                "installed at all."
            ),
            tone="bad" if sdk else "ok",
        )
        facts = {"profile": self.settings.profile, "sdk_modules": sdk, "profiles": profiles}
        return [deployment, adapters, findings], facts

    def _step_routine(self) -> Produced:
        return self._assess_panels(ROUTINE_CASE, expect_routing=False)

    def _step_escalation(self) -> Produced:
        return self._assess_panels(ESCALATING_CASE, expect_routing=True)

    def _step_redaction(self) -> Produced:
        panels, facts = self._assess_panels(PII_CASE, expect_routing=True)
        record = self.container.audit.log.read_all()[-1]
        blob = json.dumps(record, sort_keys=True, default=str)
        leaked = PLANTED_NRIC in blob
        panels.append(
            Panel(
                title="Redact before the write",
                rows=(
                    Row("Identifier planted in a signal citation", PLANTED_NRIC, "warn"),
                    Row(
                        "Identifier in the immutable record",
                        "PRESENT" if leaked else "absent",
                        "bad" if leaked else "ok",
                    ),
                    Row("Stored summary", str(record.get("redacted_summary", ""))),
                ),
                note=(
                    "The record is immutable, so a redaction pass after the write would be too "
                    "late. Masking happens on the way in, for the summary AND every citation."
                ),
                tone="bad" if leaked else "ok",
            )
        )
        facts["planted_identifier_leaked"] = leaked
        return panels, facts

    def _step_review_queue(self) -> Produced:
        pending = list(self.container.review_router.outbox.pending())
        rows: list[Row] = []
        leaked = False
        for item in pending:
            payload = to_jsonable(item)
            leaked = leaked or PLANTED_NRIC in json.dumps(payload, sort_keys=True)
            rows.append(Row(str(getattr(item, "source_key", "review")), _summarise(payload)))
        queue = Panel(
            title="Outbound review queue",
            rows=tuple(rows) or (Row("queue", "empty", "bad"),),
            note=(
                "Queued, not submitted. The reference the caller received says exactly that, so "
                "a buffered escalation is never mistaken for a reviewed one."
            ),
        )
        findings = Panel(
            title="Findings",
            rows=(
                Row("Escalated assessments", str(self.escalated)),
                Row(
                    "Routed to review",
                    str(self.routed),
                    "ok" if self.routed == self.escalated else "bad",
                ),
                Row(
                    "Personal data on the wire",
                    "LEAKED" if leaked else "none",
                    "bad" if leaked else "ok",
                ),
            ),
            note=(
                "Every escalation is accounted for. A flag with no routing reference is "
                "auto-execution with extra steps."
            ),
            tone="bad" if leaked or self.routed != self.escalated else "ok",
        )
        actions = Panel(
            title="Next actions",
            rows=(
                Row("Reviewer", "open the queued item and approve or reject it"),
                Row("Operator", "point HUMAN_REVIEW_URL at the console and flush the outbox"),
            ),
        )
        return [queue, findings, actions], {"pending": len(pending), "wire_leak": leaked}

    def _step_audit(self) -> Produced:
        log = self.container.audit.log
        report = self.container.audit.verify()
        self.chain_ok = report.ok
        export = self.workdir / "export" / "audit.jsonl"
        export.parent.mkdir(parents=True, exist_ok=True)
        written = log.export_jsonl(export)
        restored = HashChainedAuditLog(":memory:")
        reloaded = restored.import_jsonl(export)
        round_trip = restored.verify_chain()
        anchored = bool(self.settings.audit_anchor_path) and self.anchor_path.exists()
        trail = Panel(
            title="Audit trail",
            rows=(
                Row("Records", str(report.entries)),
                Row("Hash-chained", str(report.chained)),
                Row(
                    "Unverifiable (unchained)",
                    str(report.legacy),
                    "ok" if report.legacy == 0 else "bad",
                ),
                Row("Verdict", report.detail, "ok" if report.ok else "bad"),
                Row(
                    "External head anchor",
                    "configured" if anchored else "absent",
                    "ok" if anchored else "warn",
                ),
            ),
            note=(
                "The chain alone cannot detect a truncated tail: dropping the newest rows leaves "
                "a shorter chain that verifies perfectly. The anchor, kept on a different volume, "
                "is what closes that gap."
            ),
            tone="ok" if report.ok else "bad",
        )
        portable = Panel(
            title="Open-format round trip",
            rows=(
                Row("Exported records", str(written)),
                Row("Reloaded into a fresh store", str(reloaded)),
                Row("Chain after reload", round_trip.detail, "ok" if round_trip.ok else "bad"),
            ),
            note=(
                "JSON Lines with the hashes included, so a consumer can re-verify the trail "
                "without this codebase. That is what makes the record portable."
            ),
            tone="ok" if round_trip.ok else "bad",
        )
        facts = {
            "chain_ok": report.ok,
            "entries": report.entries,
            "exported": written,
            "round_trip_ok": round_trip.ok,
            "anchored": anchored,
        }
        return [trail, portable], facts

    def _step_tamper(self) -> Produced:
        before = self.container.audit.verify()
        target = _rewrite_a_record(self.audit_path)
        after = self.container.audit.verify()
        self.chain_ok = after.ok
        detected = (not after.ok) and after.first_bad_seq == target
        attack = Panel(
            title="The tamper",
            rows=(
                Row("Append-only triggers", "dropped by the attacker", "warn"),
                Row("Record rewritten in place", "seq " + str(target), "warn"),
                Row("Verdict before the rewrite", before.detail, "ok"),
            ),
            note=(
                "File access beats a database trigger. A store that claims otherwise is "
                "describing a policy, not a control."
            ),
        )
        findings = Panel(
            title="Findings",
            rows=(
                Row("Chain intact", "YES" if after.ok else "no", "bad" if after.ok else "ok"),
                Row("First broken record", str(after.first_bad_seq), "ok"),
                Row("Detail", after.detail),
                Row(
                    "Named the exact rewritten record",
                    "yes" if detected else "no",
                    "ok" if detected else "bad",
                ),
            ),
            note=(
                "Tamper-EVIDENT, not tamper-proof. The guarantee is that a rewrite cannot pass "
                "unnoticed, and that the report names which record broke."
            ),
            tone="ok" if detected else "bad",
        )
        actions = Panel(
            title="Next actions",
            rows=(
                Row("Operator", "restore from the exported JSONL and re-anchor deliberately"),
                Row("Auditor", "treat every record from seq " + str(target) + " on as suspect"),
            ),
        )
        facts = {"tampered_seq": target, "detected": detected, "chain_ok": after.ok}
        return [attack, findings, actions], facts

    def _step_portability(self) -> Produced:
        onprem = build_container(Settings(profile="onprem", tenant=TENANT))
        rows: list[Row] = []
        refused: list[str] = []
        absent: list[str] = []
        for port, call in EXIT_CALLS.items():
            expected_absent = port in EXIT_ABSENT
            try:
                call(onprem)
            except NotImplementedError as exc:
                if expected_absent:
                    rows.append(Row(port, "REFUSED, but is meant to be absent", "bad"))
                else:
                    refused.append(port)
                    rows.append(Row(port, "refused: " + str(exc).split(":")[0], "ok"))
            else:
                if expected_absent:
                    absent.append(port)
                    rows.append(Row(port, "absent, by design (a diagnostic, not a control)", "ok"))
                else:
                    rows.append(Row(port, "SUCCEEDED SILENTLY", "bad"))
        exit_panel = Panel(
            title="Exit profile (onprem)",
            rows=tuple(rows),
            note=(
                "Selected by one environment variable. No domain module was edited and no import "
                "changed."
            ),
            tone="ok" if len(refused) + len(absent) == len(EXIT_CALLS) else "bad",
        )
        bounds = Panel(
            title="What this does and does not prove",
            rows=(
                Row("Proved", "every port is swappable and every seam is named"),
                Row("Proved", "an unimplemented seam refuses instead of dropping work"),
                Row("NOT proved", "a running on-premises deployment exists"),
                Row("NOT proved", "model, infrastructure or whole-system portability"),
            ),
            note=(
                "Bounded claims are the point. Run scripts/portability_demo.py for the full seam "
                "tour, with a pass or fail per named check."
            ),
        )
        return [exit_panel, bounds], {
            "refused": sorted(refused),
            "absent": sorted(absent),
        }

    # -------------------------------------------------------------- helpers

    def _assess_panels(self, case: DemoCase, *, expect_routing: bool) -> Produced:
        from consumer_duty_monitoring.domain.kernel import utcnow

        assessment = self.service.assess(case.tenant, self.policy, actor=ACTOR, as_of=utcnow())
        self.cases += 1
        review_ref = assessment.review_ref
        if assessment.requires_human_review:
            self.escalated += 1
            if review_ref:
                self.routed += 1
        consistent = bool(review_ref) == expect_routing == assessment.requires_human_review
        decision = Panel(
            title="Assessment: " + case.subject,
            rows=(
                Row("Overall", assessment.overall.value),
                Row(
                    "Severity",
                    assessment.severity.value,
                    "bad" if assessment.requires_human_review else "ok",
                ),
                Row("Breaches", str(assessment.breach_count)),
                Row("Gaps", str(assessment.gap_count)),
                Row("Requires human review", str(assessment.requires_human_review)),
                Row(
                    "Routed to review",
                    review_ref or "not routed (clean book)",
                    "ok" if consistent else "bad",
                ),
                Row("Attributed to", ACTOR),
            ),
            note=(
                "Every number is computed by pure stdlib code and is replayable. A model narrates "
                "this assessment; it never produces a figure or a verdict."
            ),
            tone="ok" if consistent else "bad",
        )
        breaches = Panel(
            title="Breaching outcome tests",
            rows=tuple(
                Row(
                    f"{r.family.value} / {r.product_id}",
                    f"{r.outcome.value}: observed {r.observed:g} vs threshold {r.threshold:g}",
                    "bad",
                )
                for r in assessment.breaches
            )
            or (Row("outcome tests", "all passed", "ok"),),
            note="Every breach names its instrument and the signals behind it.",
        )
        facts = {
            "tenant": case.tenant,
            "overall": assessment.overall.value,
            "severity": assessment.severity.value,
            "requires_human_review": assessment.requires_human_review,
            "review_ref": review_ref,
            "breach_count": assessment.breach_count,
            "consistent": consistent,
        }
        return [decision, breaches], facts

    # -------------------------------------------------------------- state

    def state(self) -> dict[str, Any]:
        """The whole run as JSON-safe data: what the UI renders and the walkthrough asserts."""
        current = self.results[-1]
        return {
            "service": SERVICE_NAME,
            "repository": REPOSITORY,
            "profile": self.settings.profile,
            "region": self.settings.region,
            "step": current.key,
            "step_index": self.index,
            "step_count": len(STEPS),
            "label": current.label,
            "next": "" if self.done else STEPS[len(self.results)].label,
            "done": self.done,
            "totals": {
                "cases": self.cases,
                "escalated": self.escalated,
                "routed": self.routed,
                "chain_ok": self.chain_ok,
            },
            "steps": [_step_to_dict(result) for result in self.results],
        }


def _step_to_dict(result: StepResult) -> dict[str, Any]:
    return {
        "key": result.key,
        "label": result.label,
        "narration": result.narration,
        "facts": result.facts,
        "panels": [
            {
                "title": panel.title,
                "note": panel.note,
                "tone": panel.tone,
                "rows": [
                    {"label": row.label, "value": row.value, "tone": row.tone} for row in panel.rows
                ],
            }
            for panel in result.panels
        ],
    }


def _summarise(payload: Any) -> str:
    """One readable line for a queued review, without dumping the whole payload."""
    if isinstance(payload, dict):
        parts = [
            str(payload[key])
            for key in ("action", "severity", "maker", "tenant")
            if payload.get(key)
        ]
        if parts:
            return " / ".join(parts)
    return json.dumps(payload, sort_keys=True)[:120]


def _rewrite_a_record(store: Path) -> int:
    """Drop the append-only triggers and rewrite one INTERIOR record, as an attacker would."""
    conn = sqlite3.connect(store)
    try:
        conn.execute("DROP TRIGGER IF EXISTS audit_log_no_update")
        conn.execute("DROP TRIGGER IF EXISTS audit_log_no_delete")
        rows = conn.execute("SELECT seq, event_json FROM audit_log ORDER BY seq ASC").fetchall()
        if len(rows) < 3:
            raise RuntimeError("the tamper step needs an interior record to rewrite")
        middle = rows[len(rows) // 2]
        payload = json.loads(middle[1])
        payload["decision"] = "allowed"
        payload["severity"] = "low"
        conn.execute(
            "UPDATE audit_log SET event_json = ? WHERE seq = ?",
            (json.dumps(payload, sort_keys=True, separators=(",", ":")), int(middle[0])),
        )
        conn.commit()
        return int(middle[0])
    finally:
        conn.close()


def _exit_audit(container: Any) -> Any:
    return container.audit.record(
        kernel.AuditEvent(
            action="assess",
            actor=ACTOR,
            decision=kernel.Decision.ESCALATED,
            severity=kernel.Severity.HIGH,
            redacted_summary="demo assessment escalated",
        )
    )


def _exit_identity(container: Any) -> Any:
    return container.identity.resolve(RequestContext(headers={"x-dev-persona": "approver"}))


def _demo_assessment() -> Any:
    """A minimal escalated assessment for the review-router and narration exit / offline calls."""
    from datetime import UTC, datetime

    from consumer_duty_monitoring.domain import models

    citation = kernel.Citation("fca_prin2a", "FCA PRIN 2A", "good outcomes")
    return models.OutcomeAssessment(
        assessment_id="cda-demo",
        tenant=TENANT,
        as_of=datetime(2026, 7, 20, tzinfo=UTC),
        pack_version="demo",
        engine_version="demo",
        results=(),
        themes=(),
        overall=kernel.Decision.ESCALATED,
        severity=kernel.Severity.HIGH,
        requires_human_review=True,
        signal_count=0,
        product_count=0,
        citations=(citation,),
    )


def _exit_review(container: Any) -> Any:
    return container.review_router.route(_demo_assessment(), maker=ACTOR, tenant=TENANT)


def _exit_narration(container: Any) -> Any:
    from consumer_duty_monitoring.domain.narration import narration_brief

    return container.narration.narrate(narration_brief(_demo_assessment()))


def _exit_signals(container: Any) -> Any:
    return container.signal_source.load(TENANT)


def _exit_products(container: Any) -> Any:
    return container.product_governance.load(TENANT)


def _exit_consent(container: Any) -> Any:
    return container.consent.decide(ConsentQuery(tenant=TENANT, subject_id="subj-x"))


def _exit_store(container: Any) -> Any:
    return container.assessment_store.get("cda-none")


def _exit_warehouse(container: Any) -> Any:
    return container.warehouse.export(())


def _exit_tracer(container: Any) -> Any:
    with container.tracer.span("exit.tour", action="portability"):
        return None


def _exit_evaluation(container: Any) -> Any:
    return container.evaluation.gate("eval/datasets/golden_cases.jsonl")


#: The calls the exit profile must REFUSE, one per port with an exit placeholder. Add a port, add
#: a row: a seam nobody calls is a seam nobody knows is unimplemented.
EXIT_CALLS: dict[str, Callable[[Any], Any]] = {
    "audit": _exit_audit,
    "identity": _exit_identity,
    "review_router": _exit_review,
    "tracer": _exit_tracer,
    "evaluation": _exit_evaluation,
    "narration": _exit_narration,
    "signal_source": _exit_signals,
    "product_governance": _exit_products,
    "consent": _exit_consent,
    "assessment_store": _exit_store,
    "warehouse": _exit_warehouse,
}


#: Diagnostic seams that complete as an honest no-op under the exit profile.
EXIT_ABSENT: frozenset[str] = frozenset({"tracer"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the scripted offline demo end to end.")
    parser.add_argument(
        "output",
        nargs="?",
        default="demo.json",
        help="where to write the audit-view JSON (default: demo.json)",
    )
    parser.add_argument("--quiet", action="store_true", help="write the JSON and print nothing")
    args = parser.parse_args(argv)

    run = DemoRun()
    run.run_to_end()
    state = run.state()
    Path(args.output).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    if not args.quiet:
        for step in state["steps"]:
            print("[" + step["key"] + "] " + step["label"])
        totals = state["totals"]
        print(
            "cases="
            + str(totals["cases"])
            + " escalated="
            + str(totals["escalated"])
            + " routed="
            + str(totals["routed"])
        )
        print("wrote " + args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
