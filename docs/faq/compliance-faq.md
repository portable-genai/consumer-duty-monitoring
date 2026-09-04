# Compliance FAQ

For compliance, conduct risk, model risk and the second line. The mapping table with a file
reference on every row is [`../../COMPLIANCE.md`](../../COMPLIANCE.md); this page answers the
questions that come back after reading it.

### Is an outcome verdict defensible in front of a regulator?

That is the reason it is pure code. Every observed metric, every threshold comparison, every
verdict and every severity come from `domain/outcome_tests.py`, a stdlib module with no clock
read inside a method, no randomness, no I/O and no model, run against a pinned `as_of`. The same
signals, product frame and consent context reproduce the same assessment years later, and each
result records the metric, the threshold it was compared against and a `Citation` to the
instrument the threshold derives from. Three invariants matter for a review:

- **An unconfigured family is a GAP, not a pass.** A test that measured nothing must never read
  as an outcome that was checked and found good.
- **Unknown consent is a refusal.** A subject the store cannot answer for, or a store that is
  unreachable, is treated as contacted-against-preference when a contact was made.
- **Price vs value is peer-relative and outlier-resistant.** The fee-per-unit-of-value z-score
  uses median and MAD rather than mean and standard deviation, so the very outliers it is
  screening for cannot move the baseline that screens them.

The thresholds shipped here are a REFERENCE, not a legal position: the numbers are your firm's
risk appetite and your conduct function owns them.

### Who signs off a Consumer Duty assessment?

A human, always, for anything consequential. `requires_human_review` and the call to
`ReviewRouterPort.route` are one act, not a flag plus an intention: every surface goes through
`service.build_service` and routes in the same call that produced the result, and
`tests/unit/test_review_routing.py` asserts the routing rather than the flag. A CRITICAL band
demands two approvals (`adapters/_review_payload.py`). Under the managed profile the router
REFUSES when no console is configured, so a deployment cannot swallow an escalation silently. The
eval scores this directly as `review_safety` at a threshold of 1.0.

### Where does the data live, and is residency enforced or just documented?

Enforced at deploy time. The region is chosen once (`asia-southeast1`) and shared by the runtime
and Terraform: `infra/terraform/variables.tf` validates the region against the residency
allowlist at plan, `org_policy.tf` pins `gcp.resourceLocations` to that region's location group,
and every regional resource (the CMEK key ring, the WORM log bucket, the Cloud Run service) is
created in it. `infra/terraform/production_edge.tftest.hcl` is the standing proof: its
`reject_region_outside_the_residency_allowlist` and `residency_defaults_are_in_country` runs fail
if the allowlist stops refusing or a resource drifts off region, and they run against a mocked
provider so they need no project and no credentials.

### What about key management and least privilege?

One REGIONAL CMEK key with a 90-day rotation, and an explicit key binding for EACH service agent
that encrypts under it (Logging, Cloud Run, Vertex AI, Storage), because CMEK does not cascade
(`infra/terraform/kms.tf`). One serving identity holding four roles, each traceable to a bound
adapter, with `logging.logWriter` write only so the process cannot read back the WORM trail it
writes (`iam.tf`). Exportable service-account keys are forbidden by org policy rather than merely
avoided, and a key creation raises an alert if one happens anyway (`org_policy.tf`,
`monitoring.tf`).

### How long is the audit trail kept, and can it be edited?

180 days by default, and the variable refuses anything below 180. The Cloud Logging bucket is
LOCKED by default, which is irreversible: once applied, retention cannot be reduced and the
bucket cannot be deleted for the full window, not even with project-owner rights. Confirm
`retention_days` before the first apply. DATA_READ audit logging is enabled too, so a read of an
assessment is itself recorded: a trail that records who was assessed but not who read the
assessment is half a trail.

Offline the same guarantee is earned differently: the log is hash-chained AND externally
anchored, because a truncated tail leaves a shorter chain that verifies perfectly. The retention
schedule and the legal basis for the trail are adopter-owned. Note the warehouse export is a
SEPARATE retention question with a different answer: it carries the flat `AssessmentRow` and
never a signal, a subject id or free text, precisely so the analytics copy is not a second,
longer-lived store of evidence.

### What personal data does this system process?

Less than the inputs might suggest, and deliberately so. The engine reasons over counts, cohorts,
products and verdicts rather than customer records, and the narration brief carries counts,
verdicts and instrument ids only, so no raw identifier and no signal detail ever reaches a model.
Whatever does appear is masked before every boundary (the audit write, the outbound review
payload, and any tool result that could enter a model's context), with the jurisdiction rows and
their ORDER chosen in `domain/pii.py`. The `pii_safety` metric holds this at `>= 0.99` and is
proved able to go red.

The exception that deserves its own scoping decision is the vulnerable-customer test: it joins a
protected characteristic of a real person to a contact event and a channel preference. It is
read-only on the consent side and this service never records a send or writes consent, but the
input class is still the most sensitive in the repo.

### What model-risk evidence exists?

[`../model-card.md`](../model-card.md) records the model boundary as built, and it is a narrower
boundary than most: no model executes today on any profile. The offline narrator is deterministic
and SDK-free, the managed `GeminiNarrator` raises rather than calling a model, and every figure
comes from the deterministic engine either way. The narration grounding gate
(`domain/narration.py`) is real, tested and scored: `narration_groundedness` runs at a threshold
of 1.0 against adversarial drafts built in the eval harness, so the gate is proved able to reject
before a model is ever bound. What is NOT yet in place: the managed narrator is unimplemented,
its default model id is an untested config default rather than a confirmed pin, there is no token
budget, rate limit or kill switch, no live-model eval run has been registered with the `model-quality-gate`
promotion gate, and prompt-injection screening through `agent-guardrail-gateway` is not bound.

### Which regulations does this claim to satisfy?

None, on your behalf. The mapping in `COMPLIANCE.md` is to the CATALOG's own principles (P-01 to
P-13) and platform rules (R1 to R8). The instrument names in `rulepacks/consumer_duty.yaml` are
cited so a reviewer can trace a threshold to its basis; none of them is legal advice, and the
numbers beside them are adopter policy rather than quoted regulatory limits. The crosswalk from a
catalog row to MAS TRM, CPS 234, CPS 230, HKMA, FCA Consumer Duty or PDPA control ids, and the
judgement that a control is SUFFICIENT for a regulation, is explicitly adopter-owned: it depends
on your risk appetite, your regulator and your existing control library. No row in that document
should be quoted as regulatory assurance, and the second-line review of the deterministic policy
in `domain/` is bank-owned logic rather than a vendor default to inherit unexamined.

### What is still open at go-live?

The `Partial` and `TODO (repo owner)` rows in `COMPLIANCE.md`, each of which names exactly what
is missing. The ones that need a risk acceptance if you go live without them: the
construction-only managed adapters listed in `managed_readiness.py` (which the Terraform edge
gate refuses to serve past), rule R1 (the `agent-guardrail-gateway` binding), rule R5 and P-08 (the `model-quality-gate`
metric bundle), P-10 (timeouts, circuit breaker and a documented kill switch), and P-01's
private-egress rule, which depends on your own network rather than on this repo.
