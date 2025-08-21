# NL-to-CRUD Gateway (MVP) — Technical Specification

**Audience:** Claude Code implementers and backend engineers
**Goal:** Deliver a lean, production-ready endpoint that accepts natural language (NL) requests from AI agents and safely executes data operations by compiling NL → constrained plan → validated internal CRUD calls.
**Design Tenets:** *MVP-first, minimal public surface, strong guardrails, deterministic validation, centralized policy, no back-and-forth interactions.*

## 1) Context & Business Rationale

### 1.1 Problem

Multiple LangChain-based agents must interact with a backend database whose internal API contracts and schemas evolve. Exposing many granular endpoints to each agent creates coupling, prompt/tool bloat, and governance risks.

### 1.2 Solution

A single external endpoint (`POST /agent/db`) accepts a natural-language instruction and optional hints. The backend:

1. **Routes** the request to likely resources.
2. **Retrieves** minimal contracts for those resources.
3. **Plans** a *constrained internal JSON plan* (DSL).
4. **Validates** the plan deterministically against contracts, role, and safety caps.
5. **Executes** the operation via internal CRUD services (not raw LLM SQL).

### 1.3 Why it matters

* **Leaner agents:** One tool, minimal prompt surface.
* **Faster iteration:** Internal API/schema changes are absorbed centrally.
* **Governance:** A single choke point enforces RBAC, RLS/CLS, data minimization.
* **Reliability:** Deterministic validation and DB constraints prevent destructive mistakes.

> **MVP Constraint:** No “plan-only” confirmations, no write tiers, no explicit idempotency keys, and DELETE is disallowed. Operations either execute immediately or are denied with a 4xx error.

## 2) Public API

### 2.1 Endpoint

`POST /agent/db`

### 2.2 Request (minimal)

```json
{
  "natural_language": "Find all active cases for client 123 created after Jan 1, 2024.",
  "hints": { "resources": ["cases"] }
}
```

* `natural_language` (required): Free-text instruction from the agent.
* `hints.resources` (optional): Caller’s best guess at relevant logical resources.

### 2.3 Unified Response Envelope

```ts
type AgentDbResponse = {
  ok: boolean;
  operation: 'READ' | 'INSERT' | 'UPDATE' | null;
  resource: string | null;
  data: Array<Record<string, any>>;   // post-image rows (READ or WRITE)
  count: number;                      // READ: rows returned; WRITE: rows affected
  page?: { limit: number; offset: number }; // present only on READ when used
  error?: {
    type:
      | 'AMBIGUOUS_INTENT'
      | 'UNAUTHORIZED_OPERATION'
      | 'UNAUTHORIZED_FIELD'
      | 'INVALID_QUERY'
      | 'RESOURCE_NOT_FOUND'
      | 'CONFLICT';
    message: string;
    clarification?: string;           // single question (422 only)
    details?: Record<string, any>;
  };
};
```

### 2.4 HTTP Status Codes

* **200**: Success (READ/INSERT/UPDATE)
* **400**: `INVALID_QUERY` (type/operator/limit violation)
* **403**: `UNAUTHORIZED_OPERATION` / `UNAUTHORIZED_FIELD`
* **404**: `RESOURCE_NOT_FOUND`
* **409**: `CONFLICT` (e.g., unique constraint violated on INSERT/UPSERT)
* **422**: `AMBIGUOUS_INTENT` (low-confidence write or underspecified intent)

## 3) Internal Architecture (Pipeline)

### 3.1 Overview

```
Request → Router (tiny LLM + rules) → Contract Retrieval → Planner (LLM → DSL)
       → Validator (deterministic) → Executor (internal CRUD) → Response
```

### 3.2 Router (K=2, elastic to K=3)

**Purpose:** Map NL + hints to most likely resources; determine read vs write intent.

* **Inputs:** `natural_language`, `hints.resources`
* **Model:** Fast, low-cost LLM (e.g., gpt-5-nano) + heuristic rules.
* **Outputs:** `{ resources: string[], confidence: number, reason: string, intent: 'READ'|'WRITE' }`
* **Policy:**

  * **K=2** resources default; expand to **K=3** only when NL clearly implies a join.
  * If **WRITE** and `confidence < threshold`, return **422 AMBIGUOUS\_INTENT** with one clarifying question.
  * If **READ** and confidence is mediocre, proceed but contracts/validator will constrain behavior.

**Why it matters:** Keeps planner context small and token costs low while avoiding guessy writes.

### 3.3 Contract Retrieval (enumerated JSON, not prose)

**Purpose:** Load *only* the policy surface for selected resources.

**Contract shape (per resource, per role):**

* `version`: string
* `resource`: string (canonical name)
* `ops_allowed`: `READ|INSERT|UPDATE` (subset)
* `fields`: array of `{ name, type, nullable, pii, readable, writable }`
* `filters_allowed`: map `{ fieldName: allowedOperators[] }`
* `order_allowed`: array of fields eligible for `order_by`
* `limits`: `{ max_rows, max_predicates, max_update_fields, max_joins }`
* `joins_allowed` (optional, MVP-minimal): array of `{ target_resource, on: [{leftField, rightField}], type: 'inner' }`

**Why it matters:** Contracts are the source of truth for validation; they prevent LLM drift.

### 3.4 Planner (LLM → strict internal DSL)

**Purpose:** Convert NL + contracts into a constrained plan. **No raw SQL.**

**Operations supported:** `READ`, `INSERT`, `UPDATE` (DELETE disallowed)

**Internal DSL (examples)**

* **READ**

  ```json
  {
    "steps": [{
      "op": "READ",
      "resource": "cases",
      "select": ["id","client_id","status","created_at"],
      "where": [
        {"field":"client_id","op":"=","value":"123"},
        {"field":"status","op":"=","value":"ACTIVE"},
        {"field":"created_at","op":">=","value":"2024-01-01"}
      ],
      "order_by": [{"field":"created_at","dir":"desc"}],
      "limit": 100,
      "offset": 0
    }]
  }
  ```

* **UPDATE** *(PK equality; limit 1)*

  ```json
  {
    "steps": [{
      "op": "UPDATE",
      "resource": "cases",
      "where": [{"field":"id","op":"=","value":"case_987"}],
      "update": {"status":"IN_REVIEW"},
      "limit": 1
    }]
  }
  ```

* **INSERT** *(DB generates IDs; unique/UPSERT semantics enforced in DB)*

  ```json
  {
    "steps": [{
      "op": "INSERT",
      "resource": "client_communications",
      "values": {
        "case_id": "case_987",
        "direction": "OUTBOUND",
        "channel": "EMAIL",
        "subject": "Welcome",
        "sent_at": "2025-08-20T14:31:00Z"
      }
    }]
  }
  ```

**Why it matters:** A strict DSL eliminates ambiguity and disallows invented fields or free-form SQL.

### 3.5 Validator (deterministic, hard guardrails)

**Purpose:** Accept-only validation; no negotiation or auto-repair back-and-forth.

**Checks:**

* **Schema validation:** DSL matches JSON Schema; extra keys rejected.
* **Role/ACL:** `ops_allowed`, field readability/writability.
* **Safety rules (MVP universal):**

  * **DELETE disallowed.**
  * **UPDATE:** must include **PK equality** in `where` + `limit: 1`. No set-based updates.
  * **INSERT:** only whitelisted resources; server generates IDs; DB **UNIQUE/UPSERT** prevents dup logical objects.
  * **Caps:** defaults—`limit ≤ 100`, `predicates ≤ 10`, `update fields ≤ 10`, `joins ≤ 1`. (All are **resource-configurable**.)
* **Type/operator checks:** based on contracts (e.g., `LIKE` allowed only on text).
* **Join checks (if used):** allowed join targets and well-formed `on` pairs.

**On failure:** return 4xx with unified envelope and one clarifying question only for `AMBIGUOUS_INTENT`.

**Why it matters:** Deterministic acceptance avoids silent partials and keeps execution safe.

### 3.6 Executor (internal CRUD, transactional)

**Purpose:** Compile DSL steps into calls to existing internal REST services (service layer), not raw LLM-generated SQL.

**Behavior:**

* Wrap **writes** in a transaction.
* Enforce **RLS/CLS** in DB/service layer (not the LLM).
* **INSERT:** DB generates UUIDs; rely on UNIQUE/UPSERT to make retries harmless.
* **UPDATE:** PK-scoped to a single row; last-write-wins unless optimistic concurrency is available internally.
* **READ:** Apply `limit/offset`, `order_by`, and projection per contract.

**Response mapping (always the unified envelope):**

* `data`: **post-image** rows (READ results; or updated/inserted rows).
* `count`: rows returned/affected.
* `page` included only on READ when pagination is applied.

**Why it matters:** Keeps business rules centralized and consistent; leverages existing services and DB guarantees.

## 4) Non-Functional Requirements

### 4.1 Security & Compliance

* **AuthN:** Standard token (e.g., JWT) at the gateway; map to actor & role.
* **AuthZ:** Role → resource ops & field-level access via contracts; enforce **RLS/CLS** at DB/service.
* **PII minimization:** LLMs see schemas/contracts, not bulk data. Only minimal scalar values (e.g., a client ID) may appear in prompts.
* **No DELETE:** Hard policy in validator; soft-delete later via UPDATE of `deleted_at`.
* **Network retries:** Safe due to UPSERT and PK-scoped `UPDATE limit 1`.

### 4.2 Performance

* Router context \~200–300 tokens; planner context \~400–900; outputs \~100–200.
* Additional latency target: **\~150–300ms** typical on READ; slightly higher on writes (transaction + service calls).
* Token minimization: keep contracts tiny; choose K=2 resources (expand to 3 only when necessary).

### 4.3 Reliability & Observability

* **Structured logs** per request: `{req_id, actor, role, router_output, contract_ids@versions, dsl_fingerprint, compiled_calls, rows_affected, timings}`.
* **No metrics in the public response** (MVP leanness); collect internally.
* **dl\_fingerprint** (e.g., stable hash) may be used internally for caching/replay; not exposed.

### 4.4 Rate Limiting & Abuse Prevention

* Per-actor/role QPS and burst limits.
* Deny overly complex queries in validator (caps + depth checks).

### 4.5 Compatibility & Evolution

* Contracts carry a `version`; backend components accept multiple versions for rollout.
* DSL schema is versioned internally; reject unknown versions with `INVALID_QUERY`.

## 5) Data Models

### 5.1 Public Request

```ts
type AgentDbRequest = {
  natural_language: string;
  hints?: { resources?: string[] };
};
```

### 5.2 Public Response — Unified Envelope

(As defined in §2.3)

### 5.3 Contract (per resource, per role)

```ts
type ResourceContract = {
  version: string;
  resource: string; // e.g., "cases"
  ops_allowed: Array<'READ' | 'INSERT' | 'UPDATE'>;

  fields: Array<{
    name: string;
    type: 'uuid'|'string'|'text'|'number'|'integer'|'boolean'|'date'|'timestamp'|'json';
    nullable: boolean;
    pii: boolean;
    readable: boolean;
    writable: boolean;
  }>;

  filters_allowed: Record<string, Array<'='|'!='|'>'|'>='|'<'|'<='|'IN'|'BETWEEN'|'LIKE'|'ILIKE'>>;
  order_allowed: string[];

  limits: {
    max_rows: number;            // default 100
    max_predicates: number;      // default 10
    max_update_fields: number;   // default 10
    max_joins: number;           // default 1
  };

  joins_allowed?: Array<{
    target_resource: string;
    on: Array<{ leftField: string; rightField: string }>;
    type: 'inner';
  }>;
};
```

### 5.4 Internal DSL (planner output)

```ts
type DSL = {
  steps: Array<
    | {
        op: 'READ';
        resource: string;
        select: string[];
        where?: Array<{ field: string; op: string; value: any }>;
        order_by?: Array<{ field: string; dir: 'asc'|'desc' }>;
        limit: number;
        offset?: number;
      }
    | {
        op: 'UPDATE';
        resource: string;
        where: Array<{ field: string; op: '='; value: any }>; // must include PK equality
        update: Record<string, any>;                           // fields to set (≤ max_update_fields)
        limit: 1;
      }
    | {
        op: 'INSERT';
        resource: string;
        values: Record<string, any>; // no explicit IDs; DB generates
      }
  >;
};
```

> JSON Schemas for `ResourceContract` and `DSL` should be implemented to enable strict validation (reject unknown keys, enforce enums/types, caps).

## 6) Error Taxonomy (machine-readable)

| HTTP | type                    | Meaning / Example Action                                                                 |
| ---- | ----------------------- | ---------------------------------------------------------------------------------------- |
| 422  | AMBIGUOUS\_INTENT       | Router confidence low on WRITE or underspecified target; include one clarifying question |
| 403  | UNAUTHORIZED\_OPERATION | Role not allowed for op on resource                                                      |
| 403  | UNAUTHORIZED\_FIELD     | Role cannot read/write one or more referenced fields                                     |
| 400  | INVALID\_QUERY          | Type mismatch, operator not allowed, caps exceeded, disallowed DELETE, etc.              |
| 404  | RESOURCE\_NOT\_FOUND    | Resource name invalid/unavailable for role                                               |
| 409  | CONFLICT                | Unique constraint violation on INSERT/UPSERT                                             |

All errors use the unified envelope with `ok:false` and `error` populated.

## 7) Phase Plan (MVP-first, enterprise-grade)

### Phase 1 — **Read-Only MVP**

**Scope:**

* Implement Router (K=2; K=3 only when clear join implied). Confidence gating on writes (return 422).
* Implement contracts for initial resources (e.g., `cases`, `client_communications`, `document_analysis`).
* Implement Planner (LLM → DSL) for READ operations.
* Implement Validator: schema, ACL, types/operators, caps, join allowance (0–1).
* Implement Executor: compile to internal CRUD reads; apply projection/order/limit/offset; transactional semantics not needed for reads.
* Public unified response envelope.
* Structured logs (internal), request IDs, `dsl_fingerprint`.
* Security: AuthN at gateway, RBAC in contracts, RLS/CLS at DB.

**Exit Criteria:**

* > 95% of representative READ intents compile & pass validation.
* P95 added latency ≤ 300ms on READ.
* No PII spillage beyond contract-permitted fields.

### Phase 2 — **Safe Writes MVP**

**Scope:**

* Extend Planner & Validator for:

  * **UPDATE:** PK equality in `where`, `limit:1`, `update` fields ≤ cap.
  * **INSERT:** DB-generated IDs; unique/UPSERT semantics enforced in DB.
* Enforce **no DELETE**.
* Executor: wrap writes in transactions; map to internal CRUD; return **post-image** rows.
* Error taxonomy: include `CONFLICT` (409).
* Resource-specific caps (override defaults) for `max_rows`, `max_predicates`, `max_update_fields`.

**Exit Criteria:**

* PK-scoped updates reliably idempotent under network retries.
* Insert retries do not create duplicate logical objects.
* Audit shows zero multi-row or destructive updates.

### Phase 3 — **Scale & Hardening**

**Scope:**

* Router/Planner caching of frequent NL → DSL (“intent macros”), fully internal; no public API changes.
* Expand joins to controlled, simple inner joins where contracts allow (still K small).
* Fine-grained per-resource limits; throttling per actor/role.
* Observability: dashboards for 4xx rates, latency, rows\_affected, conflict rate.
* Replay tool (internal): given logs, re-run Router→Planner→Validator for debugging.
* Optional: soft-delete via UPDATE `deleted_at`.
* Optional: optimistic concurrency where tables expose `version` or `updated_at`.

**Exit Criteria:**

* Cache hit rate ≥ 50% on stable workloads, reducing planner calls.
* Error rates within SLOs; alerting on spikes in 4xx or conflicts.
* Minimal operator overhead; contracts/limits modifiable without redeploys.

## 8) Implementation Principles (for Claude Code & backend)

1. **No free-form SQL from LLMs.** Only the internal DSL; compile server-side.
2. **Contracts are the ground truth.** Keep them tiny, enumerated, and versioned.
3. **Execute or deny.** No interactive plan confirmation or multi-turn repairs.
4. **Deterministic validation.** Fail fast with a single, precise 4xx and (if 422) one clarifying question.
5. **Safety by construction.** Disallow DELETE; UPDATE is PK=only; INSERT is UPSERT-safe.
6. **Least privilege.** Role/field ACLs + DB RLS/CLS; PII minimization in prompts.
7. **MVP leanness.** Minimal public surface, single endpoint, unified envelope, internal logs only.
8. **Enterprise readiness.** Transactions on writes, structured audit logs, rate limits, and conflict handling.

## 9) Example Flows (Narrative)

### 9.1 READ — “Find active cases for client 123 since 2024-01-01”

* **Router:** picks `cases` (confidence 0.92).
* **Contracts:** load `cases` contract for caller role.
* **Planner:** emits READ DSL with predicates and limit 100.
* **Validator:** checks ACL, predicate types, operators, caps.
* **Executor:** internal CRUD call; return rows as `data`; `count=…`; optionally `page`.

### 9.2 UPDATE — “Mark case\_987 as IN\_REVIEW”

* **Router:** `cases` (confidence high), intent=WRITE.
* **Contracts:** load `cases`.
* **Planner:** UPDATE DSL with `where id = case_987`, `limit:1`, `update.status="IN_REVIEW"`.
* **Validator:** enforces PK equality, `limit:1`, field writable, caps.
* **Executor:** transactional CRUD update; post-image row in `data`, `count=1`.

### 9.3 INSERT — “Record an outbound welcome email for case\_987”

* **Router:** `client_communications` (and possibly `cases` if referenced).
* **Contracts:** load `client_communications`.
* **Planner:** INSERT DSL; values omit ID.
* **Validator:** INSERT allowed; fields writable; types valid.
* **Executor:** transactional internal create; DB generates ID; return created row.

## 10) Configuration (initial defaults)

* Router write-confidence threshold: **0.80**
* Contracts limits (defaults; per-resource overrides allowed):

  * `max_rows`: **100**
  * `max_predicates`: **10**
  * `max_update_fields`: **10**
  * `max_joins`: **1**
* Allowed operators by type (baseline):

  * **text/string:** `=`, `!=`, `LIKE`, `ILIKE`, `IN`
  * **numeric:** `=`, `!=`, `>`, `>=`, `<`, `<=`, `IN`, `BETWEEN`
  * **date/timestamp:** `=`, `>`, `>=`, `<`, `<=`, `BETWEEN`
  * **uuid/boolean/json:** restricted to equality unless explicitly extended

---

**This specification is intentionally minimal in public surface and maximal in guardrails.** It enables immediate execution (or denial) without iterative planning, while ensuring safety, observability, and role-based governance suitable for production and enterprise use.
