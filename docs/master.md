# Project Sentinel - Master Plan

## 0. Document Control

- Status: Active implementation (baseline complete; ML readiness wave in planning)
- Scope: System blueprint and operating model for 2027 election readiness
- Canonical document: This file is the single source of truth for project direction

## 1. Mission, Scope, and Non-Goals

### 1.1 Mission

Protect the 2027 Kenyan General Election from ethnic incitement and election-related disinformation by building a Kenya-native multilingual political safety infrastructure.

### 1.2 Scope

Sentinel provides two tightly coupled capabilities:

1. A real-time Moderation API for low-latency decisions in publishing workflows.
2. An asynchronous Monitoring and Update System that adapts lexicons, language packs, and policies as rhetoric shifts.

### 1.3 Non-Goals

Sentinel is not:

- A general-purpose global moderation platform.
- A replacement for full investigative fact-checking.
- A surveillance product for mass personal profiling.

## 2. Problem Context (Kenya-Specific)

Kenyan political discourse is multilingual, code-switched, and context-heavy. Harmful rhetoric often appears in mixed language, local slang, and coded references that generic moderation tools fail to interpret reliably.

During election cycles, risk intensifies because:

- New terms and dog whistles appear quickly.
- Meaning changes by time, geography, and historical context.
- Adversaries actively probe systems for evasion.
- External platform APIs can change or be withdrawn without warning.

Sentinel is designed to remain operational under these conditions.

## 3. Success Criteria and Operating Targets

### 3.1 Core Outcomes

| Outcome | Target |
|---|---|
| High-severity harm detection | >90% F1 on Tier 1 languages for core harm classes |
| Real-time response | P95 latency <150ms on hot path |
| Availability | 99.9% service target with surge readiness |
| Adaptation speed | Weekly or faster pack and lexicon updates during campaign peaks |
| Auditability | 100% decision traceability with reason codes and version IDs |

### 3.2 Async Queue SLAs

| Priority | SLA |
|---|---|
| Critical (imminent violence signals) | <= 5 minutes |
| Urgent (campaign-period misinformation spikes) | <= 30 minutes |
| Standard | <= 4 hours |
| Batch | <= 24 hours |

## 4. Design Principles

1. One engine, many languages: one core system with modular Language Packs.
2. Code-switching first: language routing at span level, not post level.
3. Deterministic hot path: structured outputs, no free-form legal reasoning.
4. Human-in-the-loop by design: ambiguity escalates; humans remain accountable.
5. Defense in depth: threat model includes state-grade intrusion, insider misuse, and election-day disruption.
6. Graceful degradation: connector failures reduce capability, not system viability.

## 5. System Architecture

### 5.1 High-Level Components

- Intake layer: REST API, webhooks, optional bulk and partner channels.
- Language router and normalizer: span-level LID, transliteration and slang normalization.
- Hot-path moderation engine: lexicon triggers, vector similarity, multi-label inference, policy decisioning.
- Human review system: queueing, override workflows, structured rationale capture.
- Monitoring and update pipeline: emerging term detection, narrative clustering, release pipeline.
- Audit and appeals layer: tamper-evident logs, case reconstruction, transparency exports.

### 5.2 Hot Path Flow

```text
Input
-> Normalize and route language spans
-> Fast lexical triggers (Redis)
-> Semantic similarity (Postgres + pgvector)
-> Claim-likeness signal (deterministic baseline)
-> Multi-label inference (shadow-first during ML readiness wave)
-> Deterministic policy logic
-> Action (ALLOW / REVIEW / BLOCK)
-> Structured output (labels, evidence, reason codes, versions, latency)
```

### 5.3 Deterministic Output Contract

```json
{
  "toxicity": 0.87,
  "labels": ["INCITEMENT_VIOLENCE", "ETHNIC_CONTEMPT"],
  "action": "BLOCK",
  "reason_codes": ["R_INCITE_CALL_TO_HARM", "R_ETHNIC_SLUR_MATCH"],
  "evidence": [
    {"type": "lexicon", "match": "____", "severity": 3, "lang": "sw"},
    {"type": "vector_match", "match_id": "lex_10293", "similarity": 0.89},
    {"type": "model_span", "span": "____", "confidence": 0.91}
  ],
  "language_spans": [
    {"start": 0, "end": 12, "lang": "sw"},
    {"start": 13, "end": 40, "lang": "kik"}
  ],
  "model_version": "sentinel-multi-v2",
  "lexicon_version": "hatelex-v2.1",
  "pack_versions": {"sw": "pack-sw-1.4", "kik": "pack-kik-0.3"},
  "policy_version": "policy-2026.11",
  "latency_ms": 94
}
```

## 6. Moderation Taxonomy and Decision Policy

### 6.1 Harm Taxonomy

1. `ETHNIC_CONTEMPT`
2. `INCITEMENT_VIOLENCE`
3. `HARASSMENT_THREAT`
4. `DOGWHISTLE_WATCH`
5. `DISINFO_RISK`
6. `BENIGN_POLITICAL_SPEECH`

### 6.2 Action Rules (V1)

- `BLOCK`: explicit calls to harm, severe slurs in direct hostile context, credible targeted threats.
- `REVIEW`: ambiguous coded hostility, uncertain context, emerging terms, or low-confidence disinfo matches.
- `ALLOW`: legitimate criticism, satire, reporting, and campaign speech without policy violation.

All actions must map to reason codes and evidence objects.

## 7. Language Coverage Strategy

### 7.1 Language Pack Standard

Each Language Pack is versioned and includes:

- normalization and tokenization rules;
- language-specific lexicon entries;
- calibration thresholds and overrides;
- evaluation set and acceptance criteria;
- optional adapters when justified by measurable gain.

### 7.2 Rollout Tiers

- Tier 1 (launch): English, Kiswahili, Sheng, and highest-risk/high-volume vernaculars.
- Tier 2: additional mother-tongue packs based on traffic, risk, and partner need.
- Tier 3: long-tail coverage using multilingual baseline plus escalation-first policy.

### 7.3 Code-Switching Handling

- Router emits token spans with language tags.
- Scoring combines span-level rules and global context.
- Ambiguous or low-confidence language mixtures default to conservative escalation.

## 8. Knowledge Layer: Hate-Lex and Narrative DB

### 8.1 Hate-Lex v2

The multilingual knowledge base stores:

- slurs and variants;
- coded dog whistles;
- violence idioms and calls to harm;
- disinformation narrative templates.

Each record includes language, severity, category, examples, first_seen, last_seen, status, and change history.

### 8.2 Storage Pattern

- Redis: high-confidence hot triggers for O(1) lookups.
- Postgres + pgvector: full lexicon and semantic retrieval.

### 8.3 Versioning and Traceability

All mutable artifacts are versioned:

- models;
- lexicon;
- language packs;
- policies.

This enables point-in-time reconstruction for audits and appeals.

## 9. Disinformation Handling Model

Sentinel does not claim full real-time fact checking.

### 9.1 Hot Path

- claim-likeness detection;
- similarity against known narrative and claim IDs;
- shadow-first multi-label disinformation/harm inference during ML readiness rollout;
- output as `DISINFO_RISK` with evidence references.

### 9.2 Async Path

- partner fact-check workflow integration;
- narrative clustering and verification;
- policy and narrative DB updates;
- escalation to trusted intermediaries when required.

## 10. Governance, Rights, and Legal Alignment

### 10.1 Governance Controls

- Deterministic reason codes and evidence traces.
- Human escalation for ambiguous and high-impact cases.
- Versioned releases with rollback.
- Tiered transparency and appeals workflows.

### 10.2 Kenyan Legal Alignment

| Framework | Relevance | Implementation Implication |
|---|---|---|
| National Cohesion and Integration Act (2008) | Ethnic hate and incitement | Policy definitions and severity mapping must align |
| Computer Misuse and Cybercrimes Act (2018) | Harmful false information and cyber harassment | Preserve context and avoid overreach on good-faith speech |
| Data Protection Act (2019) | Sensitive personal and political data | Retention controls, processor safeguards, access restrictions |
| Election Offences framework | Campaign and results-period constraints | Time-bound policy toggles by electoral phase |

### 10.3 Electoral Phase Policy Modes

| Phase | Default Policy Posture |
|---|---|
| Pre-campaign | Standard moderation baseline |
| Campaign | Elevated monitoring and parity checks |
| Silence period | Restrictive campaign-content posture |
| Voting day | Real-time escalation and high-priority review |
| Results period | Strict handling of premature or destabilizing claims |

## 11. Security and Threat Model

### 11.1 Threat Assumptions

- election-period DDoS and traffic spikes;
- well-resourced intrusion attempts;
- insider abuse and politicized misuse;
- credential theft and interception;
- third-party API instability or withdrawal.

### 11.2 Security Controls

- TLS 1.3 in transit; strong encryption at rest and backup encryption.
- API keys + OAuth baseline; mTLS for high-risk clients.
- RBAC least privilege + just-in-time privileged elevation.
- mandatory MFA with hardware keys for privileged access.
- append-only audit logs with hash chaining for tamper evidence.
- continuous monitoring and incident playbooks for election events.

## 12. Data Architecture and Retention

| Store | Purpose | Retention | Access |
|---|---|---|---|
| Operational store | active moderation and queues | 30-90 days | restricted operations access |
| Decision record store | audit and appeals | up to 7 years | controlled legal and audit access |
| Analytics warehouse | aggregate reporting | long-term anonymized | privacy-protected research access |
| Cold archive/legal hold | compliance and legal preservation | policy-driven | tightly restricted |

Privacy baseline:

- minimize personal data collection;
- enforce strict access logging;
- expose anonymized aggregates for research.

## 13. Bias, Evaluation, and Model Governance

### 13.1 Deployment Stages

1. Shadow mode
2. Advisory mode
3. Supervised enforcement
4. Higher autonomy after sustained performance evidence

### 13.2 Evaluation Requirements

- report precision, recall, F1 by language and by harm category;
- track false positives on legitimate political speech;
- monitor subgroup disparities and drift;
- define rollback triggers when quality or fairness thresholds are breached.

## 14. Integrations and Dependency Resilience

- All platform integrations must be connector-based and replaceable.
- Fallback paths include partner submissions and community monitoring inputs.
- Outbound webhooks require retries, exponential backoff, circuit breaking, and payload signing.

## 15. Technology and Delivery Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12+ |
| API | FastAPI (async) |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| Packaging | uv workspace |
| Testing | pytest + pytest-asyncio |
| Linting | ruff |
| Type checks | pyright |
| Dev runtime | Docker Compose |
| Production trajectory | Kubernetes |
| CI/CD | GitHub Actions |
| License | Apache 2.0 |

## 16. Delivery Roadmap (24 Months)

### Phase 1 (Months 1-6): Foundation

- Core API, language router, normalization pipeline.
- Language Pack framework with Tier 1 packs.
- Hate-Lex baseline, versioning, and audit logging.
- Hot-path latency and reliability baseline.

### Phase 2 (Months 7-12): Intelligence Integration

- Multi-label inference integration and optimization.
- Semantic retrieval and narrative matching.
- Shadow to advisory rollout gates.
- Bias audit baseline and reporting.

### Phase 3 (Months 13-18): Election Readiness

- Surge scaling and failover hardening.
- Monitoring and update pipeline for emerging terms.
- Weekly release cadence for packs and lexicon.
- Appeals and transparency workflow completion.

### Phase 4 (Months 19-24): Scale and Sustainability

- Tier 2 language expansion.
- Partner SLAs and governance charter finalization.
- Independent evaluation and public reporting framework.
- ML readiness execution wave tracked in `docs/specs/rfcs/0005-ml-readiness-execution-wave.md`.

## 17. Open Source and Community Operating Model

### 17.1 Repository Standards

- monorepo with internal packages: `core`, `router`, `lexicon`, `langpack`, `api`;
- staged migration from current single-package runtime into package boundaries tracked in `docs/specs/adr/0008-staged-package-boundary-migration.md`;
- shared test, seed, and scripts directories;
- mandatory PR template, issue templates, and contribution guides.

### 17.2 Community Safeguards

- contribution pathways for language packs and lexicon proposals;
- documented review criteria and approval workflow;
- code of conduct and transparent governance roles.

## 18. V1 Boundaries (Explicitly Out of Scope)

- image and meme OCR pipeline;
- cross-platform moderator UI parity;
- full multi-tenant enterprise controls;
- federated learning;
- blockchain-backed audit extensions.

## 19. Verification Checklist

1. Environment boots with Postgres, pgvector, Redis, and API.
2. Health endpoint passes.
3. Seed data loads and versions correctly.
4. Harmful test cases return `BLOCK` with valid evidence and reason codes.
5. Benign political cases return `ALLOW` without harmful labels.
6. Code-switched cases return accurate `language_spans`.
7. Unit and integration test suites pass.
8. Per-language benchmark reports generate successfully.
9. Latency remains below P95 <150ms on hot path under expected load.
10. Formal go-live gate package is approved per `docs/specs/phase4/i408-go-live-readiness-gate.md`.
11. `model_version` semantics and model artifact provenance are documented and auditable.

## 20. Key Decisions Pending

1. Primary governance body for lexicon and policy updates.
2. Cloud region strategy for East Africa latency and legal requirements.
3. Sustainability model across grants, institutional partners, and service tiers.
4. First multi-label inference model family and shadow promotion criteria.

Resolved decision:

- Tier 2 language priority order is ratified in `docs/specs/phase4/i401-tier2-language-priority-and-gates.md`.
- Deterministic claim-likeness baseline is integrated per `docs/specs/phase4/i412-disinfo-claim-likeness-baseline.md`.
- Initial embedding strategy remains `hash-bow-v1` (64-dim baseline) per `I-415` bakeoff report: `docs/specs/benchmarks/i415-embedding-selection-report-2026-02-13.md`.

## 21. Stakeholder Engagement and Risk Register

### 21.1 Priority Stakeholders

| Stakeholder Group | Primary Interest | Delivery Risk | Engagement Pattern |
|---|---|---|---|
| Regulatory and election institutions | Legal compliance and electoral integrity | Politicization or capture pressure | Transparent audit interfaces and independent oversight pathways |
| Media houses and digital publishers | Safe publishing and reduced legal exposure | Low trust if false positives are high | Clear SLAs, appeals workflows, and editorial-safe escalation modes |
| Civil society and community groups | Rights protection and accountability | Distrust of opaque moderation | Shared governance touchpoints and public transparency reports |
| Fact-check and research partners | Evidence quality and narrative verification | Data access friction | Structured data sharing with privacy-preserving controls |
| Platform and connector providers | Operational integration | API policy shifts and deprecations | Connector abstraction, fallback modes, and resilience drills |

### 21.2 Core Program Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Code-switching misclassification at scale | High | Span-level routing, pack-specific thresholds, targeted eval sets |
| Political-bias perception due to uneven flag rates | Critical | Party-blind audits, subgroup metrics, independent review cadence |
| Chilling legitimate speech through over-blocking | Critical | Conservative defaults, review-first policy for ambiguous content, appeals guarantees |
| Election-day DDoS or surge-induced downtime | Critical | Capacity pre-provisioning, rate controls, and failover playbooks |
| Third-party API withdrawal or degraded access | High | Connector abstraction and alternative ingestion channels |
| Slow lexicon updates during campaign peaks | High | Weekly release train, emergency fast-track workflow, rollback-ready versioning |
