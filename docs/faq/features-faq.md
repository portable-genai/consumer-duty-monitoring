# Features FAQ

For a product owner, a conduct-risk lead or a delivery manager deciding what this system does,
what it refuses to do, and where its responsibility ends.

### What does it actually do?

Given a tenant, it produces one Consumer Duty assessment in four deterministic stages and one
narrated one:

1. **Intake** (`ports/outcome_signals.py`): complaint categorisations and conduct flags,
   conversation-QA scorecards and next-best-action outcomes, all normalised into ONE
   `OutcomeSignal` shape so the engine reads one vocabulary rather than three feed schemas.
2. **Outcome tests** (`domain/outcome_tests.py`): one `OutcomeTestResult` per family per product,
   each recording the observed metric, the threshold it was compared against, the verdict, the
   severity and whether review is required. The four families are **foreseeable harm** (a
   weighted count of complaint, conduct-flag and QA-failure signals per product),
   **target-market drift** (the fraction of a product's signals whose cohort falls outside its
   approved target market), **price vs value** (fee per unit of value as a robust median-and-MAD
   z-score across the product set, so an expensive-for-what-it-delivers product stands out from
   its peers rather than from an absolute number nobody agreed) and **vulnerable customer** (the
   count of vulnerable subjects contacted against a recorded preference).
3. **Theme synthesis** (`domain/theme_synthesis.py`): the breaching and gapped results grouped
   into one theme per family, with the breach count, the products implicated and the signal ids
   behind them all counted in pure stdlib. A board reads themes, not a hundred rows.
4. **Routing and record**: a consequential assessment sets `requires_human_review` and is routed
   to Hrz7 in the same call, redacted before the audit write, stored, and exported as a flat row.
5. **Narration** (`domain/narration.py` plus `NarrationPort`): a paragraph a board can read. It
   computes nothing.

### What is deterministic, and what does the model write?

Everything consequential is deterministic. Every observed metric, every threshold comparison,
every verdict, every severity, every theme count and the escalation decision are pure stdlib over
the signals, the product frame and the consent context, with no clock read inside a method and no
randomness, so the same inputs and the same `as_of` produce byte-identical results. The model
receives a `NarrationBrief` that is already decided, and its draft is validated against the closed
set of figures the engine published and the closed set of instruments it cited; a draft that
invents a figure is discarded and the deterministic narration stands. With the offline narrator
bound, every consequential field is identical. See [`../model-card.md`](../model-card.md).

### What will it refuse to do?

- **It will not read an unconfigured test as a pass.** A family the outcome pack does not
  configure produces a GAP verdict, never a pass. A test that measured nothing must not read as
  an outcome that was checked and found good.
- **It will not start on a broken pack.** An unreadable pack, an unknown family or severity, a
  non-numeric threshold or a family with no citation raises `OutcomePackError` at load.
- **It will not read unknown consent as permission.** A subject the consent store refuses, or a
  store that is unreachable, is treated as contacted-against-preference when a contact was in
  fact made. Reading an unknown or unavailable consent state as permission is the precise error a
  Consumer Duty monitor must not make.
- **It will not let one tenant read another's assessments.** `get` is a raw fetch and the DOMAIN
  compares the record's tenant to the verified principal's, denying with 403 rather than 404.
- **It will not put evidence in the warehouse.** The export carries the flat `AssessmentRow` and
  never a signal, a subject id or free text.
- **It will not answer without provenance.** Every result and every theme carries a `Citation`,
  and a reloaded record refuses an unknown enum member rather than coercing it to a default.

### Which surfaces expose it?

Five, and they behave the same because they share one domain service built through
`service.build_service` rather than reimplementing it: the FastAPI app (`POST /v1/assess`,
`GET /v1/assessments/{assessment_id}`), the argparse CLI (`consumer_duty_monitoring assess
<tenant>`, `verify-audit`), the agent tools (`run_assessment`, `verify_audit_trail`, advertised
on the A2A card at `/.well-known/agent-card.json`), the embeddable `ui/` micro-frontend, and the
eval harness. No surface may build a narrower service: one that forgot the review router would
still produce correct assessments and would silently stop honouring rule R8.

### What does this repo own, and what does it integrate?

| Concern | Owner | How this repo touches it |
|---|---|---|
| The four outcome tests, the theme counting and the assessment record | **Rgc15 (this repo)** | owned outright: `domain/outcome_tests.py`, `domain/theme_synthesis.py`, `domain/models.py`. |
| Consent, channel preferences and the decision authority over them | **Mkt6** marketing and claims compliance gate (hosts the consent and preference store) | READ-ONLY over `ConsentLookupPort` through the shared `consent-preference-kit` (`CONSUMERDUTY_CONSENT_URL`). This repo never records a send and never writes consent. |
| Complaint categorisation and conduct flags | **Doc6** complaints and conduct file review | consumed as normalised `OutcomeSignal`s. Its deterministic-counting-is-authoritative merge rule is the one `theme_synthesis.py` follows. |
| Conversation QA scoring | **E3** conversation QA and compliance scorecard | consumed as normalised signals. |
| Next-best-action outcomes | **Mkt5** next-best-action | consumed as normalised signals. |
| Complaints intake | **F2** disputes and chargebacks | DECLARED in the taxonomy (`SignalSource.INTAKE`) and exercised from a fixture; not built. Its adapter registers on arrival as configuration, not as an engine change. |
| Human review and maker-checker | **Hrz7** human review console | `ReviewRouterPort` over the shared `review-kit` (`HUMAN_REVIEW_URL`). This repo produces escalations; it does not render a queue. |
| Model and agent promotion | **Hrz4** AI quality and model risk | `eval/run_eval.py --mode gate` asks Hrz4 (`CONSUMERDUTY_QUALITY_URL`); the offline smoke mode never promotes. |
| Traces and the immutable audit sink | **Hrz5** agent observability | `AuditSinkPort` and `ObservabilityTracerPort`; `OTEL_EXPORTER_OTLP_ENDPOINT` selects the Hrz5 collector. |
| Agent discovery and entitlements | **Hrz3** agent registry | this agent publishes a card; the registry owns discovery. |
| Prompt-injection defence and output filtering | **Hrz1** agent guardrail gateway | **not wired today.** It becomes mandatory the moment untrusted free text reaches a narrator (rule R1). |
| Grounded retrieval over an enterprise corpus | **Hrz2** enterprise knowledge base | not wired today; nothing here retrieves. |

### Can I demo it without a cloud project?

Yes, and the demo is code rather than a deck. `make demo` runs a presenter-paced walkthrough over
eight steps (opened, routine, escalation, redaction, review queue, audit, tamper, portability) on
its own loopback server; `make demo-selftest` runs the same arc headless and asserts every
narrated claim, so a claim that stops being true fails a build rather than a meeting;
`make demo-static` renders the same audit-first panels to static HTML for screenshots.

### What is not built yet?

The honest list is [`../practices-audit.md`](../practices-audit.md) and the `TODO (repo owner)`
rows in [`../../COMPLIANCE.md`](../../COMPLIANCE.md). The three that matter most for a production
decision: every managed feed, store and narration adapter is still construction-only (they are
listed in `managed_readiness.py`, and the Terraform refuses to plan a serving edge while that
list is non-empty), the Hrz1 guardrail binding is unwired, and this repo's metric bundle is not
yet registered with Hrz4 so `--mode gate` has no authority to ask. The F2 intake feed is declared
rather than integrated, which is deliberate and visible in the taxonomy.
