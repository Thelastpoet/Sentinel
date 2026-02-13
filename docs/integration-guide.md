# Integration Guide

This guide is for platform integrators calling the Sentinel API from a backend application. It covers authentication, the full request/response schema, enforcement patterns, rate limiting, and error handling.

Sentinel is a server-side API. Never call it directly from a browser or mobile client — always proxy through your backend.

Default runtime language support for the moderation hot path is English (`en`), Swahili (`sw`), and Sheng (`sh`).

## Authentication

All moderation requests require an API key passed in the `X-API-Key` header:

```
X-API-Key: your-api-key
```

Keep this key server-side. If it leaks to a client, rotate it immediately.

## Request

### `POST /v1/moderate`

```json
{
  "text": "The content to moderate",
  "context": {
    "source": "forum-post",
    "locale": "ke",
    "channel": "politics"
  },
  "request_id": "your-unique-id-123"
}
```

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `text` | string | Yes | 1-5000 characters | The text to moderate |
| `context` | object | No | — | Optional metadata about the content source |
| `context.source` | string | No | Max 100 chars | Where the content came from (e.g., "forum-post", "comment") |
| `context.locale` | string | No | Max 20 chars | Geographic locale (e.g., "ke" for Kenya) |
| `context.channel` | string | No | Max 50 chars | Content channel or category |
| `request_id` | string | No | Max 128 chars | Client-provided idempotency/correlation ID |

If you don't provide `request_id`, Sentinel generates one and returns it in the `X-Request-ID` response header.

## Response

### Full response schema

```jsonc
{
  // Toxicity score (0.0-1.0). Higher = more toxic.
  "toxicity": 0.92,

  // Labels detected in the text (one or more).
  "labels": ["INCITEMENT_VIOLENCE"],

  // Enforcement decision.
  "action": "BLOCK",

  // Machine-readable codes explaining the decision.
  "reason_codes": ["R_INCITE_CALL_TO_HARM"],

  // Evidence items that drove the decision.
  "evidence": [
    {
      "type": "lexicon",
      "match": "kill",
      "severity": 3,
      "lang": "en"
    }
  ],

  // Detected language spans with character offsets.
  "language_spans": [
    {"start": 0, "end": 26, "lang": "en"}
  ],

  // Artifact versions (for audit trail).
  "model_version": "sentinel-multi-v2",
  "lexicon_version": "hatelex-v2.1",
  "pack_versions": {"en": "pack-en-0.1", "sw": "pack-sw-0.1", "sh": "pack-sh-0.1"},
  "policy_version": "policy-2026.11",

  // Server-side latency in milliseconds.
  "latency_ms": 12
}
```

### Labels

| Label | Description |
|-------|-------------|
| `ETHNIC_CONTEMPT` | Ethnic slurs, dehumanizing language targeting ethnic groups |
| `INCITEMENT_VIOLENCE` | Direct calls to harm, kill, or attack |
| `HARASSMENT_THREAT` | Targeted personal threats |
| `DOGWHISTLE_WATCH` | Ambiguous language that may carry coded meaning — requires human review |
| `DISINFO_RISK` | Content resembling known disinformation narratives (claim likeness match) |
| `BENIGN_POLITICAL_SPEECH` | No policy match — normal political discourse |

A response may contain multiple labels if multiple concerns are detected.

### Actions

| Action | Meaning | Recommended handling |
|--------|---------|---------------------|
| `ALLOW` | No policy concern detected | Publish the content |
| `REVIEW` | Potential concern detected | Hold for human moderator review |
| `BLOCK` | High-confidence policy violation | Reject publication |

During heightened electoral phases (`SILENCE_PERIOD`, `VOTING_DAY`, `RESULTS_PERIOD`), Sentinel tightens thresholds. Content that would receive `ALLOW` during `PRE_CAMPAIGN` may receive `REVIEW` during `VOTING_DAY`. Your application should handle this gracefully.

### Evidence types

Each evidence item has a `type` field indicating how the match was produced:

| Type | Description | Can produce BLOCK? |
|------|-------------|-------------------|
| `lexicon` | Deterministic match against a known term in the lexicon | Yes |
| `vector_match` | Semantic similarity match via pgvector | No (REVIEW only) |
| `model_span` | Heuristic/model-derived span evidence (e.g., claim-likeness or no-match context) | No |

The safety constraint that vector matches and model spans cannot produce `BLOCK` is intentional. Only deterministic lexicon matches can block content.

### Evidence item fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `lexicon`, `vector_match`, or `model_span` |
| `match` | string or null | Matched text/term (often null for `model_span`) |
| `severity` | integer or null | 1 (low), 2 (medium), 3 (high) when available |
| `lang` | string or null | Language code when available |
| `match_id` | string | Unique identifier for the matched entry (optional) |
| `similarity` | float | Cosine similarity score, 0.0-1.0 (vector matches only) |
| `span` | string | Text span context (model spans only, optional) |
| `confidence` | float | Confidence score, 0.0-1.0 (model spans only, optional) |

## Applying enforcement decisions

Basic integration pattern:

```python
response = requests.post(
    f"{SENTINEL_URL}/v1/moderate",
    json={"text": user_text, "request_id": post_id},
    headers={"X-API-Key": API_KEY},
    timeout=1.0,
)
result = response.json()

if result["action"] == "ALLOW":
    publish(post)
elif result["action"] == "REVIEW":
    enqueue_for_moderation(post, sentinel_response=result)
elif result["action"] == "BLOCK":
    reject(post, reason=result["reason_codes"])
```

Always persist the full Sentinel response alongside the content. You'll need it for appeals and audit.

## What to persist

Store these fields in your database alongside the moderated content:

| Field | Why |
|-------|-----|
| `action` | The enforcement decision applied |
| `labels` | What was detected |
| `reason_codes` | Machine-readable explanation |
| `evidence` | Full match details for appeal reconstruction |
| `model_version` | Which model version was used |
| `lexicon_version` | Which lexicon version was used |
| `policy_version` | Which policy config was active |
| `pack_versions` | Which language packs were active |
| `X-Request-ID` header | Correlation ID linking your records to Sentinel's |

This data enables reconstructing exactly why a decision was made, even if the lexicon or policy has since changed. The appeals system uses these fields to rebuild the decision context.

## Rate limiting

Sentinel enforces per-key rate limits (default: 120 requests/minute).

### Response headers

Successful moderation responses include rate limit headers. `429` responses include the same headers plus `Retry-After`.

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Maximum requests allowed per window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Reset` | Seconds until the window resets |

### 429 Too Many Requests

When rate limited, Sentinel returns HTTP 429 with:

- A `Retry-After` header indicating seconds to wait
- An `ErrorResponse` body

Implement exponential backoff or honor `Retry-After`. Do not retry immediately.

## Error handling

### Error response format

All errors return a consistent structure:

```json
{
  "error_code": "HTTP_400",
  "message": "Invalid request payload (1 validation error(s))",
  "request_id": "abc-123"
}
```

### HTTP status codes

| Status | Meaning | Action |
|--------|---------|--------|
| 200 | Success | Process the moderation response |
| 400 | Validation error (bad request body) | Fix the request — check `text` length (1-5000) and field types |
| 401 | Missing or invalid API key | Check `X-API-Key` header |
| 503 | API authentication not configured on the server | Operator must set `SENTINEL_API_KEY` |
| 429 | Rate limited | Wait for `Retry-After` seconds, then retry |
| 500 | Internal server error | Retry with backoff; default to REVIEW if persistent |

### Failure handling recommendations

- **Timeout**: Set a request timeout of 500-1000ms. Sentinel targets P95 latency under 150ms.
- **Unavailability**: If Sentinel is unreachable, default to `REVIEW` for safety-critical content. Never default to `ALLOW` for content that hasn't been checked.
- **Retries**: Retry on 500 and network errors with exponential backoff. Do not retry on 400 or 401.
- **Circuit breaker**: If Sentinel returns errors persistently, open a circuit breaker and route all content to your human moderation queue.
