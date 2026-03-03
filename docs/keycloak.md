# Keycloak (local dev) – Church Scheduler

All Keycloak-related assets live under `/keycloak`.

## Paths
- Realm import file: `keycloak/realm-churchschedule.json`
- Custom theme:
  - `keycloak/login/theme.properties`
  - `keycloak/login/resources/styles.css`

## Local URLs
- Streamlit app: http://localhost:8501
- Keycloak admin: http://localhost:8081

## Start local stack
From repo root:

```bash
docker compose --env-file .env.local -f docker-compose.local.yml up -d --build
```

## Hard reset Keycloak (wipe all realms/users)

```bash
docker compose --env-file .env.local -f docker-compose.local.yml down --remove-orphans
docker volume rm church-scheduler-local_pgdata_keycloak_local 2>/dev/null || true
docker compose --env-file .env.local -f docker-compose.local.yml up -d --build
```

## Restart app container:

```bash
docker compose --env-file .env.local -f docker-compose.local.yml up -d --build --force-recreate app
```