"use client";

import { useMemo, useRef, useState } from "react";

type RiskLevel = "low" | "medium" | "high";
type RunStatus = "completed" | "waiting_approval" | "rejected" | "blocked" | "failed";
type ScenarioName = "low" | "high" | "blocked";

type CandidateAction = {
  action_id: string;
  name: string;
  tool: string;
  operation: string;
  payload: Record<string, unknown>;
  expected_value: number;
  risk: RiskLevel;
  reversible: boolean;
  evidence: string[];
  required_permissions: string[];
};

type RunPayload = {
  idempotency_key: string;
  goal: string;
  observation: Record<string, unknown>;
  contract: {
    version: string;
    allowed_action_ids: string[];
    granted_permissions: string[];
  };
  candidates: CandidateAction[];
};

type DecisionTrace = {
  run_id: string;
  created_at: string;
  updated_at: string;
  revision: number;
  idempotency_key?: string | null;
  goal: string;
  observation: Record<string, unknown>;
  observation_fingerprint: string;
  request_fingerprint: string;
  contract_version: string;
  candidates: CandidateAction[];
  eligible_action_ids: string[];
  selected_action: CandidateAction | null;
  rejected_actions: { action_id: string; reasons: string[] }[];
  policy_checks: { rule: string; passed: boolean; details: Record<string, unknown> }[];
  approval: {
    decision: "approve" | "reject";
    approver: string;
    reason: string;
    decided_at: string;
  } | null;
  events: { event_type: string; at: string; details: Record<string, unknown> }[];
  status: RunStatus;
  result: Record<string, unknown>;
  error: { error_type: string; message: string } | null;
  execution_count?: number;
  idempotency_replayed?: boolean;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
const allowedTools = new Set([
  "support_api.reply",
  "support_api.escalate",
  "billing_api.refund",
]);
const riskOrder: Record<RiskLevel, number> = { low: 0, medium: 1, high: 2 };

const scenarios: Record<ScenarioName, RunPayload> = {
  low: {
    idempotency_key: "demo-low-001",
    goal: "Resolve a customer support request",
    observation: { ticket_id: "T-100", customer_tier: "standard" },
    contract: {
      version: "support-v1",
      allowed_action_ids: ["reply", "escalate"],
      granted_permissions: ["ticket:write"],
    },
    candidates: [
      {
        action_id: "reply",
        name: "Send approved response",
        tool: "support_api",
        operation: "reply",
        payload: { ticket_id: "T-100", message: "Your request has been resolved." },
        expected_value: 0.8,
        risk: "low",
        reversible: true,
        evidence: ["knowledge-base/article-12"],
        required_permissions: ["ticket:write"],
      },
      {
        action_id: "escalate",
        name: "Escalate to operator",
        tool: "support_api",
        operation: "escalate",
        payload: { ticket_id: "T-100", queue: "tier-2" },
        expected_value: 0.5,
        risk: "low",
        reversible: true,
        evidence: [],
        required_permissions: ["ticket:write"],
      },
    ],
  },
  high: {
    idempotency_key: "demo-high-001",
    goal: "Issue a policy-compliant refund",
    observation: { ticket_id: "T-101", refund_amount: 12000, currency: "JPY" },
    contract: {
      version: "billing-v1",
      allowed_action_ids: ["refund"],
      granted_permissions: ["refund:write"],
    },
    candidates: [
      {
        action_id: "refund",
        name: "Issue refund",
        tool: "billing_api",
        operation: "refund",
        payload: { ticket_id: "T-101", amount: 12000, currency: "JPY" },
        expected_value: 0.9,
        risk: "high",
        reversible: false,
        evidence: ["ticket/T-101/refund-policy"],
        required_permissions: ["refund:write"],
      },
    ],
  },
  blocked: {
    idempotency_key: "demo-blocked-001",
    goal: "Prove invalid actions cannot execute",
    observation: { ticket_id: "T-102" },
    contract: {
      version: "support-v1",
      allowed_action_ids: ["reply", "refund-no-evidence", "unknown-tool"],
      granted_permissions: ["ticket:read"],
    },
    candidates: [
      {
        action_id: "delete-account",
        name: "Delete account outside contract",
        tool: "support_api",
        operation: "delete",
        payload: { customer_id: "C-9" },
        expected_value: 1,
        risk: "high",
        reversible: false,
        evidence: ["request/9"],
        required_permissions: ["account:delete"],
      },
      {
        action_id: "reply",
        name: "Reply without permission",
        tool: "support_api",
        operation: "reply",
        payload: { ticket_id: "T-102", message: "Resolved" },
        expected_value: 0.8,
        risk: "low",
        reversible: true,
        evidence: [],
        required_permissions: ["ticket:write"],
      },
      {
        action_id: "refund-no-evidence",
        name: "High-risk refund without evidence",
        tool: "billing_api",
        operation: "refund",
        payload: { ticket_id: "T-102", amount: 3000 },
        expected_value: 0.7,
        risk: "high",
        reversible: false,
        evidence: [],
        required_permissions: [],
      },
      {
        action_id: "unknown-tool",
        name: "Call unregistered tool",
        tool: "shadow_api",
        operation: "exfiltrate",
        payload: { record_id: "R-1" },
        expected_value: 0.6,
        risk: "low",
        reversible: true,
        evidence: [],
        required_permissions: [],
      },
    ],
  },
};

function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function stable(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stable(record[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
}

async function sha256(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(stable(value));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function requestIdentity(payload: RunPayload): Record<string, unknown> {
  return {
    goal: payload.goal,
    observation: payload.observation,
    contract: payload.contract,
    candidates: payload.candidates,
  };
}

function reasonsFor(payload: RunPayload, candidate: CandidateAction): string[] {
  const reasons: string[] = [];
  if (!payload.contract.allowed_action_ids.includes(candidate.action_id)) {
    reasons.push("not_in_current_contract");
  }
  const missing = candidate.required_permissions.filter(
    (permission) => !payload.contract.granted_permissions.includes(permission),
  );
  if (missing.length) reasons.push(`missing_permissions:${missing.join(",")}`);
  if (candidate.risk === "high" && candidate.evidence.length === 0) {
    reasons.push("missing_evidence_for_high_risk_action");
  }
  if (!allowedTools.has(`${candidate.tool}.${candidate.operation}`)) {
    reasons.push(`unregistered_tool_operation:${candidate.tool}.${candidate.operation}`);
  }
  return reasons;
}

async function browserTrace(payload: RunPayload): Promise<DecisionTrace> {
  const timestamp = new Date().toISOString();
  const rejected: DecisionTrace["rejected_actions"] = [];
  const eligible = payload.candidates.filter((candidate) => {
    const reasons = reasonsFor(payload, candidate);
    if (reasons.length) rejected.push({ action_id: candidate.action_id, reasons });
    return reasons.length === 0;
  });
  eligible.sort(
    (left, right) =>
      right.expected_value - left.expected_value ||
      riskOrder[left.risk] - riskOrder[right.risk] ||
      Number(!left.reversible) - Number(!right.reversible) ||
      left.action_id.localeCompare(right.action_id),
  );
  const selected = eligible[0] ?? null;
  eligible.slice(1).forEach((candidate) =>
    rejected.push({ action_id: candidate.action_id, reasons: ["lower_deterministic_rank"] }),
  );
  const waiting = Boolean(selected && (selected.risk === "high" || !selected.reversible));
  const status: RunStatus = !selected ? "blocked" : waiting ? "waiting_approval" : "completed";
  const events: DecisionTrace["events"] = [
    {
      event_type: "candidates_generated",
      at: timestamp,
      details: { provider: "simulated-openai-compatible", candidate_count: payload.candidates.length },
    },
    {
      event_type: "contract_evaluated",
      at: timestamp,
      details: { eligible: eligible.length, rejected: rejected.length },
    },
  ];
  if (!selected) events.push({ event_type: "run_blocked", at: timestamp, details: { reason: "no_eligible_actions" } });
  if (selected) events.push({ event_type: "action_selected", at: timestamp, details: { action_id: selected.action_id } });
  if (waiting && selected) events.push({ event_type: "approval_requested", at: timestamp, details: { action_id: selected.action_id } });
  if (status === "completed" && selected) events.push({ event_type: "action_executed", at: timestamp, details: { action_id: selected.action_id, adapter: "browser_simulation" } });

  return {
    run_id: crypto.randomUUID(),
    created_at: timestamp,
    updated_at: timestamp,
    revision: waiting ? 1 : 2,
    idempotency_key: payload.idempotency_key,
    goal: payload.goal,
    observation: {
      ...payload.observation,
      _planner: { provider: "simulated-openai-compatible", authority: "candidate-generation-only" },
    },
    observation_fingerprint: await sha256(payload.observation),
    request_fingerprint: await sha256(requestIdentity(payload)),
    contract_version: payload.contract.version,
    candidates: payload.candidates,
    eligible_action_ids: eligible.map((candidate) => candidate.action_id),
    selected_action: selected,
    rejected_actions: rejected,
    policy_checks: [
      {
        rule: "current_contract_enforced",
        passed: eligible.every((candidate) => payload.contract.allowed_action_ids.includes(candidate.action_id)),
        details: { contract_version: payload.contract.version },
      },
      {
        rule: "permissions_enforced",
        passed: eligible.every((candidate) => candidate.required_permissions.every((permission) => payload.contract.granted_permissions.includes(permission))),
        details: { granted_permissions: payload.contract.granted_permissions },
      },
      {
        rule: "high_risk_evidence_required",
        passed: eligible.every((candidate) => candidate.risk !== "high" || candidate.evidence.length > 0),
        details: {},
      },
      {
        rule: "tool_adapter_allow_list",
        passed: eligible.every((candidate) => allowedTools.has(`${candidate.tool}.${candidate.operation}`)),
        details: { fixed_capabilities: Array.from(allowedTools) },
      },
      {
        rule: "idempotency_request_identity",
        passed: true,
        details: { key: payload.idempotency_key, replayed: false },
      },
    ],
    approval: null,
    events,
    status,
    result:
      status === "completed" && selected
        ? {
            executed: true,
            adapter: "browser_simulation",
            external_side_effect: false,
            tool: selected.tool,
            operation: selected.operation,
          }
        : {},
    error: null,
    execution_count: status === "completed" ? 1 : 0,
    idempotency_replayed: false,
  };
}

function conflictTrace(payload: RunPayload, requestFingerprint: string): DecisionTrace {
  const timestamp = new Date().toISOString();
  return {
    run_id: crypto.randomUUID(),
    created_at: timestamp,
    updated_at: timestamp,
    revision: 1,
    idempotency_key: payload.idempotency_key,
    goal: payload.goal,
    observation: payload.observation,
    observation_fingerprint: requestFingerprint,
    request_fingerprint: requestFingerprint,
    contract_version: payload.contract.version,
    candidates: payload.candidates,
    eligible_action_ids: [],
    selected_action: null,
    rejected_actions: [],
    policy_checks: [
      {
        rule: "idempotency_request_identity",
        passed: false,
        details: { same_key: true, same_request: false },
      },
    ],
    approval: null,
    events: [
      {
        event_type: "idempotency_conflict",
        at: timestamp,
        details: { idempotency_key: payload.idempotency_key },
      },
    ],
    status: "blocked",
    result: {},
    error: {
      error_type: "IdempotencyConflictError",
      message: "idempotency_key was already used for a different request",
    },
    execution_count: 0,
    idempotency_replayed: false,
  };
}

export default function Home() {
  const [trace, setTrace] = useState<DecisionTrace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const store = useRef(new Map<string, { fingerprint: string; trace: DecisionTrace }>());

  const statusLabel = useMemo(() => trace?.status.replaceAll("_", " ") ?? "not started", [trace]);

  async function createRun(name: ScenarioName) {
    setLoading(true);
    setError(null);
    const payload = structuredClone(scenarios[name]);
    try {
      if (demoMode) {
        const fingerprint = await sha256(requestIdentity(payload));
        const existing = store.current.get(payload.idempotency_key);
        if (existing) {
          const replayed = structuredClone(existing.trace);
          replayed.idempotency_replayed = true;
          replayed.events.push({
            event_type: "idempotency_replay",
            at: new Date().toISOString(),
            details: { returned_existing_run: true, no_second_execution: true },
          });
          setTrace(replayed);
          return;
        }
        const created = await browserTrace(payload);
        store.current.set(payload.idempotency_key, { fingerprint, trace: structuredClone(created) });
        setTrace(created);
        return;
      }

      const response = await fetch(`${apiBase}/v1/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const responsePayload = await response.json();
      if (!response.ok) throw new Error(responsePayload.detail ?? `Request failed with ${response.status}`);
      setTrace(responsePayload as DecisionTrace);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown request error");
    } finally {
      setLoading(false);
    }
  }

  async function replayConflict() {
    setLoading(true);
    setError(null);
    const original = structuredClone(scenarios.low);
    const originalFingerprint = await sha256(requestIdentity(original));
    if (!store.current.has(original.idempotency_key) && demoMode) {
      const first = await browserTrace(original);
      store.current.set(original.idempotency_key, { fingerprint: originalFingerprint, trace: first });
    }
    const conflicting = { ...original, goal: "Conflicting request using the same idempotency key" };
    try {
      if (demoMode) {
        setTrace(conflictTrace(conflicting, await sha256(requestIdentity(conflicting))));
        return;
      }
      const response = await fetch(`${apiBase}/v1/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(conflicting),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? `Request failed with ${response.status}`);
      setTrace(payload as DecisionTrace);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown request error");
    } finally {
      setLoading(false);
    }
  }

  async function decide(decision: "approve" | "reject") {
    if (!trace) return;
    setLoading(true);
    setError(null);
    try {
      if (demoMode) {
        const timestamp = new Date().toISOString();
        const approved = decision === "approve";
        const updated: DecisionTrace = {
          ...trace,
          updated_at: timestamp,
          revision: trace.revision + (approved ? 2 : 1),
          status: approved ? "completed" : "rejected",
          approval: {
            decision,
            approver: "portfolio-operator-id",
            reason: approved ? "Evidence, permissions, and policy checks verified" : "Rejected during human review",
            decided_at: timestamp,
          },
          events: [
            ...trace.events,
            {
              event_type: approved ? "approval_granted" : "approval_rejected",
              at: timestamp,
              details: { approver: "portfolio-operator-id" },
            },
            ...(approved && trace.selected_action
              ? [{ event_type: "action_executed", at: timestamp, details: { action_id: trace.selected_action.action_id, adapter: "browser_simulation" } }]
              : []),
          ],
          result:
            approved && trace.selected_action
              ? {
                  executed: true,
                  adapter: "browser_simulation",
                  external_side_effect: false,
                  tool: trace.selected_action.tool,
                  operation: trace.selected_action.operation,
                }
              : {},
          execution_count: approved ? 1 : 0,
        };
        setTrace(updated);
        if (updated.idempotency_key) {
          store.current.set(updated.idempotency_key, { fingerprint: updated.request_fingerprint, trace: structuredClone(updated) });
        }
        return;
      }

      const response = await fetch(`${apiBase}/v1/runs/${trace.run_id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          approver: "portfolio-operator-id",
          reason: approvedReason(decision),
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? `Request failed with ${response.status}`);
      setTrace(payload as DecisionTrace);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown decision error");
    } finally {
      setLoading(false);
    }
  }

  function approvedReason(decision: "approve" | "reject"): string {
    return decision === "approve" ? "Evidence and policy checks verified" : "Rejected during human review";
  }

  function reset() {
    setTrace(null);
    setError(null);
    store.current.clear();
  }

  return (
    <main>
      <section className="demo-badges" aria-label="implementation status">
        <span>PUBLIC SIMULATION</span><span>DETERMINISTIC FINGERPRINTS</span><span>BLOCKED ACTIONS</span><span>VISIBLE IDEMPOTENCY</span><span>HUMAN APPROVAL</span>
      </section>
      <section className="hero">
        <div><p className="eyebrow">BLACK / PUBLIC PORTFOLIO</p><h1>AI Agent Control Plane</h1><p className="lede">Contract-aware candidate evaluation, exact rejection reasons, named approval, one-time execution, deterministic request identity, and a complete audit trace.</p></div>
        <div className={`status status-${trace?.status ?? "idle"}`} aria-live="polite"><span>RUN STATUS</span><strong>{statusLabel}</strong></div>
      </section>
      <section className="truth panel"><strong>What is real here?</strong> The contract, permission, evidence, ranking, approval, idempotency, blocking, fingerprint, and trace lifecycle are executed in-browser. Provider generation and tool execution are simulated. No external side effect occurs.</section>
      <section className="toolbar panel">
        <div><span className="label">PROOF SCENARIOS</span><code>{demoMode ? "Browser-safe proof · zero secrets · zero external side effects" : apiBase}</code></div>
        <div className="actions">
          <button disabled={loading} onClick={() => createRun("low")}>Run low-risk workflow</button>
          <button className="secondary" disabled={loading} onClick={() => createRun("high")}>Run approval-gated refund</button>
          <button className="danger" disabled={loading} onClick={() => createRun("blocked")}>Run blocked candidates</button>
          <button className="warning" disabled={loading} onClick={() => createRun("low")}>Replay same idempotency key</button>
          <button className="danger" disabled={loading} onClick={replayConflict}>Replay conflicting request</button>
          <button className="ghost" disabled={loading} onClick={reset}>Reset</button>
        </div>
      </section>
      {error && <section className="error panel" aria-live="assertive">{error}</section>}
      {!trace ? <section className="empty panel"><h2>No trace yet</h2><p>Run a successful, approval-gated, blocked, duplicate, or conflicting workflow. The same canonical input always produces the same fingerprint.</p></section> : <>
        <section className="grid metrics six-metrics">
          <article className="panel metric"><span>Contract</span><strong>{trace.contract_version}</strong></article>
          <article className="panel metric"><span>Eligible</span><strong>{trace.eligible_action_ids.length}</strong></article>
          <article className="panel metric"><span>Rejected</span><strong>{trace.rejected_actions.length}</strong></article>
          <article className="panel metric"><span>Executions</span><strong>{trace.execution_count ?? trace.events.filter((event) => event.event_type === "action_executed").length}</strong></article>
          <article className="panel metric"><span>Replay</span><strong>{trace.idempotency_replayed ? "REUSED" : "NEW"}</strong></article>
          <article className="panel metric"><span>Revision</span><strong>{trace.revision}</strong></article>
        </section>
        <section className="grid main-grid">
          <article className="panel">
            <div className="section-heading"><div><span className="label">DECISION</span><h2>{trace.selected_action?.name ?? trace.error?.error_type ?? "No eligible action"}</h2></div>{trace.selected_action && <span className={`risk risk-${trace.selected_action.risk}`}>{trace.selected_action.risk}</span>}</div>
            <p className="goal">{trace.goal}</p>
            <dl><div><dt>Tool</dt><dd>{trace.selected_action?.tool ?? "—"}</dd></div><div><dt>Operation</dt><dd>{trace.selected_action?.operation ?? "—"}</dd></div><div><dt>Idempotency key</dt><dd>{trace.idempotency_key ?? "—"}</dd></div><div><dt>Reversible</dt><dd>{trace.selected_action ? (trace.selected_action.reversible ? "yes" : "no") : "—"}</dd></div></dl>
            {trace.status === "waiting_approval" && <div className="approval-box"><p>This high-impact action is paused. It has not executed.</p><div className="actions"><button disabled={loading} onClick={() => decide("approve")}>Approve execution</button><button className="danger" disabled={loading} onClick={() => decide("reject")}>Reject action</button></div></div>}
            {trace.approval && <div className="approval-record"><span className="label">HUMAN DECISION</span><strong>{trace.approval.decision}</strong><p>{trace.approval.reason}</p><small>{trace.approval.approver}</small></div>}
          </article>
          <article className="panel"><span className="label">POLICY CHECKS</span><div className="stack">{trace.policy_checks.map((check) => <div className="row" key={check.rule}><span className={check.passed ? "dot pass" : "dot fail"}/><div><strong>{check.rule.replaceAll("_", " ")}</strong><small>{pretty(check.details)}</small></div></div>)}</div></article>
        </section>
        <section className="grid main-grid">
          <article className="panel"><span className="label">REJECTED CANDIDATES</span><div className="stack">{trace.rejected_actions.length === 0 ? <p className="muted">No rejected candidates.</p> : trace.rejected_actions.map((item) => <div className="rejected" key={item.action_id}><strong>{item.action_id}</strong><ul>{item.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></div>)}</div></article>
          <article className="panel"><span className="label">AUDIT EVENTS</span><div className="timeline">{trace.events.map((event, index) => <div className="timeline-row" key={`${event.event_type}-${index}`}><span>{index + 1}</span><div><strong>{event.event_type.replaceAll("_", " ")}</strong><small>{new Date(event.at).toLocaleString()}</small></div></div>)}</div></article>
        </section>
        <section className="grid main-grid">
          <article className="panel code-panel"><span className="label">RESULT / ERROR</span><pre>{pretty(trace.error ?? trace.result)}</pre></article>
          <article className="panel code-panel"><span className="label">TRACE IDENTITY</span><pre>{pretty({run_id:trace.run_id,idempotency_key:trace.idempotency_key,idempotency_replayed:trace.idempotency_replayed ?? false,execution_count:trace.execution_count ?? trace.events.filter((event) => event.event_type === "action_executed").length,observation_fingerprint:trace.observation_fingerprint,request_fingerprint:trace.request_fingerprint,canonical_input_excludes_run_id:true})}</pre></article>
        </section>
      </>}
    </main>
  );
}
