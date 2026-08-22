"""One obviously-synthetic dataset the offline adapters share, so ids line up across ports.

The ``local`` signal source, product governance and consent adapters all read from here, so the
subject a vulnerability cue names is the same subject the contact-outcome names and the same
subject the consent fixture denies. A dataset split across three files drifts the first time one
is edited.

Every party is fictional, every product code is invented, every subject id is a synthetic
pseudonym (never a real identifier), and the single tenant is ``duty-bank``. The dataset is
designed to breach all four outcome tests exactly once, so the demo and the eval have a
deterministic, interesting assessment to reason about.
"""

from __future__ import annotations

from dataclasses import replace

from ...domain.kernel import Citation
from ...domain.models import (
    OutcomeSignal,
    ProductGovernanceFrame,
    ProductProfile,
    SignalKind,
    SignalSource,
)

TENANT = "demo-bank"

#: A vulnerable subject contacted against preference (the consent fixture denies this id).
VULNERABLE_SUBJECT = "subj-9001"
#: A subject whose consent IS an allow, present so the allow path is exercised too.
CONSENTED_SUBJECT = "subj-9002"

_PRODUCTS: tuple[ProductProfile, ...] = (
    ProductProfile(
        product_id="P-SAVE-01",
        name="Everyday Saver (FICTIONAL)",
        target_cohorts=("mass_market", "students"),
        annual_fee=12.0,
        benefit_score=80.0,
        citation=Citation("prod:P-SAVE-01", "Product pack: Everyday Saver", "target: mass market"),
    ),
    ProductProfile(
        product_id="P-LOAN-02",
        name="Flexi Loan (FICTIONAL)",
        target_cohorts=("mass_market",),
        annual_fee=200.0,
        benefit_score=10.0,
        citation=Citation("prod:P-LOAN-02", "Product pack: Flexi Loan", "target: mass market"),
    ),
    ProductProfile(
        product_id="P-INV-03",
        name="Growth ISA (FICTIONAL)",
        target_cohorts=("affluent",),
        annual_fee=90.0,
        benefit_score=60.0,
        citation=Citation("prod:P-INV-03", "Product pack: Growth ISA", "target: affluent"),
    ),
    ProductProfile(
        product_id="P-PKG-04",
        name="Packaged Account (FICTIONAL)",
        target_cohorts=("mass_market",),
        annual_fee=180.0,
        benefit_score=40.0,
        citation=Citation("prod:P-PKG-04", "Product pack: Packaged Account", "target: mass market"),
    ),
)


def _c(source_id: str, title: str, snippet: str) -> Citation:
    return Citation(source_id=source_id, title=title, snippet=snippet)


_SIGNALS: tuple[OutcomeSignal, ...] = (
    # P-SAVE-01: a vulnerable subject contacted against preference (vulnerable-customer breach).
    OutcomeSignal(
        signal_id="e3-scr-001",
        source=SignalSource.CONVERSATION_QA,
        kind=SignalKind.VULNERABILITY_CUE,
        tenant=TENANT,
        product_id="P-SAVE-01",
        cohort="mass_market",
        subject_id=VULNERABLE_SUBJECT,
        observed_date="2026-06-02",
        citation=_c(
            "e3:scorecard:001", "E3 scorecard vulnerability cue", "cue: financial hardship"
        ),
    ),
    OutcomeSignal(
        signal_id="mkt5-nba-001",
        source=SignalSource.NEXT_BEST_ACTION,
        kind=SignalKind.CONTACT_OUTCOME,
        tenant=TENANT,
        product_id="P-SAVE-01",
        cohort="mass_market",
        subject_id=VULNERABLE_SUBJECT,
        channel="sms",
        observed_date="2026-06-03",
        citation=_c("mkt5:nba:001", "Mkt5 next-best-action outcome", "contacted on sms"),
    ),
    # P-LOAN-02: expensive for what it delivers (price-vs-value breach), plus an F2 intake signal.
    OutcomeSignal(
        signal_id="doc6-cmp-010",
        source=SignalSource.COMPLAINTS,
        kind=SignalKind.COMPLAINT,
        tenant=TENANT,
        product_id="P-LOAN-02",
        cohort="mass_market",
        observed_date="2026-06-05",
        citation=_c(
            "doc6:complaint:010", "Doc6 complaint categorisation", "category: fees_charges"
        ),
    ),
    OutcomeSignal(
        signal_id="f2-intake-001",
        source=SignalSource.INTAKE,
        kind=SignalKind.COMPLAINT,
        tenant=TENANT,
        product_id="P-LOAN-02",
        cohort="mass_market",
        observed_date="2026-06-06",
        citation=_c("f2:intake:001", "F2 intake (declared fixture; feed not yet built)", "fees"),
    ),
    # P-INV-03: mostly sold outside its affluent target market (target-market-drift breach).
    OutcomeSignal(
        signal_id="doc6-cmp-020",
        source=SignalSource.COMPLAINTS,
        kind=SignalKind.COMPLAINT,
        tenant=TENANT,
        product_id="P-INV-03",
        cohort="mass_market",
        observed_date="2026-06-07",
        citation=_c("doc6:complaint:020", "Doc6 complaint categorisation", "category: mis_selling"),
    ),
    OutcomeSignal(
        signal_id="e3-scr-020",
        source=SignalSource.CONVERSATION_QA,
        kind=SignalKind.QA_FAILURE,
        tenant=TENANT,
        product_id="P-INV-03",
        cohort="students",
        observed_date="2026-06-08",
        citation=_c("e3:scorecard:020", "E3 scorecard failing requirement", "risk warning absent"),
    ),
    OutcomeSignal(
        signal_id="mkt5-nba-020",
        source=SignalSource.NEXT_BEST_ACTION,
        kind=SignalKind.CONTACT_OUTCOME,
        tenant=TENANT,
        product_id="P-INV-03",
        cohort="affluent",
        subject_id=CONSENTED_SUBJECT,
        channel="email",
        observed_date="2026-06-09",
        citation=_c("mkt5:nba:020", "Mkt5 next-best-action outcome", "contacted on email"),
    ),
    # P-PKG-04: high complaint and conduct-flag volume (foreseeable-harm breach).
    OutcomeSignal(
        signal_id="doc6-cmp-030",
        source=SignalSource.COMPLAINTS,
        kind=SignalKind.COMPLAINT,
        tenant=TENANT,
        product_id="P-PKG-04",
        cohort="mass_market",
        observed_date="2026-06-10",
        citation=_c("doc6:complaint:030", "Doc6 complaint categorisation", "category: service"),
    ),
    OutcomeSignal(
        signal_id="doc6-cmp-031",
        source=SignalSource.COMPLAINTS,
        kind=SignalKind.COMPLAINT,
        tenant=TENANT,
        product_id="P-PKG-04",
        cohort="mass_market",
        observed_date="2026-06-11",
        citation=_c("doc6:complaint:031", "Doc6 complaint categorisation", "category: service"),
    ),
    OutcomeSignal(
        signal_id="doc6-cmp-032",
        source=SignalSource.COMPLAINTS,
        kind=SignalKind.COMPLAINT,
        tenant=TENANT,
        product_id="P-PKG-04",
        cohort="mass_market",
        observed_date="2026-06-12",
        citation=_c(
            "doc6:complaint:032", "Doc6 complaint categorisation", "category: fees_charges"
        ),
    ),
    OutcomeSignal(
        signal_id="doc6-flag-030",
        source=SignalSource.COMPLAINTS,
        kind=SignalKind.CONDUCT_FLAG,
        tenant=TENANT,
        product_id="P-PKG-04",
        cohort="mass_market",
        observed_date="2026-06-12",
        citation=_c("doc6:conduct:030", "Doc6 conduct flag", "systemic_issue"),
    ),
    OutcomeSignal(
        signal_id="doc6-flag-031",
        source=SignalSource.COMPLAINTS,
        kind=SignalKind.CONDUCT_FLAG,
        tenant=TENANT,
        product_id="P-PKG-04",
        cohort="mass_market",
        observed_date="2026-06-13",
        citation=_c("doc6:conduct:031", "Doc6 conduct flag", "regulatory_breach"),
    ),
)

#: Consent decisions the offline consent adapter returns, keyed by subject id. The vulnerable
#: subject is opted out on sms; the other subject has granted consent. A subject not listed is
#: unknown, which the adapter reads as a refusal (fail-closed, like the kit itself).
CONSENT_FIXTURE: dict[str, tuple[str, tuple[str, ...]]] = {
    VULNERABLE_SUBJECT: ("denied", ("channel_opted_out",)),
    CONSENTED_SUBJECT: ("allowed", ("consent_granted", "channel_opted_in")),
}


#: A demo tenant with a clean book: products at similar value and a couple of on-target
#: complaints below the harm threshold, so no outcome test breaches (the routine beat).
CLEAN_TENANT = "clean-bank"

_CLEAN_PRODUCTS: tuple[ProductProfile, ...] = (
    ProductProfile(
        product_id="C-SAVE-01",
        name="Simple Saver (FICTIONAL)",
        target_cohorts=("mass_market", "students"),
        annual_fee=10.0,
        benefit_score=80.0,
        citation=Citation("prod:C-SAVE-01", "Product pack: Simple Saver", "target: mass market"),
    ),
    ProductProfile(
        product_id="C-CARD-02",
        name="Fair Card (FICTIONAL)",
        target_cohorts=("mass_market",),
        annual_fee=14.0,
        benefit_score=70.0,
        citation=Citation("prod:C-CARD-02", "Product pack: Fair Card", "target: mass market"),
    ),
)

_CLEAN_SIGNALS: tuple[OutcomeSignal, ...] = (
    OutcomeSignal(
        signal_id="clean-cmp-001",
        source=SignalSource.COMPLAINTS,
        kind=SignalKind.COMPLAINT,
        tenant=CLEAN_TENANT,
        product_id="C-SAVE-01",
        cohort="mass_market",
        observed_date="2026-06-04",
        citation=_c("doc6:complaint:900", "Doc6 complaint categorisation", "category: service"),
    ),
    OutcomeSignal(
        signal_id="clean-cmp-002",
        source=SignalSource.COMPLAINTS,
        kind=SignalKind.COMPLAINT,
        tenant=CLEAN_TENANT,
        product_id="C-CARD-02",
        cohort="mass_market",
        observed_date="2026-06-05",
        citation=_c("doc6:complaint:901", "Doc6 complaint categorisation", "category: service"),
    ),
)

#: A demo tenant identical to the breaching book but with a national id planted in one signal
#: citation, so the redaction beat has an independent literal to prove was masked before the write.
PII_TENANT = "pii-bank"
PLANTED_NRIC = "S1234567D"


def _pii_signals() -> tuple[OutcomeSignal, ...]:
    out: list[OutcomeSignal] = []
    for index, signal in enumerate(_SIGNALS):
        citation = signal.citation
        if index == 0 and citation is not None:
            citation = Citation(
                source_id=citation.source_id,
                title=citation.title,
                snippet=f"cue noted for NRIC {PLANTED_NRIC}",
            )
        out.append(replace(signal, tenant=PII_TENANT, citation=citation))
    return tuple(out)


def seed_signals(tenant: str) -> tuple[OutcomeSignal, ...]:
    """Every synthetic signal for ``tenant`` (empty for any tenant but the seeded ones)."""
    if tenant == TENANT:
        return _SIGNALS
    if tenant == CLEAN_TENANT:
        return _CLEAN_SIGNALS
    if tenant == PII_TENANT:
        return _pii_signals()
    return ()


def seed_frame(tenant: str) -> ProductGovernanceFrame:
    """The synthetic product governance frame for ``tenant`` (empty for any other tenant)."""
    if tenant == TENANT:
        return ProductGovernanceFrame(tenant=TENANT, products=_PRODUCTS)
    if tenant == CLEAN_TENANT:
        return ProductGovernanceFrame(tenant=CLEAN_TENANT, products=_CLEAN_PRODUCTS)
    if tenant == PII_TENANT:
        return ProductGovernanceFrame(tenant=PII_TENANT, products=_PRODUCTS)
    return ProductGovernanceFrame(tenant=tenant, products=())
