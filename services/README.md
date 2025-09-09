# Lakehouse Lab Services Directory

This directory is for contributed service modules. Each service should be placed in its own subdirectory, containing:

- A Docker Compose overlay file (e.g., `docker-compose.myservice.yml`)
- A configuration file or example `.env` (if needed)
- A `README.md` describing the service, integration steps, and any dependencies

## Example Structure

```
services/
  myservice/
    docker-compose.myservice.yml
    config.env.example
    README.md
```

## Contribution Guidelines

1. Create a new subdirectory for your service.
2. Add your Docker Compose overlay and any required config files.
3. Document the service, integration steps, and health checks in `README.md`.
4. Follow the template and best practices provided in `docker-compose.newservice.yml.example`.
5. Submit a pull request for review.
