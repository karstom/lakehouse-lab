# V3 Open Questions

> Draft · 2026-09-25. Each question names how it gets resolved. When resolved, record the
> answer here and update the relevant ADR.

| ID | Question | Resolved by | Current lean |
|---|---|---|---|
| **OQ-1** | Does SeaweedFS STS work with Lakekeeper vending well enough for DuckDB? | Spike S-2 | ✅ **Resolved: yes.** SeaweedFS 4.47 + Lakekeeper v0.13.6 + DuckDB 1.5.5: reads and INSERTs work with vended credentials limited to one table. STS is now required for Trino as well (ADR-006) |
| **OQ-2** | Spark Connect or classic standalone driver in workspaces? | Spike S-4 | ✅ **Resolved: Spark Connect by default.** ~2 MB client, no JVM, sessions isolated. Classic-driver image variant is opt-in (+722 MB, ~466 MB JVM per user). How Spark Connect authenticates users is now OQ-15 |
| **OQ-3** | How do beginners trust Caddy's local CA for `*.lab.localhost` / `sslip.io`? | Spike S-3 | ✅ **Resolved.** Plain HTTP is only viable on `*.localhost`; on `sslip.io` it breaks PKCE, Secure cookies and the Trino UI. Remote installs import the Caddy root once (the installer generates it and keeps it safe from upgrades), or use a real domain with ACME |
| **OQ-4** | Real RAM floor for `core`: does it fit a 16 GB laptop with room for work? | Spike S-5 → Phase 1 load test | ⏳ **Partly answered.** Idle use is low: the S-3 SSO stack used 2.4 GB (Keycloak 0.6, Trino 0.7), S-1 used 1.3 GB, and a workspace uses 0.2 GB. Configured limits add up to 11–14.5 GB per spike. A realistic load test is needed before setting the limits |
| **OQ-5** | Lakekeeper authorization: OpenFGA (fine-grained) or allow-all + group-level checks? | Phase 1 | ✅ **Resolved: OpenFGA adopted.** Bootstrap stays click-free (one Lakekeeper role per Keycloak group); smoke 6/6 passes under both OpenFGA and the `allowall` fallback |
| **OQ-6** | Is Kubernetes in scope for any 3.x release? | Owner decision | No for 3.0; revisit after release |
| **OQ-7** | Which model gateway? | Phase 5 design | An OpenAI/Anthropic-compatible proxy with per-user keys and budgets (e.g. LiteLLM); evaluate against Jupyter AI v3 and Claude Code configuration |
| **OQ-8** | Default AI providers and data policy: hosted models on by default, or local-only until an admin opts in? | Owner decision | Off until the admin configures it; installer asks. Local-model add-on for private datasets |
| **OQ-9** | Which Trino MCP server: adopt a community one or write a thin read-only one? | Phase 5 evaluation | Adopt if it can pass through the user's token; otherwise a thin wrapper |
| **OQ-10** | Where does learning-track content live: this repo or a separate content repo? | Phase 4 | Separate repo, pinned by version in `versions.env`, so lessons can change without a stack release |
| **OQ-11** | Keep Portainer at all, given Keycloak + Console cover most of what it offered? | Phase 3 | Add-on only |
| **OQ-12** | License and support statement for V3 (MIT retained?), plus a note on Garage/AGPL if it's ever offered as an alternative store | Owner decision | Keep MIT; ship only permissively licensed components in core |
| **OQ-13** | Credential refresh: do Trino, DuckDB and Spark renew vended STS credentials after the 1-hour expiry during long jobs? | Phase 1 test | Not exercised in the spikes. Multi-TB Spark jobs use remote signing, so they aren't affected |
| **OQ-14** | Lakekeeper caches STS credentials, so a revoked grant can keep working for up to 1 hour. Acceptable? | Phase 1, with OQ-5 | Probably acceptable for a lab; document it, and shorten the credential lifetime if needed |
| **OQ-15** | Spark Connect authentication and topology: one shared Connect server or one per user? How is the user's identity carried to the catalog? | Phase 2 design | One shared server with per-session identity if Lakekeeper can take the user token; otherwise one per user |
| **OQ-16** | Airflow authorization: keep the UMA permission setup as a scripted bootstrap step, or export it into the realm template? | Phase 1 | Scripted step, because the export must be regenerated whenever the provider version changes |
| **OQ-17** | Trino group-based access control: which group provider (file, LDAP from Keycloak, custom)? | Phase 1 | ✅ **Resolved: file-based rules + file group provider.** The group file is generated from Keycloak by bootstrap (refreshes every 15 s). The viewer write denial is verified by smoke check 5 |
| **OQ-18** | Limit GitHub logins to members of a GitHub organization or team? Keycloak's built-in GitHub provider may not check organization membership, so this could need a custom mapper or an extra approval step | Phase 3 (ADR-016) | Start with "no group until an admin approves"; add an org check only if classroom use needs self-service |
| **OQ-19** | Trino 483 can't pass the user's identity to Lakekeeper, so catalog rules for SQL users are enforced in Trino, not Lakekeeper. Is keeping two rule sets (Trino rules + OpenFGA) acceptable, or should one be generated from the other? | Phase 2 | Generate both from Keycloak groups in bootstrap (already done for Trino's groups); revisit if Trino adds user sessions for the REST catalog |
| **OQ-20** | Group changes reach Trino and Lakekeeper only when bootstrap re-runs. Add `lab sync` or a periodic sync? | Phase 2 | A `lab sync` command now; a periodic sidecar only if classrooms need it |
