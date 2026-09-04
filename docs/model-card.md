# Model card: Consumer Duty Monitoring (`consumer-duty-monitoring`)

**No model runs in this system today, on any profile.** The narration seam exists, is bound in
all three profiles and is fully constrained, but nothing behind it calls a model: the offline
narrator composes sentences deterministically, the managed `GeminiNarrator` raises rather than
generating, and the on-premises adapter is a fail-fast placeholder. This card records the seam as
built, what the pipeline does without it, and the constraints a real narrator would have to meet
before it could be bound.

## The pipeline is deterministic end to end

Every consequential figure and every verdict is pure stdlib. `domain/outcome_tests.py` produces
one `OutcomeTestResult` per family per product (the observed metric, the threshold, the verdict,
the severity, the review requirement) from the signals, the product governance frame and the
consent context, with no clock read inside a method, no randomness, no I/O and no model.
`domain/theme_synthesis.py` counts the breaching and gapped results into themes, and the breach
counts, the products implicated and the signal ids behind them are all computed there. The
severity ladder and the rule-R8 escalation follow from those results. Same inputs and same
`as_of`, byte-identical output.

## Where the narration seam is, and what it may do

- The seam is exactly one port, `ports/narration.py`, whose whole surface is
  `narrate(brief: NarrationBrief) -> Narration | None`. There is no second model seam and no
  classification, extraction or embedding port anywhere in `ports/`.
- The narrator receives an ALREADY-DECIDED, ALREADY-REDACTED brief. It carries counts, verdicts,
  theme titles, the closed set of figures the engine published (`allowed_figures`) and the closed
  set of instruments it cited (`allowed_source_ids`). No raw identifier and no signal detail
  reaches it.
- The draft is checked by `domain/narration.py::grounded_or_fallback`, the single place that
  decision is made. A draft that mentions a figure outside `allowed_figures` is rejected, so an
  invented "97% of customers" is caught because 97 is not in the closed set; citations outside
  `allowed_source_ids` are stripped. A rejected draft is DISCARDED and `deterministic_narration`
  stands.
- **Failure is a first-class answer.** Returning `None` is allowed, and so is RAISING:
  `AssessmentService._narrate` catches any exception and falls back, so an assessment is never
  blocked on a narrator being reachable and a broken managed binding is never invisible.

## Adapters and profiles

| Profile | Narration adapter | Behaviour |
|---|---|---|
| `local` | `adapters/local/narration.py` (`LocalNarrator`) | Deterministic and SDK-free. Composes the same grounded sentences the domain fallback would, drawing only on `brief.allowed_figures` and `brief.theme_titles`, so it passes the grounding gate by construction. It reports `model = "offline-deterministic"`. Its job is to keep the SEAM exercised in the gate, the demo and the eval, and to stand as proof that the gate is not so strict it rejects a correct narration. |
| `gcp` | `adapters/gcp/narration.py` (`GeminiNarrator`) | **Not implemented.** It performs the lazy `from google import genai` import (so the import path and the offline-refusal behaviour are real) and then raises `NotImplementedError` naming `settings.narration_model`. It is listed in `managed_readiness.py` as `narration.GeminiNarrator.narrate`, so a managed process whose bindings include it refuses to start. |
| `onprem` | `adapters/onprem/narration.py` (`OnPremNarrator`) | Fail-fast placeholder: raises, naming the client-hosted model gateway to bind and noting that the assessment stands on its deterministic verdict regardless. |

## What the eval already proves about the seam

`narration_groundedness` runs at a threshold of 1.0 in the offline gate, and it is scored on
ADVERSARIAL drafts constructed inside `eval/run_eval.py` rather than on whatever the bound
narrator produced. The gate is therefore proved able to REJECT before any model exists to reject.
`theme_citation` (threshold 1.0) holds the counting side: every theme must carry a citation the
assessment emitted. Both are proved able to go red in `tests/unit/test_eval_metrics.py`.

## Before a real narrator is bound (TODO, repo owner)

- **Implement `GeminiNarrator.narrate` and integration-test it.** Today it raises, so the request
  shape, the brief-to-prompt mapping and the response-to-`Narration` mapping have never been
  exercised. Add a test under `tests/integration/`, then remove
  `narration.GeminiNarrator.narrate` from `INCOMPLETE_MANAGED_OPERATIONS` and flip
  `managed_profile_implemented` in `infra/terraform/managed_readiness.tf`, in the same reviewed
  commit.
- **Pin the model id properly.** `Settings.narration_model` defaults to `"gemini-3.5-flash"` in
  `config.py`. That is a code default, not a pin and not a verified id: there is no
  `narration_model` key in `config/settings.yaml` and no `CONSUMERDUTY_`-prefixed variable for
  it, so no deployment can currently set it. Add the settings key and the variable, confirm the
  id is actually served in your deployment region, pin the exact model and version, and record it
  here. Gemini model ids are regional and an unavailable one fails at call time rather than at
  boot.
- **Budget, rate limit and a kill switch** (P-10, P-11): there is no per-tenant token budget, no
  request rate limit, and no switch that forces deterministic-only operation. The fallback path
  already exists and is exercised, but nothing yet lets an operator disable a bound narrator
  deliberately.
- **Evaluation of the live model**: add a managed-profile run, registered with the `model-quality-gate` promotion
  gate (P-08, rule R5), that scores `narration_groundedness` against the same golden set with the
  real model bound. The offline score measures the gate, not a model.
- **Prompt-injection screening** (rule R1): the `agent-guardrail-gateway` is not bound. The brief is
  already narrow (counts, verdicts and instrument ids only), which is the strongest single
  defence here, but any future change that widened it to carry verbatim complaint text would make
  screening mandatory before `narration_brief` is built, failing closed to deterministic-only
  when the screen is unavailable.
- **Reasoning trace**: `COMPLIANCE.md` P-07 records that a model's reasoning trace should be
  audited alongside its output. Today the audit record carries the assessment and its citations,
  and there is no prompt and reply pair to record because there is no model call.

Until a narrator is implemented and these controls close, the system runs entirely on its
deterministic path, which is a complete product rather than a degraded mode: the verdicts, the
severities, the theme counts and the escalation are identical either way.
