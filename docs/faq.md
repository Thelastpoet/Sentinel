# FAQ

## General

### What is Sentinel?

Sentinel is an open-source election-safety moderation API built to help protect Kenya's 2027 general election from ethnic incitement and election disinformation. It currently supports code-switched moderation across English (`en`), Swahili (`sw`), and Sheng (`sh`), and returns deterministic moderation decisions (`ALLOW`, `REVIEW`, `BLOCK`) with full audit evidence.

### Is Sentinel production-ready?

The moderation pipeline, appeals system, transparency reporting, and safety controls are fully implemented. However:

- The **seed lexicon contains only 7 demonstration terms**. Production use requires building a comprehensive lexicon with domain-expert annotation covering the specific hate speech, incitement, and disinformation patterns relevant to your context.
- The **multi-label classifier runs in shadow mode** (observability only).
- The **claim-likeness scorer is active for REVIEW-only disinformation signals** (cannot produce `BLOCK`).
- Deterministic lexicon matches remain the only direct path to `BLOCK`.

Production rollout should follow the go-live readiness gate (`python scripts/check_go_live_readiness.py`) and the SHADOW -> ADVISORY -> SUPERVISED deployment stage progression.

### What languages does Sentinel support?

Sentinel currently supports three language codes in the moderation pipeline:

- **English (en)** — baseline deterministic support
- **Swahili (sw)** — baseline deterministic support with hint-word detection
- **Sheng (sh)** — baseline deterministic support with hint-word detection

Language routing is token-informed and returns span-level `language_spans`, so code-switched text (e.g., English + Sheng in one sentence) is handled natively.

Sentinel also includes language-pack artifacts for additional languages (currently Luo and Kalenjin), but these are for staged/operator rollout and are not active in the default moderation hot path.

### What are the six labels?

| Label | Meaning |
|-------|---------|
| `ETHNIC_CONTEMPT` | Ethnic slurs, dehumanizing language targeting ethnic groups |
| `INCITEMENT_VIOLENCE` | Direct calls to harm, kill, or attack |
| `HARASSMENT_THREAT` | Targeted personal threats |
| `DOGWHISTLE_WATCH` | Ambiguous language that may carry coded meaning — flagged for human review |
| `DISINFO_RISK` | Content resembling known disinformation narratives |
| `BENIGN_POLITICAL_SPEECH` | Normal political discourse, no policy concern detected |

---

## Integrators

### Can I call Sentinel from the browser?

No. Sentinel is a server-side API. Your backend should call Sentinel and apply the enforcement decision. Never expose the API key to frontend code.

### What should I do if Sentinel is unavailable?

Default to `REVIEW` for safety-critical content. Never default to `ALLOW` for content that hasn't been moderated. Set a request timeout of 500-1000ms and implement a circuit breaker pattern. See the [Integration Guide](integration-guide.md) for detailed failure handling recommendations.

### What do the labels mean for my moderation workflow?

The `action` field is your primary enforcement signal:
- `ALLOW` — publish the content
- `REVIEW` — hold for human moderator review
- `BLOCK` — reject publication

Labels and reason codes provide detail for moderators reviewing flagged content and for users who want to understand why their content was actioned.

### Can ML predictions auto-block content?

No. This is an intentional safety constraint. Only deterministic lexicon matches (exact normalized regex against known terms) can produce a `BLOCK` action. Vector similarity and claim-likeness paths are REVIEW-only. Multi-label classifier predictions operate in shadow mode and do not change enforcement. See [Security](security.md) for the full safety architecture.

### What is the text size limit?

1 to 5,000 characters. Empty strings are rejected (400 error). Text exceeding 5,000 characters is rejected.

### Can I use Sentinel for a small forum?

Yes. Integrate server-to-server with `POST /v1/moderate` and map the three actions to your moderation workflow. Sentinel runs without Postgres or Redis in development mode (file-based lexicon, in-memory rate limiting), but production use should include Postgres for the full feature set.

---

## Operators

### How do I switch electoral phases?

Set the `SENTINEL_ELECTORAL_PHASE` environment variable and restart the API:

```bash
export SENTINEL_ELECTORAL_PHASE=voting_day
```

The five phases are `pre_campaign`, `campaign`, `silence_period`, `voting_day`, and `results_period`. Each phase adjusts vector match thresholds and no-match behavior. During `silence_period`, `voting_day`, and `results_period`, unmatched content defaults to `REVIEW` instead of `ALLOW`. See the [Deployment Guide](deployment.md) for the full phase table.

### How do I manage the lexicon?

The lexicon follows a governed lifecycle: Draft -> Active -> Deprecated. Use the make targets:

```bash
make release-create       # Create a new draft release
make release-ingest       # Add terms to the draft
make release-validate     # Validate against quality gates
make release-activate     # Activate (deactivates previous active)
make release-deprecate    # Deprecate old releases
```

Only one release can be active at a time. The active release is what the moderation endpoint uses for matching. See the [Deployment Guide](deployment.md) for the full lexicon lifecycle.

### What is the recommended rollout path?

1. **SHADOW** — Deploy and route traffic. All decisions are downgraded to ALLOW. Log everything, analyze decision quality, tune the lexicon.
2. **ADVISORY** — BLOCK decisions are downgraded to REVIEW. Human moderators see what Sentinel would block. Build confidence in the lexicon.
3. **SUPERVISED** — Full enforcement. BLOCK actions are applied automatically.

Set the stage with `SENTINEL_DEPLOYMENT_STAGE=shadow|advisory|supervised`.

### How do I set up OAuth for admin endpoints?

For development, use a static token registry:

```bash
export SENTINEL_OAUTH_TOKENS_JSON='{"my-token": {"client_id": "admin", "scopes": ["admin:appeal:read", "admin:appeal:write"]}}'
```

For production, configure JWT validation:

```bash
export SENTINEL_OAUTH_JWT_SECRET='your-secret'
```

See the [Deployment Guide](deployment.md) for the full OAuth setup including all scopes.

### How do I set up monitoring?

Sentinel exposes three monitoring endpoints:

- `GET /health` — basic health check (no auth)
- `GET /health/live` — liveness probe (no auth)
- `GET /health/ready` — readiness probe (no auth)
- `GET /metrics` — JSON metrics: action counts, HTTP status counts, latency buckets (no auth)
- `GET /metrics/prometheus` — Prometheus text format for scraping (no auth)

For internal queue monitoring, use `GET /internal/monitoring/queue/metrics` with the `internal:queue:read` OAuth scope.

All requests carry an `X-Request-ID` header for log correlation.

### What is the go-live readiness gate?

The go-live gate validates that all required artifacts are present and consistent before production deployment:

```bash
python scripts/check_go_live_readiness.py --bundle-dir releases/go-live/<release-id>
```

It checks for a valid lexicon release, policy config, migration state, and launch profile. Use the template bundle in `templates/go-live/` as a starting point.
