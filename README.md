# Sentinel

Open-source election-safety moderation API built to help protect Kenya's 2027 general election from ethnic incitement and election disinformation.

Sentinel currently supports code-switched moderation across English (`en`), Swahili (`sw`), and Sheng (`sh`) in the live moderation hot path. Language-pack artifacts for additional languages (including Luo and Kalenjin) are included for operator evaluation and staged rollout, but are not active in default hot-path enforcement.

Sentinel returns deterministic moderation decisions (`ALLOW`, `REVIEW`, or `BLOCK`) with full audit evidence, so every action can be explained and appealed.

## Who is this for?

**Platform integrators** — You run a forum, news platform, or civic tech tool and need a moderation API. You send text, Sentinel returns a decision. Start with the [Integration Guide](docs/integration-guide.md).

**Self-host operators** — You want to deploy and manage a Sentinel instance for your organization. Start with the [Deployment Guide](docs/deployment.md).

Both audiences should begin with the [Quickstart](docs/quickstart.md).

## Capability Snapshot

- **Available now (default runtime)**: moderation routing and enforcement for `en`, `sw`, `sh`
- **Included but not default-active**: additional language-pack artifacts (e.g., Luo, Kalenjin)
- **Contract stability**: `POST /v1/moderate` is the stable integration surface; admin/internal interfaces are operator-oriented and can evolve

## What Sentinel returns

```jsonc
{
  "toxicity": 0.92,
  "labels": ["INCITEMENT_VIOLENCE"],
  "action": "BLOCK",
  "reason_codes": ["R_INCITE_CALL_TO_HARM"],
  "evidence": [
    {
      "type": "lexicon",
      "match": "kill",
      "severity": 3,
      "lang": "en"
    }
  ],
  "language_spans": [
    {"start": 0, "end": 26, "lang": "en"}
  ],
  "model_version": "sentinel-multi-v2",
  "lexicon_version": "hatelex-v2.1",
  "pack_versions": {"en": "pack-en-0.1", "sw": "pack-sw-0.1", "sh": "pack-sh-0.1"},
  "policy_version": "policy-2026.11",
  "latency_ms": 12
}
```

Every response includes the evidence that drove the decision, the versions of all artifacts involved, and the latency of the call. This is the audit trail for appeals and transparency reporting.

## Key concepts

**6 labels**: `ETHNIC_CONTEMPT`, `INCITEMENT_VIOLENCE`, `HARASSMENT_THREAT`, `DOGWHISTLE_WATCH`, `DISINFO_RISK`, `BENIGN_POLITICAL_SPEECH`

**3 actions**: `ALLOW` (publish), `REVIEW` (hold for human moderator), `BLOCK` (reject)

**3 deployment stages**: `SHADOW` (log-only, no enforcement) -> `ADVISORY` (blocks downgraded to review) -> `SUPERVISED` (full enforcement). Roll out safely with progressive stages.

**5 electoral phases**: `PRE_CAMPAIGN` -> `CAMPAIGN` -> `SILENCE_PERIOD` -> `VOTING_DAY` -> `RESULTS_PERIOD`. Sensitivity thresholds tighten automatically as election day approaches.

## Quickstart

```bash
git clone https://github.com/Thelastpoet/sentinel.git && cd sentinel
pip install -e .[dev,ops]
docker compose up -d --build postgres redis
make apply-migrations && make seed-lexicon
export SENTINEL_API_KEY='your-key-here' && make run
```

See the full [Quickstart guide](docs/quickstart.md) for detailed instructions.

### Hardened Docker entrypoint (recommended for public hosting)

If you're deploying Sentinel on a host that is reachable from the public internet, run it behind a reverse proxy and do **not** expose operator endpoints (`/metrics*`, `/admin/*`, `/internal/*`) publicly.

This repo includes a hardened Compose file that exposes only `/health` and `/v1/moderate` on port 8000:

```bash
export SENTINEL_API_KEY='replace-with-a-strong-key'
docker compose -f docker-compose.hardened.yml up -d --build
```

## Project maturity

Sentinel ships with a **7-term demonstration seed lexicon**. This is enough to validate the system works end-to-end, but production deployment requires building out your own lexicon with domain-expert annotation.

The multi-label classifier currently runs in **shadow mode** (observability only). Claim-likeness scoring is active but **REVIEW-only** (it cannot produce `BLOCK`). Deterministic lexicon matches remain the only direct path to `BLOCK`.

## Documentation

| Document | Audience | Description |
|----------|----------|-------------|
| [Quickstart](docs/quickstart.md) | Both | Get running in 5 minutes |
| [Integration Guide](docs/integration-guide.md) | Integrators | Full request/response reference and enforcement patterns |
| [Deployment Guide](docs/deployment.md) | Operators | Infrastructure, configuration, and operations |
| [API Reference](docs/api-reference.md) | Both | All 13 endpoints documented |
| [Security](docs/security.md) | Operators | Authentication, authorization, and safety architecture |
| [FAQ](docs/faq.md) | Both | Common questions for integrators and operators |

Machine-readable public moderation contract: [`contracts/api/openapi.yaml`](contracts/api/openapi.yaml) and [`contracts/schemas/`](contracts/schemas/)

## Contributing

Contributions are welcome. Please open an issue to discuss significant changes before submitting a pull request.

## License

Apache-2.0. See [LICENSE](LICENSE).
