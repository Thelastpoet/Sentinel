# API Reference

Sentinel exposes 13 endpoints across four groups: public, moderation, admin, and internal.

## Authentication summary

| Endpoint group | Auth method | Header |
|---------------|-------------|--------|
| Public (`/health`, `/metrics`, `/metrics/prometheus`) | None | — |
| Moderation (`/v1/moderate`) | API key | `X-API-Key` |
| Admin (`/admin/*`) | OAuth bearer token | `Authorization: Bearer <token>` |
| Internal (`/internal/*`) | OAuth bearer token | `Authorization: Bearer <token>` |

## Public endpoints

### `GET /health`

Returns API health status.

**Response** `200 OK`

```json
{"status": "ok"}
```

### `GET /metrics`

Returns runtime counters in JSON.

**Response** `200 OK`

```json
{
  "action_counts": {"ALLOW": 150, "REVIEW": 23, "BLOCK": 7},
  "http_status_counts": {"200": 180, "400": 2, "429": 1},
  "latency_ms_buckets": {"le_50ms": 100, "le_100ms": 50, "le_150ms": 20},
  "validation_error_count": 2
}
```

### `GET /metrics/prometheus`

Returns Prometheus exposition text (`text/plain`).

## Moderation endpoint

### `POST /v1/moderate`

Primary moderation endpoint.

**Authentication**: `X-API-Key` header

**Request body**

```json
{
  "text": "Content to moderate",
  "context": {
    "source": "forum-post",
    "locale": "ke",
    "channel": "politics"
  },
  "request_id": "client-correlation-id"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `text` | string | Yes | 1-5000 chars |
| `context.source` | string | No | max 100 |
| `context.locale` | string | No | max 20 |
| `context.channel` | string | No | max 50 |
| `request_id` | string | No | max 128 |

**Response** `200 OK`

```json
{
  "toxicity": 0.9,
  "labels": ["INCITEMENT_VIOLENCE"],
  "action": "BLOCK",
  "reason_codes": ["R_INCITE_CALL_TO_HARM"],
  "evidence": [
    {
      "type": "lexicon",
      "match": "kill",
      "severity": 3,
      "lang": "en",
      "match_id": null,
      "similarity": null,
      "span": null,
      "confidence": null
    }
  ],
  "language_spans": [{"start": 0, "end": 26, "lang": "en"}],
  "model_version": "sentinel-multi-v2",
  "lexicon_version": "hatelex-v2.1",
  "pack_versions": {"en": "pack-en-0.1", "sw": "pack-sw-0.1", "sh": "pack-sh-0.1"},
  "policy_version": "policy-2026.11",
  "latency_ms": 12
}
```

| Field | Type |
|-------|------|
| `toxicity` | float (0..1) |
| `labels` | enum[] (`ETHNIC_CONTEMPT`, `INCITEMENT_VIOLENCE`, `HARASSMENT_THREAT`, `DOGWHISTLE_WATCH`, `DISINFO_RISK`, `BENIGN_POLITICAL_SPEECH`) |
| `action` | `ALLOW` \| `REVIEW` \| `BLOCK` |
| `reason_codes` | string[] (`R_[A-Z0-9_]+`) |
| `evidence` | `EvidenceItem[]` |
| `language_spans` | `LanguageSpan[]` |
| `model_version` | string |
| `lexicon_version` | string |
| `pack_versions` | object |
| `policy_version` | string |
| `latency_ms` | integer |

**EvidenceItem fields**

| Field | Type | Notes |
|-------|------|-------|
| `type` | `lexicon` \| `vector_match` \| `model_span` | required |
| `match` | string or null | optional |
| `severity` | int (1..3) or null | optional |
| `lang` | string or null | optional |
| `match_id` | string or null | optional |
| `similarity` | float (0..1) or null | vector matches |
| `span` | string or null | model-derived evidence |
| `confidence` | float (0..1) or null | model-derived evidence |

**Moderation error responses**

| Status | `error_code` | Meaning |
|--------|--------------|---------|
| 400 | `HTTP_400` | Invalid request payload |
| 401 | `HTTP_401` | Missing or invalid API key |
| 429 | `HTTP_429` | Rate limited |
| 500 | `HTTP_500` | Internal server error |
| 503 | `HTTP_503` | API key auth not configured on server |

## Admin: Appeals

### Appeal state machine

```text
submitted -> triaged -> in_review -> resolved_upheld
                                -> resolved_reversed
                                -> resolved_modified
         -> rejected_invalid
```

### `POST /admin/appeals`

Create an appeal.

**OAuth scope**: `admin:appeal:write`

**Request body**

```json
{
  "original_decision_id": "decision-uuid",
  "request_id": "request-uuid",
  "original_action": "BLOCK",
  "original_reason_codes": ["R_INCITE_CALL_TO_HARM"],
  "original_model_version": "sentinel-multi-v2",
  "original_lexicon_version": "hatelex-v2.1",
  "original_policy_version": "policy-2026.11",
  "original_pack_versions": {"en": "pack-en-0.1"},
  "rationale": "User disputed the decision"
}
```

**Response** `200 OK`: `AdminAppealRecord`

### `GET /admin/appeals`

List appeals.

**OAuth scope**: `admin:appeal:read`

**Query params**: `status`, `request_id`, `limit` (1..200, default 50)

**Response** `200 OK`

```json
{
  "total_count": 1,
  "items": [
    {
      "id": 1,
      "status": "submitted",
      "request_id": "request-uuid",
      "original_decision_id": "decision-uuid",
      "original_action": "BLOCK",
      "original_reason_codes": ["R_INCITE_CALL_TO_HARM"],
      "original_model_version": "sentinel-multi-v2",
      "original_lexicon_version": "hatelex-v2.1",
      "original_policy_version": "policy-2026.11",
      "original_pack_versions": {"en": "pack-en-0.1"},
      "submitted_by": "admin-dashboard",
      "reviewer_actor": null,
      "resolution_code": null,
      "resolution_reason_codes": null,
      "created_at": "2026-01-15T10:30:00Z",
      "updated_at": "2026-01-15T10:30:00Z",
      "resolved_at": null
    }
  ]
}
```

### `POST /admin/appeals/{appeal_id}/transition`

Transition an appeal.

**OAuth scope**: `admin:appeal:write`

**Path param**: `appeal_id` (integer >= 1)

**Request body**

```json
{
  "to_status": "in_review",
  "rationale": "Escalating",
  "resolution_code": null,
  "resolution_reason_codes": null
}
```

**Response** `200 OK`: updated `AdminAppealRecord`

### `GET /admin/appeals/{appeal_id}/reconstruct`

Get full reconstruction for one appeal.

**OAuth scope**: `admin:appeal:read`

**Path param**: `appeal_id` (integer >= 1)

**Response** `200 OK`

```json
{
  "appeal": {"id": 1, "status": "in_review"},
  "timeline": [{"id": 2, "appeal_id": 1, "from_status": "submitted", "to_status": "triaged", "actor": "admin-dashboard", "rationale": "valid", "created_at": "2026-01-15T11:00:00Z"}],
  "artifact_versions": {
    "model": "sentinel-multi-v2",
    "lexicon": "hatelex-v2.1",
    "policy": "policy-2026.11",
    "pack": {"en": "pack-en-0.1"}
  },
  "original_reason_codes": ["R_INCITE_CALL_TO_HARM"],
  "resolution": {
    "status": null,
    "resolution_code": null,
    "resolution_reason_codes": null,
    "reviewer_actor": null,
    "resolved_at": null
  }
}
```

## Admin: Transparency

### `GET /admin/transparency/reports/appeals`

Aggregate appeals report.

**OAuth scope**: `admin:transparency:read`

**Query params**: `created_from`, `created_to` (ISO-8601 datetime)

**Response** `200 OK`

```json
{
  "generated_at": "2026-02-13T12:00:00Z",
  "total_appeals": 42,
  "open_appeals": 5,
  "resolved_appeals": 37,
  "backlog_over_72h": 2,
  "reversal_rate": 0.15,
  "mean_resolution_hours": 18.5,
  "status_counts": {
    "submitted": 3,
    "triaged": 1,
    "in_review": 1,
    "resolved_upheld": 20,
    "resolved_reversed": 5,
    "resolved_modified": 7,
    "rejected_invalid": 5
  },
  "resolution_counts": {
    "resolved_upheld": 20,
    "resolved_reversed": 5,
    "resolved_modified": 7
  }
}
```

### `GET /admin/transparency/exports/appeals`

Raw appeals export.

**OAuth scope**: `admin:transparency:export`

**Extra scope when `include_identifiers=true`**: `admin:transparency:identifiers`

**Query params**: `created_from`, `created_to`, `include_identifiers` (default `false`), `limit` (1..5000, default `200`)

**Response** `200 OK`

```json
{
  "generated_at": "2026-02-13T12:00:00Z",
  "include_identifiers": false,
  "total_count": 1,
  "records": [
    {
      "appeal_id": 1,
      "status": "resolved_upheld",
      "original_action": "BLOCK",
      "original_reason_codes": ["R_INCITE_CALL_TO_HARM"],
      "resolution_status": "resolved_upheld",
      "resolution_code": "decision_correct",
      "resolution_reason_codes": ["R_INCITE_CALL_TO_HARM"],
      "artifact_versions": {
        "model": "sentinel-multi-v2",
        "lexicon": "hatelex-v2.1",
        "policy": "policy-2026.11",
        "pack": {"en": "pack-en-0.1"}
      },
      "request_id": null,
      "original_decision_id": null,
      "transition_count": 3,
      "created_at": "2026-01-15T10:30:00Z",
      "resolved_at": "2026-01-16T14:00:00Z"
    }
  ]
}
```

## Admin: Release proposals

### `GET /admin/release-proposals/permissions`

Returns actor identity and scopes.

**OAuth scope**: `admin:proposal:read`

**Response** `200 OK`

```json
{
  "status": "ok",
  "actor_client_id": "admin-dashboard",
  "scopes": ["admin:proposal:read", "admin:proposal:review"]
}
```

### `POST /admin/release-proposals/{proposal_id}/review`

Submit a review action.

**OAuth scope**: `admin:proposal:review`

**Path param**: `proposal_id` (integer >= 1)

**Request body**

```json
{
  "action": "approve",
  "rationale": "Reviewed and accepted"
}
```

`action` values: `submit_review`, `approve`, `reject`, `request_changes`, `promote`

**Response** `200 OK`

```json
{
  "proposal_id": 12,
  "action": "approve",
  "actor": "admin-dashboard",
  "status": "accepted",
  "rationale": "Reviewed and accepted"
}
```

## Internal monitoring

### `GET /internal/monitoring/queue/metrics`

Queue metrics snapshot.

**OAuth scope**: `internal:queue:read`

**Response** `200 OK`

```json
{
  "queue_depth_by_priority": {"critical": 0, "urgent": 1, "standard": 3, "batch": 9},
  "sla_breach_count_by_priority": {"critical": 0, "urgent": 0, "standard": 0, "batch": 1},
  "actor_client_id": "ops-service"
}
```

## Error response format

All API errors use this shape:

```json
{
  "error_code": "HTTP_400",
  "message": "Invalid request payload (1 validation error(s))",
  "request_id": "abc-123"
}
```

## Rate-limiting headers (`POST /v1/moderate`)

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Max requests per window |
| `X-RateLimit-Remaining` | Remaining requests in current window |
| `X-RateLimit-Reset` | Seconds until window resets |
| `Retry-After` | Seconds to wait (`429` only) |
