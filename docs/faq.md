# FAQ

## Is Sentinel production-ready?

Core implementation tasks are complete. Production rollout should still follow the go-live readiness gate and sign-off process.

## Can Sentinel directly auto-block from ML predictions?

Initial ML paths are safety-constrained. Governance and policy controls determine whether model signals can enforce beyond advisory/shadow behavior.

## Do I need ML dependencies to use Sentinel?

No. Base deterministic moderation works without `.[ml]`. Install `.[ml]` only when you need optional ML runtime paths.

## Can I use this for a small forum?

Yes. Integrate server-to-server with `POST /v1/moderate` and map `ALLOW/REVIEW/BLOCK` to your moderation workflow.
