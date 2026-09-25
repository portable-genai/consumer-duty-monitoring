"use client";

import { useEffect, useState } from "react";

// Every request goes to THIS origin. The browser never learns the service's address and never
// holds its credential; the route handler under /api/agent forwards, having discarded whatever
// identity the client tried to assert.
const API = "/api/agent";

// Mirrors the service's seeded local personas. The picker is a DEV convenience: the server
// validates the selection against its own list, so a hand-crafted value cannot invent a persona.
const PERSONAS = ["analyst", "approver", "auditor", "other-tenant"];

// What happened to the human-review hand-off, in the words the user needs. A result that
// escalated but is not queued must say so rather than read as reviewed.
const REVIEW_ROUTING_TEXT: Record<string, string> = {
  routed: "Sent to the review console.",
  failed: "Could not reach the review console; this assessment is not queued for review.",
  off: "Review routing is off in this deployment; this assessment is not queued for review.",
};

// The id of the assessment a response carries, so the console can read it back from the store.
function assessmentIdOf(body: string): string | undefined {
  try {
    const parsed = JSON.parse(body) as { assessment_id?: unknown };
    return typeof parsed.assessment_id === "string" ? parsed.assessment_id : undefined;
  } catch {
    return undefined;
  }
}

function reviewRoutingOf(body: string): string | undefined {
  try {
    const parsed = JSON.parse(body) as { review_routing?: unknown };
    return typeof parsed.review_routing === "string" ? parsed.review_routing : undefined;
  } catch {
    return undefined;
  }
}

interface CardSummary {
  name?: string;
  description?: string;
  skills?: { id: string; name: string }[];
}

export default function Home() {
  const [persona, setPersona] = useState(PERSONAS[0]);
  const [assessmentId, setAssessmentId] = useState("");
  const [result, setResult] = useState("");
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [card, setCard] = useState<CardSummary | null>(null);

  // The service names itself, so this UI carries no hardcoded product name to go stale.
  useEffect(() => {
    let live = true;
    fetch(API + "/.well-known/agent-card.json", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => {
        if (live) setCard(body as CardSummary | null);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  // An assessment covers the verified principal's own tenant, and the tenant comes from identity,
  // so the console sends an empty body: `AssessRequest.tenant` is optional and a tenant typed in
  // the browser would be a client-asserted one.
  async function assess(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFailed(false);
    try {
      const response = await fetch(API + "/v1/assess", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Dev-Persona": persona },
        body: JSON.stringify({}),
      });
      const body = await response.text();
      setFailed(!response.ok);
      setResult(body);
      const stored = response.ok ? assessmentIdOf(body) : undefined;
      if (stored) setAssessmentId(stored);
    } catch (error) {
      setFailed(true);
      setResult(String(error));
    } finally {
      setBusy(false);
    }
  }

  // Reads a stored assessment as the CURRENT persona. The tenant boundary is the service's: a
  // persona from another tenant is answered 403, never the record.
  async function readBack(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFailed(false);
    try {
      const response = await fetch(API + "/v1/assessments/" + encodeURIComponent(assessmentId), {
        cache: "no-store",
        headers: { "X-Dev-Persona": persona },
      });
      const body = await response.text();
      setFailed(!response.ok);
      setResult(body);
    } catch (error) {
      setFailed(true);
      setResult(String(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>{card?.name ?? "Agent console"}</h1>
      <p className="sub">
        {card?.description ??
          "Run a Consumer Duty outcome assessment. The result is deterministic, cited, and routed to a human reviewer when it escalates."}
      </p>

      <form onSubmit={assess}>
        <fieldset>
          <legend>Who you are</legend>
          <label>
            Seeded dev persona (local profile only; the server resolves identity, not this field)
            <select value={persona} onChange={(event) => setPersona(event.target.value)}>
              {PERSONAS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </fieldset>

        <fieldset>
          <legend>Outcome assessment</legend>
          <p className="sub">
            Tests the outcome signals and product governance of this persona&apos;s own tenant. The
            tenant comes from the resolved identity, so there is nothing to type.
          </p>
          <button type="submit" disabled={busy}>
            {busy ? "Working" : "Run the assessment"}
          </button>
        </fieldset>
      </form>

      <form onSubmit={readBack}>
        <fieldset>
          <legend>Read a stored assessment</legend>
          <label>
            Assessment id (filled in by the last run; switch persona to see the tenant boundary)
            <input value={assessmentId} onChange={(event) => setAssessmentId(event.target.value)} />
          </label>
          <button type="submit" disabled={busy || !assessmentId}>
            {busy ? "Working" : "Read it back"}
          </button>
        </fieldset>
      </form>

      {result && REVIEW_ROUTING_TEXT[reviewRoutingOf(result) ?? ""] ? (
        <p className="sub" data-review-routing={reviewRoutingOf(result)}>
          {REVIEW_ROUTING_TEXT[reviewRoutingOf(result) ?? ""]}
        </p>
      ) : null}
      {result ? <pre className={failed ? "result error" : "result"}>{result}</pre> : null}

      <footer>
        Synthetic, obviously fictional data only. Identity is resolved server-side and the
        client-asserted actor is discarded; see ui/README.md for the embedding contract.
      </footer>
    </main>
  );
}
