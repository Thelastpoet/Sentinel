# Integration Guide

Sentinel is a server-side moderation API. Your app sends text, Sentinel returns `ALLOW`, `REVIEW`, or `BLOCK` with audit evidence.

## Recommended flow

1. User submits content in your forum.
2. Your backend calls `POST /v1/moderate`.
3. Your backend applies enforcement:
   - `ALLOW`: publish
   - `REVIEW`: hold for moderator
   - `BLOCK`: reject publish
4. Store decision metadata for audit and appeals.

## Request example

```bash
curl -sS -X POST http://localhost:8000/v1/moderate \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: ${SENTINEL_API_KEY}" \
  -d '{"text":"Sample post"}'
```

## What to persist in your DB

- `action`
- `labels`
- `reason_codes`
- `evidence`
- `model_version`
- `lexicon_version`
- `policy_version`
- request ID (`X-Request-ID`)

## Failure handling

- Use request timeout (for example 500-1000ms).
- If Sentinel is unavailable, default to `REVIEW` for safety-critical contexts.
- Never call Sentinel directly from the browser; call from your backend only.
