"""Minimal stdlib CLI: run an assessment, or verify the audit chain (argparse, no extra deps)."""

from __future__ import annotations

import argparse
import sys

from hex_service_kit.logging import configure_logging

from ..adapters.controls import RecordingReviewRouter
from ..config import build_container
from ..domain.kernel import utcnow
from ..service import build_service, policy_for


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="consumer_duty_monitoring")
    sub = parser.add_subparsers(dest="command", required=True)

    assess_cmd = sub.add_parser("assess", help="Run the Consumer Duty assessment for a tenant.")
    assess_cmd.add_argument("tenant")
    assess_cmd.add_argument("--actor", default="cli-user@bank.example")

    verify_cmd = sub.add_parser("verify-audit", help="Verify the audit chain and anchor.")
    _ = verify_cmd

    args = parser.parse_args(argv)
    container = build_container()
    # Idempotent: a process that is both an API app and a CLI configures once.
    configure_logging(container.settings.profile, service="consumer-duty-monitoring")

    if args.command == "assess":
        routing = RecordingReviewRouter(container.review_router)
        service = build_service(container, review_router=routing)
        assessment = service.assess(
            args.tenant, policy_for(container), actor=args.actor, as_of=utcnow()
        )
        print(
            f"{assessment.assessment_id}: {assessment.overall.value} ({assessment.severity.value})"
        )
        print(
            f"  {assessment.breach_count} breach(es), {assessment.gap_count} gap(s) across "
            f"{assessment.product_count} product(s), {assessment.signal_count} signal(s)"
        )
        for result in assessment.breaches:
            print(f"  - {result.family.value} / {result.product_id}: {result.outcome.value}")
        print(f"  requires_human_review: {assessment.requires_human_review}")
        # Rule R8 on the CLI path too: routed inside the service, not merely printed.
        print(f"  human review hand-off : {routing.outcome.value} {assessment.review_ref}".rstrip())
        return 0

    if args.command == "verify-audit":
        audit = container.audit
        report = audit.verify()  # type: ignore[attr-defined]
        print(f"audit ok={report.ok} entries={report.entries} detail={report.detail}")
        return 0 if report.ok else 1

    return 2  # pragma: no cover - argparse requires a subcommand


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
