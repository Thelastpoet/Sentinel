# API Reference

## `GET /health`

Returns service status.

Example response:

```json
{"status":"ok"}
```

## `GET /metrics`

Returns runtime counters and latency buckets.

## `POST /v1/moderate`

Moderates input text.

### Request

```json
{
  "text": "They should kill them now.",
  "request_id": "optional-client-id"
}
```

### Response (shape)

```json
{
  "toxicity": 0.9,
  "labels": ["INCITEMENT_VIOLENCE"],
  "action": "BLOCK",
  "reason_codes": ["R_INCITE_CALL_TO_HARM"],
  "evidence": [],
  "language_spans": [],
  "model_version": "...",
  "lexicon_version": "...",
  "pack_versions": {},
  "policy_version": "...",
  "latency_ms": 42
}
```

For strict machine contract files, see `contracts/api/openapi.yaml` and `contracts/schemas/`.
