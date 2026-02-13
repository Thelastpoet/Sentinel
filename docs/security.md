# Security Notes

## API access

- Set a strong `SENTINEL_API_KEY`.
- Do not expose the API key to frontend clients.

## Admin/internal access

Use OAuth/JWT configuration for internal and admin endpoints.

## Data handling

- Store moderation decisions and evidence for auditability.
- Avoid storing unnecessary personal data in logs.

## Operational controls

- Run release gates before production rollout.
- Keep backups for Postgres.
- Monitor health and error rates continuously.
