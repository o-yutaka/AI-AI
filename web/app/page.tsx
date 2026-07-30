"use client";

import { useMemo, useState } from "react";

type RiskLevel = "low" | "medium" | "high";
type RunStatus = "completed" | "waiting_approval" | "rejected" | "blocked" | "failed";

type CandidateAction = {
  action_id: string;
  name: string;
  tool: string;
  operation: string;
  expected_value: number;
  risk: RiskLevel;
  reversible: boolean;
  evidence: string[];
  required_permissions: string[];
};

type RejectedAction = {
  action_id: string;
  reasons: string[];
};

type PolicyCheck = {
  rule: string;
  passed: boolean;
  details: Record<string, unknown>;
};

type AuditEvent = {
  event_type: string;
  at: string;
  details: Record<string, unknown>;
};

type DecisionTrace = {
  run_id: string;
  created_at: string;
  updated_at: string;
  revision: number;
  goal: string;
  observation_fingerprint: string;
  request_fingerprint: string;
  contract_version: string;
  candidates: CandidateAction[];
  eligible_action_ids: string[];
  selected_action: CandidateAction | null;
  rejected_actions: RejectedAction[];
  policy_checks: PolicyCheck[];
  approval: {
    decision: "approve" | "reject";
    approver: string;
    reason: string;
    decided_at: string;
  } | null;
  events: AuditEvent[];
  status: RunStatus;
  result: Record<string, unknown>;
  error: { error_type: string; message: string } | null;
};

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const lowRiskPayload = {
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
      expected_value: 0.8,
      risk: "low",
      reversible: true,
      required_permissions: ["ticket:write"],
      evidence: ["knowledge-base/article-12"],
    },
    {
      action_id: "escalate",
      name: "Escalate to operator",
      tool: "support_api",
      operation: "escalate",
      expected_value: 0.5,
      risk: "low",
      reversible: true,
      required_permissions: ["ticket:write"],
      evidence: [],
    },
  ],
  idempotency_key: `support-low-${Date.now()}`,
};

const highRiskPayload = {
  goal: "Issue a policy-compliant refund",
  observation: { ticket_id: "T-101", refund_amount: 12000 },
  contract: {
    version: "support-v1",
    allowed_action_ids: ["refund"],
    granted_permissions: ["refund:write"],
  },
  candidates: [
    {
      action_id: "refund",
      name: "Issue refund",
      tool: "billing_api",
      operation: "refund",
      payload: { amount: 12000, currency: "JPY" },
      expected_value: 0.9,
      risk: "high",
      reversible: false,
      required_permissions: ["refund:write"],
      evidence: ["ticket/T-101/refund-policy"],
    },
  ],
  idempotency_key: `support-high-${Date.now()}`,
};

function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

export default function Home() {
  const [trace, setTrace] = useState<DecisionTrace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const statusLabel = useMemo(
    () => trace?.status.replaceAll("_", " ") ?? "not started",
    [trace],
  );

  async function createRun(mode: "low" | "high") {
    setLoading(true);
    setError(null);
    const source = mode === "low" ? lowRiskPayload : highRiskPayload;
    const body = {
      ...source,
      idempotency_key: `${mode}-${crypto.randomUUID()}`,
    };

    try {
      const response = await fetch(`${apiBase}/v1/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? `Request failed with ${response.status}`);
      }
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
      const response = await fetch(`${apiBase}/v1/runs/${trace.run_id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision,
          approver: "portfolio-operator@example.com",
          reason:
            decision === "approve"
              ? "Evidence and policy checks verified in the portfolio demo"
              : "Rejected during the portfolio approval review",
        }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail ?? `Request failed with ${response.status}`);
      }
      setTrace(payload as DecisionTrace);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unknown decision error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <section className="hero">
        <div>
          <p className="eyebrow">BLACK / PUBLIC PORTFOLIO</p>
          <h1>AI Agent Control Plane</h1>
          <p className="lede">
            Contract-aware execution, deterministic decisions, human approval, and a complete
            audit trace—shown as a working support-automation workflow.
          </p>
        </div>
        <div className={`status status-${trace?.status ?? "idle"}`}>
          <span>RUN STATUS</span>
          <strong>{statusLabel}</strong>
        </div>
      </section>

      <section className="toolbar panel">
        <div>
          <span className="label">API</span>
          <code>{apiBase}</code>
        </div>
        <div className="actions">
          <button disabled={loading} onClick={() => createRun("low")}>
            Run low-risk workflow
          </button>
          <button className="secondary" disabled={loading} onClick={() => createRun("high")}>
            Run approval-gated refund
          </button>
        </div>
      </section>

      {error && <section className="error panel">{error}</section>}

      {!trace ? (
        <section className="empty panel">
          <h2>No trace yet</h2>
          <p>Start a workflow to inspect candidate filtering, policy checks, and execution events.</p>
        </section>
      ) : (
        <>
          <section className="grid metrics">
            <article className="panel metric">
              <span>Contract</span>
              <strong>{trace.contract_version}</strong>
            </article>
            <article className="panel metric">
              <span>Revision</span>
              <strong>{trace.revision}</strong>
            </article>
            <article className="panel metric">
              <span>Eligible</span>
              <strong>{trace.eligible_action_ids.length}</strong>
            </article>
            <article className="panel metric">
              <span>Rejected</span>
              <strong>{trace.rejected_actions.length}</strong>
            </article>
          </section>

          <section className="grid main-grid">
            <article className="panel">
              <div className="section-heading">
                <div>
                  <span className="label">DECISION</span>
                  <h2>{trace.selected_action?.name ?? "No eligible action"}</h2>
                </div>
                {trace.selected_action && (
                  <span className={`risk risk-${trace.selected_action.risk}`}>
                    {trace.selected_action.risk}
                  </span>
                )}
              </div>
              <p className="goal">{trace.goal}</p>
              {trace.selected_action && (
                <dl>
                  <div>
                    <dt>Tool</dt>
                    <dd>{trace.selected_action.tool}</dd>
                  </div>
                  <div>
                    <dt>Operation</dt>
                    <dd>{trace.selected_action.operation}</dd>
                  </div>
                  <div>
                    <dt>Expected value</dt>
                    <dd>{trace.selected_action.expected_value.toFixed(2)}</dd>
                  </div>
                  <div>
                    <dt>Reversible</dt>
                    <dd>{trace.selected_action.reversible ? "yes" : "no"}</dd>
                  </div>
                </dl>
              )}

              {trace.status === "waiting_approval" && (
                <div className="approval-box">
                  <p>This action is high-impact and has not executed.</p>
                  <div className="actions">
                    <button disabled={loading} onClick={() => decide("approve")}>
                      Approve execution
                    </button>
                    <button className="danger" disabled={loading} onClick={() => decide("reject")}>
                      Reject action
                    </button>
                  </div>
                </div>
              )}

              {trace.approval && (
                <div className="approval-record">
                  <span className="label">HUMAN DECISION</span>
                  <strong>{trace.approval.decision}</strong>
                  <p>{trace.approval.reason}</p>
                  <small>{trace.approval.approver}</small>
                </div>
              )}
            </article>

            <article className="panel">
              <span className="label">POLICY CHECKS</span>
              <div className="stack">
                {trace.policy_checks.map((check) => (
                  <div className="row" key={check.rule}>
                    <span className={check.passed ? "dot pass" : "dot fail"} />
                    <div>
                      <strong>{check.rule.replaceAll("_", " ")}</strong>
                      {Object.keys(check.details).length > 0 && <small>{pretty(check.details)}</small>}
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <section className="grid main-grid">
            <article className="panel">
              <span className="label">REJECTED CANDIDATES</span>
              {trace.rejected_actions.length === 0 ? (
                <p className="muted">No rejected candidates.</p>
              ) : (
                <div className="stack">
                  {trace.rejected_actions.map((item) => (
                    <div className="rejected" key={`${item.action_id}-${item.reasons.join("-")}`}>
                      <strong>{item.action_id}</strong>
                      <ul>
                        {item.reasons.map((reason) => (
                          <li key={reason}>{reason.replaceAll("_", " ")}</li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article className="panel">
              <span className="label">AUDIT EVENTS</span>
              <div className="timeline">
                {trace.events.map((event, index) => (
                  <div className="timeline-row" key={`${event.event_type}-${index}`}>
                    <span>{index + 1}</span>
                    <div>
                      <strong>{event.event_type.replaceAll("_", " ")}</strong>
                      <small>{new Date(event.at).toLocaleString()}</small>
                    </div>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <section className="grid main-grid">
            <article className="panel code-panel">
              <span className="label">RESULT / ERROR</span>
              <pre>{pretty(trace.error ?? trace.result)}</pre>
            </article>
            <article className="panel code-panel">
              <span className="label">TRACE IDENTITY</span>
              <pre>
                {pretty({
                  run_id: trace.run_id,
                  observation_fingerprint: trace.observation_fingerprint,
                  request_fingerprint: trace.request_fingerprint,
                  created_at: trace.created_at,
                  updated_at: trace.updated_at,
                })}
              </pre>
            </article>
          </section>
        </>
      )}
    </main>
  );
}
