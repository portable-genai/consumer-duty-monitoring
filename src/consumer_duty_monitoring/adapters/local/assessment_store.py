"""Local AssessmentStorePort: SDK-free SQLite store of produced assessments.

The ``local`` profile's stand-in for the managed store (Firestore in the residency region): a
``sqlite3`` table keyed by the assessment's deterministic id, with the tenant lifted into an
indexed column and the whole record kept as plain JSON. Plain JSON rather than a normalised schema
on purpose: a compliance record must be readable by somebody who does not have this service, and a
migration off this platform is a file copy (P-12). The typed values come back through
``domain/serialization.py``, which refuses an unknown outcome or severity rather than defaulting.

Tenant isolation is enforced IN THE QUERY for :meth:`list_for_product`; :meth:`get` is DELIBERATELY
unfiltered, and the domain service compares the record's tenant against the verified principal's
and raises a 403. That split is what makes the cross-tenant denial test meaningful.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from hex_service_kit.serialization import to_jsonable

from ...config import Settings
from ...domain.models import OutcomeAssessment
from ...domain.serialization import assessment_from_jsonable

_DEFAULT_DB_DIR = Path.home() / ".consumer_duty_monitoring"
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "assessments.db"


class LocalAssessmentStore:
    """Serve tenant-scoped assessments from a local SQLite store."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        db_path = (settings.assessment_path or "").strip() or str(_DEFAULT_DB_PATH)
        self._db_path = db_path
        self._lock = threading.RLock()
        self._conn = self._connect(db_path)
        self._init_schema()

    @property
    def db_path(self) -> str:
        return self._db_path

    @staticmethod
    def _connect(db_path: str) -> sqlite3.Connection:
        if db_path not in (":memory:", "") and not db_path.startswith("file:"):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS assessments (
                    id TEXT PRIMARY KEY,
                    tenant TEXT NOT NULL,
                    as_of TEXT NOT NULL DEFAULT '',
                    products TEXT NOT NULL DEFAULT '',
                    document TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS assessments_tenant ON assessments (tenant)"
            )
            self._conn.commit()

    def list_for_product(self, tenant: str, product_id: str) -> tuple[OutcomeAssessment, ...]:
        """Assessments held by ``tenant`` mentioning ``product_id``; the tenant filter is in SQL."""
        if not tenant:
            return ()
        with self._lock:
            rows = self._conn.execute(
                "SELECT document, products FROM assessments WHERE tenant = ? ORDER BY as_of, id",
                (tenant,),
            ).fetchall()
        out = []
        for row in rows:
            products = set(json.loads(row["products"] or "[]"))
            if not product_id or product_id in products:
                out.append(assessment_from_jsonable(json.loads(row["document"])))
        return tuple(out)

    def get(self, assessment_id: str) -> OutcomeAssessment | None:
        """Raw fetch by id: the DOMAIN authorizes the tenant, never this adapter."""
        with self._lock:
            row = self._conn.execute(
                "SELECT document FROM assessments WHERE id = ?", (assessment_id,)
            ).fetchone()
        return None if row is None else assessment_from_jsonable(json.loads(row["document"]))

    def put(self, assessment: OutcomeAssessment) -> str:
        """Upsert one assessment. The id is a digest, so a re-run updates rather than piles up."""
        document = json.dumps(to_jsonable(assessment), sort_keys=True)
        products = json.dumps(sorted({r.product_id for r in assessment.results}))
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO assessments (id, tenant, as_of, products, document) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    assessment.assessment_id,
                    assessment.tenant,
                    assessment.as_of.isoformat(),
                    products,
                    document,
                ),
            )
            self._conn.commit()
        return assessment.assessment_id

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT count(*) AS n FROM assessments").fetchone()
        return int(row["n"])
