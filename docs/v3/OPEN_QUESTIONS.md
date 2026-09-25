# V3 Open Questions

> Draft · 2026-09-25. Each question names how it gets resolved. When resolved, record the
> answer here and update the relevant ADR.

| ID | Question | Resolved by | Current lean |
|---|---|---|---|
| **OQ-1** | Does SeaweedFS STS work with Lakekeeper vending well enough for DuckDB? | Spike S-2 | Yes on ≥ 4.40, but there are reports of an incomplete STS implementation, so the fallback is kept ready |
| **OQ-2** | Spark Connect or classic standalone driver in workspaces? | Spike S-4 | Spark Connect: lighter workspace and cleaner per-user isolation; keep standalone for the Spark UI lessons |
| **OQ-3** | How do beginners trust Caddy's local CA for `*.lab.localhost` / `sslip.io`? | Spike S-3 | Installer offers to install the root CA; fall back to plain HTTP on `localhost` only |
| **OQ-4** | Real RAM floor for `core`: does it fit a 16 GB laptop with room for work? | Spike S-5 | Target ~12 GB; Keycloak and Trino are the big new costs |
| **OQ-5** | Lakekeeper authorization: OpenFGA (fine-grained) or allow-all + group-level checks? | Design review after S-1 | OpenFGA, since governance is a skill worth teaching, as long as bootstrap stays click-free |
| **OQ-6** | Is Kubernetes in scope for any 3.x release? | Owner decision | No for 3.0; revisit after release |
| **OQ-7** | Which model gateway? | Phase 5 design | An OpenAI/Anthropic-compatible proxy with per-user keys and budgets (e.g. LiteLLM); evaluate against Jupyter AI v3 and Claude Code configuration |
| **OQ-8** | Default AI providers and data policy: hosted models on by default, or local-only until an admin opts in? | Owner decision | Off until the admin configures it; installer asks. Local-model add-on for private datasets |
| **OQ-9** | Which Trino MCP server: adopt a community one or write a thin read-only one? | Phase 5 evaluation | Adopt if it can pass through the user's token; otherwise a thin wrapper |
| **OQ-10** | Where does learning-track content live: this repo or a separate content repo? | Phase 4 | Separate repo, pinned by version in `versions.env`, so lessons can change without a stack release |
| **OQ-11** | Keep Portainer at all, given Keycloak + Console cover most of what it offered? | Phase 3 | Add-on only |
| **OQ-12** | License and support statement for V3 (MIT retained?), plus a note on Garage/AGPL if it's ever offered as an alternative store | Owner decision | Keep MIT; ship only permissively licensed components in core |
