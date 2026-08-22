# Security FAQ

For AppSec and security architecture. Every answer names the file that is the evidence, so the
review can read the control rather than the claim.

### Who is the actor on an assessment, and can a caller assert it?

A server-verified `Principal`, always. `AssessRequest` (`api/schemas.py`) has no `actor` field,
and its one `tenant` field can only NARROW to the principal's own tenant, never widen to
another: the audited actor and the review maker both come from the identity adapter, and every
client-supplied actor, tenant, role, ACL and authorization header is discarded at the browser
boundary (`ui/lib/embed-policy.mjs`). Under the `gcp` profile the adapter verifies the
IAP-injected assertion against the configured audience, against IAP's own key set and against the
issuer (`adapters/gcp/identity.py`); an unset or emptied `CONSUMERDUTY_IAP_AUDIENCE` REFUSES
every caller, because `audience=None` means google-auth does not verify the audience at all and
would accept any Google-signed token from any project.

### Can one tenant read another's assessments?

No, and the check is in the DOMAIN rather than in an adapter, so every surface inherits it.
`AssessmentStorePort.list_for_product` takes the tenant and filters on it IN the store, so a
query cannot span tenants; `get` is a raw fetch by id and `domain/assessment_service.py` compares
the record's tenant to the verified principal's, raising `TenantAccessDeniedError`. Every surface
maps that to 403 rather than 404, deliberately: the record exists and this caller may not have
it, and answering 404 would make the store probeable with an id generator.

### What happens if the profile variable goes missing in production?

The process still binds the SDK-free adapters (the alternative is importing cloud SDKs that are
not installed), but nobody chose them, so every relaxation is withdrawn: the seeded dev personas
refuse to construct, no service-to-service scheme is selected, the dev CORS allowlist and the
`X-Dev-Persona` header are gone, the interactive docs are not registered, and the loopback
exposure guard refuses every route to any non-loopback peer. An emptied or mis-capitalised value
raises AT IMPORT, so the process fails to boot rather than serving on a posture nobody chose
(`config.py`, `tests/unit/test_profile_single_source.py`).

### Does setting the service-to-service token open anything?

No, and this is enforced rather than intended. The exposure guard's posture is derived from the
identity BINDING (the adapter declares `VERIFIED` / `CLIENT_ASSERTED` / `UNIMPLEMENTED`), never
from a credential. `CONSUMERDUTY_S2S_TOKEN` authenticates a calling SERVICE and no end user.
`tests/unit/test_end_user_auth_posture.py` walks the guard's argument through the constants it
names and fails the build if a credential reappears at any depth, because it did once: setting
the token switched the guard off for the end-user routes it was protecting.

### Where does personal data go?

It is masked before it crosses any boundary, not once at the end. Redaction runs before the audit
write (`domain/assessment_service.py`), before a review payload leaves the process
(`adapters/_review_payload.py`, against EVERY jurisdiction's rows because the console is a shared
sink), and before a tool result can enter a model's context (`agent/tools.py`). The pattern set
and its ORDER are this vertical's (`domain/pii.py`, national rows first, universal rows last),
drawn from the shared `pii-kit`. The `pii_safety` eval metric holds this at `>= 0.99` and it is
proved able to go red in `tests/unit/test_eval_metrics.py`.

Two boundaries are narrower than the redaction rule alone would make them, on purpose. The
NARRATION brief carries counts, verdicts and instrument ids only, never a raw identifier and
never signal detail, so a model never sees a subject. The WAREHOUSE export takes the flat
`AssessmentRow` projection and never a signal, a subject id or free text
(`ports/warehouse.py`), because analytics rows get joined, copied into notebooks and exported by
people who never saw the retention policy. The evidence stays in the tenant-scoped assessment
store behind the 403.

### What is the most sensitive input here?

The vulnerable-customer test. It reasons about whether a subject flagged as vulnerable was
contacted against a recorded preference, which is a protected characteristic of a real person
joined to a contact event. The consent side is read-only through `ConsentLookupPort` and this
service never records a send and never writes consent. Scope that input with your privacy
function before pointing it at real data.

### Can the model exfiltrate or invent anything?

The model is reachable through exactly one port (`ports/narration.py`) and receives a
`NarrationBrief` that is ALREADY decided and already redacted. `domain/narration.py` validates
the returned draft against the closed set of figures the engine published
(`brief.allowed_figures`) and the closed set of instruments it cited
(`brief.allowed_source_ids`); a draft that mentions a figure the engine did not publish is
DISCARDED and the deterministic narration stands. Returning `None` and RAISING are both
first-class answers, so a broken or unreachable narrator degrades rather than blocking an
assessment. Prompt-injection screening through the Hrz1 guardrail gateway is **not** wired yet,
so a verbatim complaint narrative should not be fed to a narrator until it is (rule R1 in
`COMPLIANCE.md`).

### How is the audit trail protected?

Append-only and hash-chained, AND externally anchored. The chain catches an edit, a deletion or a
reorder; only the anchor catches a TRUNCATED TAIL, because dropping the newest rows leaves a
shorter chain that verifies perfectly. `audit_anchor_path` (`CONSUMERDUTY_AUDIT_ANCHOR`) writes
the chain head to a file on another volume, and `tests/unit/test_audit_anchor.py` proves the
detection, proves the control case goes UNDETECTED without an anchor, and proves an append after
truncation refuses rather than re-anchoring. Under the managed profile the sink is a locked Cloud
Logging bucket (`infra/terraform/logging_worm.tf`), which provides non-rewritability itself.

### What about supply chain?

Both lockfiles are committed and pin every dependency exactly; the catalog commons are pinned to
40-character COMMIT shas rather than tags, because a re-pushed tag changes what installs with no
diff in the lockfile. The base image is digest-pinned, Actions are SHA-pinned, dependabot covers
pip, docker, github-actions and npm, and `pip-audit` plus `npm audit --audit-level=high` are HARD
CI failures. `tests/unit/test_repo_artifacts.py` asserts each of these from inside the repo, and
it asks git whether each pinned sha is a COMMIT object rather than an annotated tag object, which
a regular expression cannot tell apart. Note that `consent-preference-kit` is a private
dependency, so a fork resolving the locks needs a credential for it.

### What is deliberately out of scope?

- **Login.** This repo authenticates nobody itself: the platform in front of it does, and the UI
  forwards the assertion without parsing or trusting a parsed copy.
- **Consent decisions.** Owned by the consent and preference store inside Mkt6, which stays the
  decision authority. This repo reads it read-only and fail-closed.
- **Injection defence and output filtering.** Owned by Hrz1; not bound yet.
- **The review queue.** Owned by Hrz7; this repo produces escalations and routes them.
- **Complaint categorisation, conversation scoring and recommendation outcomes.** Owned by Doc6,
  E3 and Mkt5; this repo consumes their outputs as normalised signals.
- **Network egress control.** VPC-SC governs access to Google APIs across perimeters, not
  arbitrary internet egress. The private-egress rule that lets this service reach the Hrz7
  console and the Mkt6 consent store and nothing else is an adopter network decision, called out
  in `COMPLIANCE.md` P-01.
