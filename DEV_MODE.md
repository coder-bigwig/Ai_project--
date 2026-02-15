# Development Mode

This repo can run in hot-reload mode for frontend development.

## Start

Run from repo root:

```
start-dev.bat
```

What it does:

- Starts backend containers: `training-postgres`, `training-redis`, `training-experiment-manager`, `training-ai-assistant`
- Stops production `training-frontend` and `training-nginx` to avoid stale content on `:8080`
- Starts React dev server on `http://localhost:3000` with hot reload

## Stop

Run from repo root:

```
stop-dev.bat
```

## Notes

- In dev mode, use `http://localhost:3000` (not `http://localhost:8080`).
- API requests go to `http://localhost:8001`.
- Quick backend-only check:

```
set SKIP_FRONTEND=1 && start-dev.bat
```

- To return to production-like static mode:

```
docker compose up -d frontend nginx
```
