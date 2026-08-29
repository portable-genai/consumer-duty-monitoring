# Adoption FAQ

For an engineering lead forking this repo as their institution's fair-outcomes base. The
step-by-step is [`../ADOPTING.md`](../ADOPTING.md); this answers the "will it hurt later?"
questions.

### How do I rebrand it for my organisation?

`scripts/rename_fork.py` rewrites the package name (`consumer_duty_monitoring`, which is also the
console script, so the `assess` command is renamed with it), the `CONSUMERDUTY_` env prefix
(including the bare token that `infra/terraform/render.tf.json` carries, so Terraform sets the
same variable names on the service), the Terraform `name_prefix` resource stem (`rgc15-svc`) and
the distribution / git id in one pass. Preview with `--dry-run`, apply with `--yes`, then recreate
the venv, `make install`, and run `make gate`. The catalog id `Rgc15` is left alone unless you
pass `--catalog-id`, so a fork stays traceable to the entry it descends from. The script does the
mechanical rename; the human decisions (the outcome pack, the signal feeds, region, IdP, eval
golden set) are the checklist in `ADOPTING.md`.

### If several institutions fork this, how does each take upstream fixes?

Track upstream via **git tags**. The repo declares a core-vs-adopter-owned boundary
(`ADOPTING.md` section 2): upstream owns `domain/kernel.py`, `ports/`, `tests/contract/`, the
eval harness mechanics, CI, the assembly seam in `service.py` and the Terraform stack; you own
`config/settings.yaml` values, the outcome pack in `rulepacks/consumer_duty.yaml`, the fixtures
and golden set, `adapters/onprem/*`, UI theming and `terraform.tfvars`. Rebase your adopter-owned
changes onto each release rather than merging `main` continuously, so conflicts stay in files you
were told to expect.

### What do we have to supply that is not in this repo?

Four things, and none of them is code here:

1. **The outcome-test pack.** `rulepacks/consumer_duty.yaml` ships reference numbers for the four
   families, each citing the regulator instrument it derives from. The numbers are your firm's
   Consumer Duty risk appetite, set on a product review schedule, and your compliance function
   owns them. Point `CONSUMERDUTY_OUTCOME_PACK` at your own file rather than editing the
   reference.
2. **The signal feeds.** `SignalSourcePort` is feed-agnostic on purpose. Offline it serves
   synthetic fixtures for the three built sources (Doc6 complaints and conduct flags, E3
   conversation-QA scorecards, Mkt5 next-best-action outcomes) plus a declared F2 intake fixture.
   Registering a new feed is a new adapter behind the unchanged port, not an engine change.
3. **The product governance records.** `ProductGovernancePort` supplies the product packs,
   approved target markets, fees and benefit scores the tests measure against. The engine never
   learns a product name or a fee as a constant.
4. **The consent and preference store.** An Mkt6 deployment reachable at
   `CONSUMERDUTY_CONSENT_URL`. The managed lookup REFUSES when this is empty rather than
   defaulting to an allow, and the kit synthesises a DENIED decision when the store is
   unreachable, so an unavailable consent state never reads as permission.

Plus the review console: an Hrz7 deployment at `HUMAN_REVIEW_URL`. The managed router REFUSES
to swallow an escalation when this is empty, so a fork cannot ship rule R8 unwired and green.

### How do I add a new outbound dependency (a new port)?

There is a fixed touch list and a contract test that enforces it. A port must be registered in
FIVE places or it runs with no enforcement at all: `ports/__init__.py` (`PORT_PROTOCOLS`),
`config.DEFAULT_BINDINGS`, a `Container` accessor, `config/settings.yaml`, and a `PortCase` in
`tests/contract/canonical.py`. Then bind it in all three families.
`tests/contract/test_port_parity.py` asserts set equality across the five. If the new port is on
the assessment path, wire it in `service.build_service` too: a surface that built a narrower
service would still produce correct assessments and would silently stop honouring rule R8, which
is exactly why that function exists. See [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md).

### Can I retune the thresholds without touching engine code?

For the four outcome-test families, yes, and that is deliberate: they are pack DATA loaded by
`outcome_pack.py` into the frozen `OutcomePolicy` value object in `domain/policy.py`, selected by
`outcome_pack_path` in `config/settings.yaml`. The engine carries no threshold of its own. What is
NOT yet configuration: the PII jurisdiction list in `domain/pii.py` and the eval thresholds in
`eval/run_eval.py` are module constants, and there is no `policy:` block in
`config/settings.yaml` that carries them. That is the open B4 item in
[`../practices-audit.md`](../practices-audit.md). If your compliance function must own those as
configuration too, plan that small addition as part of adoption.

### What stops a managed deployment going live half-built?

`managed_readiness.py` lists the managed operations that are still construction-only (the
BigQuery signal source, the Document AI product governance loader, the Firestore assessment store
and the Gemini narrator), and the API preflight refuses to start a `gcp` process whose active
bindings include one of them. `infra/terraform/managed_readiness.tf` mirrors the same fact and
refuses to plan the serving edge while `managed_profile_implemented` is false. Emptying the tuple
and flipping the Terraform local belong in the same reviewed commit as the integration evidence,
never earlier.

### Does the gate run for my fork out of the box?

Yes. `make gate` is offline, credential-free and network-free (ruff, ruff format, mypy strict,
the whole suite except integration, and the eval), and the CI workflow references no `secrets.`,
so a fork's build is green immediately. This answer used to carry a caveat about dependency
resolution rather than the gate, because `consent-preference-kit` was a private commons and
recreating the locked environment needed a credential for it; the kit has been public in
`portable-genai` since 2026-08-22, so that caveat is gone. Note the eval measures the REFERENCE outcome pack
and golden set until you rebuild them for your own framework; that is an explicit adoption step,
not a silent pass.

### Will the demo rot after I diverge?

It is guarded, and the guard is inside the gate. A demo step lives in `demo.STEPS` and in
`walkthrough.CHECKS`, and `tests/unit/test_demo_surface.py` holds the two equal, so a claim the
demo makes but nobody verifies cannot exist. `make demo-selftest` runs the whole arc headless
over the real loopback server and exits non-zero when a claim stops being true; the demo-gate
workflow runs it, `make portability`, `make demo-static` and `make docs-check` on every push. If
you diverge, keep the step keys and the `facts` dict the checks read.

### The eval reports 1.000. Should we believe it?

Only because each metric is proved able to report something else.
`tests/unit/test_eval_metrics.py` drives `agent_eval_kit.assert_can_go_red` over every metric and
fails the build if one cannot. The oracle is also INDEPENDENT: the expected breaches in
`eval/datasets/golden_assessments.jsonl` were reasoned out from the seeded signals rather than
read back from the pipeline, and `narration_groundedness` is scored on adversarial drafts built
in the harness rather than on whatever the bound narrator happened to produce. Keep both
properties when you rebuild the set for your own framework, or the score stops being evidence.

### What is still open?

[`../practices-audit.md`](../practices-audit.md) carries the per-check verdict and the work list.
The three that matter most before production: implementing the managed feed, store and narration
adapters (nothing deploys until `managed_readiness.py` is empty), binding the Hrz1 guardrail
gateway (needed before untrusted complaint narrative reaches a narrator), and registering this
repo's metric bundle with Hrz4 so `eval/run_eval.py --mode gate` has an authority to ask. The
Terraform stack is written, validated and tested against a mocked provider; it has never been
applied.
