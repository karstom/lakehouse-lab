# Resolved Regressions (Archive)

> Regressions that have been fully fixed. Kept here for historical reference — they inform
> invariants, watchlists, and future `REGRESSED_N_TIMES` counts.
> Do NOT delete resolved regressions — move them here from `regressions.md`.

---

<!-- Resolved regression nodes live here. Format is identical to regressions.md. -->
<!-- Mark resolved regressions with a ✅ suffix on the NODE ID label line. -->

---

## NODE: REG_DASHBOARD_SERVICE_CHURN
**Type:** Regression
**Priority:** LOW
**Label:** Landing-page dashboard service kept breaking ✅
**Summary:** The landing-page dashboard was swapped four times (Homer → Homepage → Dashy → static nginx) in about two months, each swap fixing host validation, API widgets, envsubst templating, config filenames, or localhost-vs-host-IP links. Resolved by removing the dashboard service entirely in v2.1.1.
**Tags:** dashboard, resolved
**REGRESSED_N_TIMES:** 9
**Edges:**
- FIXED_BY → DEC_REMOVE_DASHBOARD_FUNCTIONALITY_FOCUS_ON_8492: service removed
**Files:** `docker-compose.yml`, `scripts/configure-services.sh`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `b6382ff`, `8e7ac1d`, `082cfd4`, `fcc6af7`, `3e0bc64`, `48f973d`, `ba7cf5b`, `92ffb10`, `397126a`
