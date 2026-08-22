# Portability FAQ

For architecture, cloud governance and exit planning. The question underneath all of these is
"how do we leave, and how do we know the answer is true today rather than on the day it was
written?"

### What is the lock-in surface?

Every outbound dependency is a `@runtime_checkable` Protocol in `ports/` (assessment store,
audit, consent lookup, evaluation, identity, narration, observability, product governance, signal
source, review router, warehouse export), bound per profile from `config/settings.yaml`. There is
no cloud SDK import anywhere in `domain/`, and the managed adapters import their SDK LAZILY
inside the method, so the other two families import with no SDK installed at all. The one managed
adapter that is NOT a cloud SDK client is `adapters/gcp/consent.py`: the consent kit is pure
stdlib `urllib` with S2S headers, and it is bound under `gcp` only because it makes a real
network call to a sibling service.

### What are the three profiles?

| Profile | What it is | Who it is for |
|---|---|---|
| `local` | SDK-free offline stack: seeded dev personas, a hash-chained SQLite WORM audit log, SQLite assessment store, synthetic signal, product and consent-preference fixtures, a JSON Lines warehouse export, a deterministic narrator | dev, test, CI, and the offline demo |
| `gcp` | the managed stack: IAP identity, Cloud Logging WORM, BigQuery signals and warehouse, Document AI product governance, Firestore assessments, Gemini narration, the real consent client | a managed deployment |
| `onprem` | fail-fast `NotImplementedError` placeholders | the sovereign exit: a client binds its own in-country implementations here |

`CONSUMERDUTY_PROFILE` selects the family. Unset means the offline adapters bind but nobody chose
them, which withdraws every relaxation rather than granting one.

### Is the portability claim tested, or just documented?

Tested, three ways, all in the offline gate or one command:

- `tests/contract/test_port_parity.py` asserts set equality across all five homes of a port (the
  `PORT_PROTOCOLS` map, `config.DEFAULT_BINDINGS`, the `Container` accessor, `settings.yaml` and
  the canonical-call table), so a port cannot be added in four places and run unenforced.
- `tests/contract/test_behavioral_parity.py` proves the offline family ANSWERS, the on-premises
  family RAISES and the managed family REFUSES rather than silently succeeding. A placeholder
  that quietly returned a default would make the exit claim false while looking green.
- `make portability` is the executable claim: named checks with a pass or fail each, ending with
  the no-cloud-SDK probe that BLOCKS the `google` import in a fresh interpreter rather than
  hoping the machine has none installed. It prints what it does NOT prove and exits non-zero on
  any failure.

### How do we actually exit?

[`../onprem-migration.md`](../onprem-migration.md) is the path. The short version: the audit
trail exports to and restores from JSON Lines, so the trail itself is a file copy; the assessment
store keeps each record as plain JSON that `domain/serialization.py` reads back into typed values,
refusing an unknown enum member rather than coercing it to a default; the domain is pure stdlib
and moves unchanged; what you implement is one adapter per port under `adapters/onprem/`, each of
which currently raises with a message naming what to bind.

### What has to be replaced on the way out, specifically?

The narrator (bind your in-country model gateway, or run with the deterministic narration and no
model at all, which changes no figure), the identity adapter (your IdP rather than IAP), the
audit sink (your WORM store), the signal source and product governance adapters (your systems of
record), the assessment store, the warehouse export (your analytics platform) and the review
router (your maker-checker queue). The consent lookup points at whatever the Mkt6 store becomes
in your estate, and stays read-only and fail-closed either way. The evaluation port is the one
that deliberately REFUSES to promote off the managed profile: a promotion certified by a laptop
with no quality service is certified by nothing.

### Can it run with no model at all?

Yes, and that is the load-bearing property rather than a convenience. Every consequential figure
is produced by the deterministic outcome tests and by the counting in
`domain/theme_synthesis.py`, so with the offline narrator bound the verdicts, the severities, the
theme counts and the escalation are identical. `NarrationPort` treats a `None` return and a raise
as first-class answers, and the domain turns either into the deterministic fallback, so an
assessment is never blocked on a model being reachable. The model changes the prose and nothing
else. See [`../model-card.md`](../model-card.md).

### Is the data residency claim portable too?

The region is chosen once and shared by the runtime and Terraform: `config/settings.yaml:region`,
`infra/terraform/render.tf.json:render_region`, and the Terraform `region` / `allowed_regions`
pair, which refuses an unapproved region at plan time. Changing jurisdiction is a configuration
change in those three places plus a re-run of
`infra/terraform/production_edge.tftest.hcl`, not a code change.

### Does the eval move with us?

Yes, and it is worth keeping intact rather than reimplementing. `eval/run_eval.py` pins an
explicit `AS_OF` so verdicts do not drift with the calendar, scores every metric against the
dataset's independently reasoned labels rather than against the pipeline's own output, and builds
adversarial drafts in the harness to score `narration_groundedness`. Those three properties are
what make the number evidence rather than a self-report; a rewrite that scored the pipeline
against itself would look identical and mean nothing.
