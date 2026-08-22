# Adopting this repo as your base

This repository (Rgc15, Consumer Duty Monitoring) is a **common base** that a bank, insurer or
other regulated firm forks to build its own **fair-outcomes monitor**: a service that pulls
complaint, conversation-QA and next-best-action signals into one normalised shape, runs four
deterministic outcome tests per product against the firm's own thresholds, synthesises the
breaches into board-readable themes by counting rather than by asking a model, and routes every
consequential assessment to a human. It ships a reusable hexagonal core (a pure-stdlib domain,
typed ports, three swappable adapter profiles, a green offline gate) plus a fully worked Consumer
Duty vertical you can keep, retune, or replace with your own outcome framework.

This guide is the step-by-step for making it yours. It has two halves: a **mechanical rebrand**
(one script) and the **human decisions** the script cannot make for you.

> Related reading: [`ARCHITECTURE.md`](../ARCHITECTURE.md) (the port table and topology),
> [`CONTRIBUTING.md`](../CONTRIBUTING.md) (adding an adapter, adding a port), the
> [`faq/`](faq/) directory, [`model-card.md`](model-card.md) (the model boundary),
> [`practices-audit.md`](practices-audit.md) (the per-check verdict).

---

## 1. What you keep vs what you rewrite

The core is hexagonal, and the boundary between reusable machinery and the Consumer Duty vertical
is a physical module split with an enforced dependency direction (practices-audit check A7).
`domain/kernel.py` owns the vertical-neutral contracts and imports nothing from the vertical, so
you can import it without loading a line of outcome-test logic; `domain/models.py` holds only the
Rgc15 artifacts and re-exports every kernel name.

| Layer | Where | For a different outcome framework |
|---|---|---|
| **Vertical-neutral machinery** | `domain/kernel.py` (`Citation`, `AuditEvent`, `Severity`, `Decision`, `utcnow`), `domain/errors.py`, every Protocol in `ports/`, the container wiring in `config.py`, the assembly seam in `service.py` | keep untouched |
| **Policy (your numbers and sets)** | the reference pack `src/consumer_duty_monitoring/rulepacks/consumer_duty.yaml` (the harm rate, the drift tolerance, the price-vs-value cutoff and the vulnerable-customer threshold, each citing its instrument, loaded by `outcome_pack.py` into `domain/policy.py`), the jurisdiction list in `domain/pii.py`, the metric thresholds in `eval/run_eval.py` | change deliberately (see section 4) |
| **Vertical (the artifacts themselves)** | the Rgc15 models in `domain/models.py` (`OutcomeSignal`, `SignalSource`, `ProductGovernanceFrame`, `OutcomeTestFamily`, `OutcomeTestResult`, `TestOutcome`, `Theme`, `Narration`, `OutcomeAssessment`), the four kernels in `domain/outcome_tests.py`, the counting in `domain/theme_synthesis.py`, the grounding gate in `domain/narration.py`, `domain/serialization.py`, the local fixtures and the eval golden set | rewrite for your framework |

If your product is another *normalise many feeds, test each entity against a threshold pack,
count the breaches into themes* monitor, most of the hexagon, the three profiles, the
deterministic-verdict pattern, the eval gate and the Hrz7 review routing transfer directly; you
replace the four test kernels and the signal taxonomy, and retune the pack.

## 2. Core-vs-adopter-owned files (so upstream merges stay mechanical)

Upstream keeps evolving these; avoid diverging from them so you can pull fixes cleanly:

- **Upstream-owned** (take our changes): the vertical-neutral machinery listed above, `ports/`,
  `tests/contract/`, the eval harness mechanics (`eval/run_eval.py`), the CI workflows, the
  hexagon wiring (`config.py` `Container` and `service.py`) and the deploy stack in
  `infra/terraform/`.
- **Adopter-owned** (yours; expect to edit): `config/settings.yaml` *values*, the outcome pack
  `rulepacks/consumer_duty.yaml`, the local fixtures and the golden eval dataset,
  `adapters/onprem/*`, UI theming and branding, `infra/terraform/terraform.tfvars`, and the
  regulator crosswalk section of `COMPLIANCE.md`.

Track upstream via git tags; rebase your adopter-owned changes onto each release rather than
merging `main` continuously.

## 3. The mechanical rebrand (one script)

`scripts/rename_fork.py` rewrites the package name (`consumer_duty_monitoring`, which is also the
console script, so `consumer_duty_monitoring assess` becomes your command), the `CONSUMERDUTY_`
env prefix (including the bare `CONSUMERDUTY` that `infra/terraform/render.tf.json` carries so
Terraform sets the same variable names on the service), the cloud resource stem (`rgc15-svc`, the
Terraform `name_prefix`) and the distribution / git id in one pass. Preview first, then apply:

```bash
# Preview (writes nothing):
python scripts/rename_fork.py --package acme_duty_monitor --env-prefix ACME \
    --resource acme-duty --dry-run

# Apply:
python scripts/rename_fork.py --package acme_duty_monitor --env-prefix ACME \
    --resource acme-duty --yes

# Then recreate the environment (the distribution name changed) and prove it is green:
python3.12 -m venv .venv && source .venv/bin/activate
make install
make gate
```

`--dist` defaults to the `--resource` value; pass it explicitly when your git id differs from
your resource stem. `--resource` is validated against the same regex the Terraform `name_prefix`
variable enforces, so a stem the stack would refuse fails here instead of at plan time. Add
`--include-docs` to sweep Markdown prose too. The catalog id `Rgc15` is left alone unless you
pass `--catalog-id`, so a fork stays traceable to the entry it descends from. The script
deliberately does NOT touch the human decisions below.

## 4. The human decisions (the script can't make these)

1. **Region / residency.** The build defaults to `asia-southeast1` (MAS / Singapore), chosen once
   and shared: `config/settings.yaml:region`, `infra/terraform/render.tf.json:render_region` and
   the Terraform `region` / `allowed_regions` pair. Set all of them to your in-country region,
   and re-run the residency tests in `infra/terraform/production_edge.tftest.hcl`, which refuse a
   region outside the allowlist at plan time. See [`runbook.md`](runbook.md).
2. **Identity / IdP.** This repo owns no login flow: the `gcp` profile verifies the IAP-injected
   assertion at the edge, `local` uses seeded dev personas, and `onprem` is a client IdP
   placeholder. Wire your issuer on the deployed service (auth is configured ON the service, not
   in this code) and set `CONSUMERDUTY_IAP_AUDIENCE`. An unset or emptied audience refuses every
   caller rather than verifying without one.
3. **The outcome-test pack (your Consumer Duty risk appetite).**
   `src/consumer_duty_monitoring/rulepacks/consumer_duty.yaml` holds the four families' numbers as
   DATA, each citing the regulator instrument it derives from: the tolerable harm rate, the
   acceptable target-market drift, the price-vs-value cutoff and the vulnerable-customer
   threshold. Point `CONSUMERDUTY_OUTCOME_PACK` at your own file rather than editing the
   reference, and keep the two invariants: loading is fail-closed (an unreadable pack, an unknown
   family or severity, a non-numeric threshold or a family with no citation refuses to boot), and
   a family the pack legitimately OMITS becomes a GAP verdict at assessment time, never a pass. A
   test that measured nothing must never read as an outcome that was checked and found good.
4. **The signal feeds.** Intake is deliberately feed-agnostic: everything maps into one
   `OutcomeSignal` shape behind `SignalSourcePort`. Offline it serves synthetic fixtures for the
   three built sources plus a declared F2 fixture; under `gcp` it reads BigQuery and the sibling
   services. Register your own feeds as new adapters behind the unchanged port, and do not add a
   second normalisation vocabulary. `ProductGovernancePort` is the other inbound edge: your
   product packs, approved target markets, fees and benefit scores. The engine never learns a
   product name or a fee as a constant.
5. **Policy numbers your compliance function owns.** The jurisdiction list in `domain/pii.py`
   (which national PII rows are scanned, and in what order) and the eval thresholds in
   `eval/run_eval.py` (`pack_schema_validity`, `outcome_test_accuracy`, `theme_citation`,
   `narration_groundedness`, `review_safety`, `pii_safety`). Those are module-level today rather
   than a `policy:` settings section (practices-audit check B4); change them deliberately and add
   a test that pins your values. Note that `eval/run_eval.py` also pins an explicit `AS_OF`, so
   verdicts do not drift with today's date; keep that property when you rebuild the golden set.
6. **Reference data is fictional.** Every fixture (`tests/fixtures/sample_cases.py`,
   `adapters/local/_seed.py` including the consent preference fixture, and
   `eval/datasets/golden_assessments.jsonl`) uses obviously fake products, cohorts and subjects.
   Replace them with your own synthetic data. **Do not run against real complaint records,
   conversation transcripts or customer vulnerability flags without your own privacy and conduct
   sign-off**: the vulnerable-customer test reasons about a protected characteristic of a real
   person, which is the most sensitive input in this repo.
7. **Eval golden set.** Rebuild `eval/datasets/golden_assessments.jsonl` for your framework: a
   fork inherits a green gate that measures the WRONG thresholds until you do. The oracle is
   independent by construction (expected breaches were reasoned out from the seeded signals, not
   read back from the pipeline) and `narration_groundedness` is scored on adversarial drafts
   built in the harness; preserve both properties, because they are what makes the score
   evidence.
8. **Deployment posture.** Review the Dockerfile (digest-pinned base, non-root uid 10001),
   `infra/terraform/` (Org Policy, CMEK, a dry-run-first VPC-SC perimeter, the locked WORM log
   bucket) and the loopback-by-default binding before you expose anything. The WORM lock is
   irreversible: confirm `retention_days` before the first apply. Note that
   `infra/terraform/managed_readiness.tf` refuses to plan the serving edge while
   `managed_readiness.py` still lists construction-only managed operations, so implementing the
   BigQuery, Document AI, Firestore and Gemini adapters is a prerequisite for a managed
   deployment, not an optional extra.

## 5. Do not duplicate the platform

This repo is one system in a catalog of composable GRC systems. Several concerns it *touches* are
owned by sibling platform services, and you should integrate rather than rebuild them (see
[`faq/features-faq.md`](faq/features-faq.md) for the full map). The `gcp` profile's adapters are
already thin clients to them:

- **Mkt6** marketing and claims compliance gate: hosts the catalog's consent and preference store
  and remains its decision authority. This repo reads it READ-ONLY through `ConsentLookupPort`
  over the shared `consent-preference-kit` (`CONSUMERDUTY_CONSENT_URL`), never records a send and
  never writes consent. Do not keep a second preference table here.
- **Doc6** complaints and conduct file review: the complaint categorisations and conduct flags
  that arrive as `OutcomeSignal`s. Its categorisation merge rule (deterministic counting is
  authoritative, a model may only phrase it) is the same rule `domain/theme_synthesis.py`
  follows.
- **E3** conversation QA and compliance scorecard: the conversation-QA failures that arrive as
  signals.
- **Mkt5** next-best-action: the recommendation outcomes that arrive as signals.
- **F2** disputes and chargebacks: the complaints-intake feed, DECLARED in the taxonomy
  (`SignalSource.INTAKE`) and exercised from a fixture, but not built. Its adapter registers on
  arrival as configuration, not as an engine change.
- **Hrz7** human-review / maker-checker console: every consequential assessment is routed to it
  over the shared `review-kit` (rule R8); you wire your endpoint
  (`HRZ_HUMAN_REVIEW_URL`), you do not re-implement the console.
- **Hrz4** AI-quality / model-risk gate: owns promotion. `eval/run_eval.py --mode gate` is the
  client half (`CONSUMERDUTY_QUALITY_URL`) and refuses to run off the managed profile.
- **Hrz5** observability plus immutable WORM audit: audit events and trace spans go to it via
  `AuditSinkPort` and `ObservabilityTracerPort` (`OTEL_EXPORTER_OTLP_ENDPOINT` selects the Hrz5
  collector over direct Cloud Trace).
- **Hrz3** agent registry: this agent publishes its A2A card at
  `/.well-known/agent-card.json`; register it rather than inventing a discovery mechanism.

The guardrail gateway (Hrz1) is **not** integrated today. It becomes mandatory the moment
untrusted free text (a verbatim complaint narrative, say) reaches a model: see rule R1 in
[`../COMPLIANCE.md`](../COMPLIANCE.md). The enterprise knowledge base (Hrz2) is likewise
unwired, because nothing here retrieves.

## 6. Adoption checklist

- [ ] Ran `scripts/rename_fork.py`, recreated the venv, `make gate` green.
- [ ] Set the region in all three places (settings, `render.tf.json`, tfvars) and re-ran the
      Terraform residency tests.
- [ ] Wired your IdP audience on the deployed service (this repo owns no login flow).
- [ ] Replaced the outcome pack with your own file behind `CONSUMERDUTY_OUTCOME_PACK`, keeping
      the fail-closed load and the omitted-family-is-a-GAP invariant.
- [ ] Registered your real signal feeds behind `SignalSourcePort` and your product governance
      records behind `ProductGovernancePort`.
- [ ] Pointed `ConsentLookupPort` at your Mkt6 consent and preference store, read-only.
- [ ] Owned the policy numbers (PII jurisdictions, eval thresholds) with your compliance
      function.
- [ ] Replaced every synthetic fixture, including the consent preference fixture.
- [ ] Rebuilt the eval golden set for your framework, keeping the independent oracle and the
      pinned `AS_OF`.
- [ ] Implemented the managed store, feed and narration adapters, emptied
      `INCOMPLETE_MANAGED_OPERATIONS`, and flipped `managed_profile_implemented` in the same
      reviewed commit.
- [ ] Reviewed the deploy posture (Dockerfile, Terraform, `retention_days`, bind address).
- [ ] Wired your Hrz7 review endpoint and decided which sibling services you integrate vs stub.
- [ ] Read [`model-card.md`](model-card.md) and closed its remaining controls before binding a
      real narrator.
- [ ] Recorded your baseline upstream tag so you can take future fixes.
