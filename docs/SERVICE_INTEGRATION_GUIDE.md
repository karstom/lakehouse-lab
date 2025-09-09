# Lakehouse Lab Service Integration Guide

This guide provides step-by-step recipes for adding new services (databases, dashboards, monitoring tools, etc.) to Lakehouse Lab using overlays, configuration, and test templates.

---

## 1. Directory Structure & Overlay Conventions

- Place contributed services in `/services/{service_name}/`
- Each service module should include:
  - `docker-compose.{service_name}.yml.example` (overlay)
  - `README.md` (service-specific docs)
  - Optional: config files, health scripts, etc.

**Example:**
```
/services/vizro/
  docker-compose.vizro.yml.example
  README.md
  config/
```

---

## 2. Creating a Docker Compose Overlay

- Copy an existing overlay (e.g., `docker-compose.newservice.yml.example`)
- Update service name, image, ports, environment, and dependencies
- Use environment variables for secrets and configuration

**Example:**
```yaml
# docker-compose.vizro.yml.example
services:
  vizro:
    image: ghcr.io/example/vizro:latest
    ports:
      - "8080:8080"
    environment:
      VIZRO_CONFIG: /config/vizro.yaml
      VIZRO_SECRET: ${VIZRO_SECRET}
    volumes:
      - ./services/vizro/config:/config
    depends_on:
      - minio
      - postgres
```

---

## 3. Configuration & Environment Variables

- Document all required environment variables in the service README
- Provide sample `.env` entries
- Use `${VAR}` syntax in overlays for easy overrides

**Example:**
```
# .env.example additions
VIZRO_SECRET=changeme
```

---

## 4. Health & Integration Tests

- Copy and adapt [`tests/template_test_service.py`](../tests/template_test_service.py:1) for basic health/integration checks
- For regression testing, use [`tests/template_snapshot_test_service.py`](../tests/template_snapshot_test_service.py:1) and `snapshottest`
- Place new test files in `tests/` and update service/endpoint details

---

## 5. Documentation Requirements

- Each service must have a `/services/{service_name}/README.md` with:
  - Service description and purpose
  - Setup instructions (overlays, env vars, config)
  - Health check and integration test info
  - Troubleshooting tips

---

## 6. Example: Adding a New Dashboard Service

1. Create `/services/homer/` and add `docker-compose.homer.yml.example`
2. Write `/services/homer/README.md` with setup and usage details
3. Add health/integration test: `tests/test_homer.py`
4. Update `.env.example` with required variables
5. (Optional) Add config files or scripts as needed

---

## 7. Best Practices

- Use overlays for optional/isolated services
- Avoid hardcoding secrets; use environment variables
- Document all integration points and dependencies
- Provide clear test coverage for health and cross-service flows

---

For questions or to contribute improvements, see the main [`README.md`](../README.md:1) or open an issue.