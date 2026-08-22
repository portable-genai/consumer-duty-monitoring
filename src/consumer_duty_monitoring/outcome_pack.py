"""Loader for the Consumer Duty outcome-test pack (config into domain values).

Lives OUTSIDE ``domain/`` because it reads YAML from disk, and the domain core stays pure stdlib
with no I/O. It turns the reference pack shipped at
``consumer_duty_monitoring/rulepacks/consumer_duty.yaml`` (or an adopter's own file, selected by
``outcome_pack_path`` in ``config/settings.yaml``) into one immutable
:class:`~consumer_duty_monitoring.domain.policy.OutcomePolicy` the engine takes as a parameter.

Why a pack file rather than constants in the engine: the tolerable harm rate, the acceptable
target-market drift, the price-vs-value cutoff and the vulnerable-customer threshold are the
adopting firm's Consumer Duty risk appetite (practice B4), set on a product review schedule, and
each cites the regulator instrument it derives from. Tuning them, or adding a firm's own numbers,
must be a config change a compliance officer can read and diff. The engine never learns a number.

Loading is fail-closed: an unreadable file, an unknown family or severity, a threshold that is not
a number, or a family with no citation raises :class:`OutcomePackError`. A monitor running on a
silently empty or partly-parsed pack would wave outcomes through as unmeasured-but-fine, so it must
not start at all. A family the pack legitimately OMITS is not an error here; it becomes a GAP at
assessment time, which is the fail-closed verdict the engine produces.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, NoReturn

import yaml

from .domain.errors import OutcomePackError
from .domain.kernel import Citation, Severity
from .domain.models import OutcomeTestFamily
from .domain.policy import OutcomePolicy, OutcomeThreshold

DEFAULT_PACK_PATH = Path(__file__).resolve().parent / "rulepacks" / "consumer_duty.yaml"


def _fail(message: str) -> NoReturn:
    raise OutcomePackError(f"outcome pack: {message}")


def _citations(doc: dict[str, Any]) -> dict[str, Citation]:
    raw = doc.get("citations") or {}
    if not isinstance(raw, dict) or not raw:
        _fail("no 'citations' block; every family must name the instrument it comes from")
    out: dict[str, Citation] = {}
    for citation_id, spec in raw.items():
        if not isinstance(spec, dict) or not str(spec.get("title", "")).strip():
            _fail(f"citation {citation_id!r} has no title (a citation must name its instrument)")
        out[str(citation_id)] = Citation(
            source_id=str(citation_id),
            title=str(spec.get("title", "")).strip(),
            snippet=" ".join(str(spec.get("snippet", "")).split()),
        )
    return out


def _severity(value: Any, family: str) -> Severity:
    try:
        return Severity(str(value))
    except ValueError as exc:
        permitted = ", ".join(s.value for s in Severity)
        raise OutcomePackError(
            f"outcome pack: {family}: unknown severity {value!r}; permitted: {permitted}"
        ) from exc


def load_pack(path: str | Path | None = None) -> OutcomePolicy:
    """Load and validate an outcome pack from ``path`` (default: the shipped reference pack)."""
    pack_path = Path(path) if path else DEFAULT_PACK_PATH
    if not pack_path.exists():
        _fail(f"pack file {pack_path} does not exist; the monitor cannot run without it")
    try:
        doc = yaml.safe_load(pack_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise OutcomePackError(f"outcome pack: {pack_path} is not valid YAML: {exc}") from exc
    if not isinstance(doc, dict):
        _fail(f"{pack_path} must contain a mapping")

    version = str(doc.get("version", "")).strip()
    if not version:
        _fail("no 'version'; a stored assessment must record which pack scored it")
    citations = _citations(doc)

    families_block = doc.get("families") or {}
    if not isinstance(families_block, dict) or not families_block:
        _fail("no 'families' block; a pack that configures no test measures nothing")

    thresholds: dict[OutcomeTestFamily, OutcomeThreshold] = {}
    for name, spec in families_block.items():
        try:
            family = OutcomeTestFamily(str(name))
        except ValueError:
            permitted = ", ".join(f.value for f in OutcomeTestFamily)
            _fail(f"unknown family {name!r}; permitted: {permitted}")
        if not isinstance(spec, dict):
            _fail(f"{name}: family entry must be a mapping")
        threshold = spec.get("threshold")
        if not isinstance(threshold, (int, float)):
            _fail(f"{name}: 'threshold' must be a number, got {threshold!r}")
        citation_id = str(spec.get("citation", "") or "")
        if citation_id not in citations:
            _fail(f"{name}: citation {citation_id!r} is not defined in the pack's citations block")
        thresholds[family] = OutcomeThreshold(
            family=family,
            threshold=float(threshold),
            severity=_severity(spec.get("severity", "high"), str(name)),
            citation=citations[citation_id],
        )
    return OutcomePolicy(version=version, thresholds=thresholds)


@lru_cache(maxsize=4)
def _cached_pack(resolved: str) -> OutcomePolicy:
    return load_pack(resolved)


def pack_for(settings: Any) -> OutcomePolicy:
    """Resolve the active policy for ``settings`` (adopter override, else the reference)."""
    configured = (getattr(settings, "outcome_pack_path", "") or "").strip()
    return _cached_pack(configured or str(DEFAULT_PACK_PATH))
