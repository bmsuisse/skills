# Azure Deployment

Procrastinate workers are long-running processes. On Azure, the typical pattern is:

- **Web App**: run the worker as a background process in the same startup script alongside your web server.
- **Container App**: run worker as a separate container (same image, different command) or alongside the web process in a startup script.

Both need Azure Database for PostgreSQL — map its connection details to `PG*` env vars.

## Environment variables

In Azure App Service or Container App, set:

```
PGHOST=<server>.postgres.database.azure.com
PGPORT=5432
PGDATABASE=<dbname>
PGUSER=<user>
PGPASSWORD=<password>
PROCRASTINATE_APP=myapp.procrastinate_app.app
```

For Azure PostgreSQL Flexible Server, SSL is required — add:
```
PGSSLMODE=require
```

---

## Azure Web App (Linux)

Set **Startup Command** in Configuration → General Settings to your startup script path, e.g. `/home/site/wwwroot/startup.sh`.

### `startup.sh`

```bash
#!/bin/bash
set -e

# Start worker in background
procrastinate --app="$PROCRASTINATE_APP" worker --concurrency=10 &

# Start web server
gunicorn myapp.wsgi:application --bind 0.0.0.0:8000 --workers 2
# FastAPI: uvicorn myapp.main:app --host 0.0.0.0 --port 8000
```

Make it executable: `git update-index --chmod=+x startup.sh`

### Notes

- The worker process dies if the web server exits — that's fine for App Service (the platform restarts the dyno).
- For high load, consider using **WebJobs** or a second App Service instance dedicated to the worker.
- Scale-out (multiple instances) is safe: procrastinate uses `SELECT ... FOR UPDATE SKIP LOCKED` so jobs are never double-processed.

---

## Azure Container App

### Option A — Separate worker Container App (recommended)

Deploy two Container Apps from the same image in the same Container Apps Environment:

**Web app** — uses the default `CMD` from your Dockerfile (e.g. `gunicorn`/`uvicorn`).

**Worker Container App** — override the startup command:

```yaml
# bicep / arm / az cli equivalent
command: ["procrastinate", "--app=myapp.procrastinate_app.app", "worker", "--concurrency=10"]
```

Azure CLI example:

```bash
az containerapp create \
  --name myapp-worker \
  --resource-group myRG \
  --environment myEnv \
  --image myregistry.azurecr.io/myapp:latest \
  --command "procrastinate --app=myapp.procrastinate_app.app worker --concurrency=10" \
  --min-replicas 1 --max-replicas 3 \
  --env-vars PGHOST=... PGDATABASE=... PGUSER=... PGPASSWORD=... PGSSLMODE=require
```

Scale rule: scale on CPU or a custom metric — not HTTP requests (workers don't serve HTTP).

### Option B — Single container startup script

Use the same `startup.sh` approach as Web App (Option B for simpler setups or cost savings):

```bash
#!/bin/bash
set -e
procrastinate --app="$PROCRASTINATE_APP" worker --concurrency=10 &
uvicorn myapp.main:app --host 0.0.0.0 --port 8000
```

Set as the container's `command` / entrypoint override.

## Schema migration tip

Run `schema --apply` only once per deployment (not on every worker replica). Use a Container App **Job** (one-shot) for the migration step in your CI/CD pipeline:

```bash
az containerapp job create \
  --name migrate \
  --resource-group myRG \
  --environment myEnv \
  --image myregistry.azurecr.io/myapp:latest \
  --replica-timeout 300 \
  --command "procrastinate --app=myapp.procrastinate_app.app schema --apply"
```
