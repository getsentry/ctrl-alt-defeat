# Deployment (Google Cloud)

Everything runs in the GCP project `hackweek-ctrl-alt-defeat`, in the Hackweek
folder, region `us-central1`.

| Part | Where | URL |
|------|-------|-----|
| Client | Cloud Run `ctrl-alt-defeat-client` | https://ctrl-alt-defeat.sentry.gg |
| Server | Cloud Run `ctrl-alt-defeat-server` | https://ctrl-alt-defeat-backend.sentry.gg |
| Database | Cloud SQL `ctrl-alt-defeat-db`, Postgres 17, database `ctrl_alt_defeat`, user `app` | socket only |
| Images | Artifact Registry `us-central1-docker.pkg.dev/hackweek-ctrl-alt-defeat/ctrl-alt-defeat` | |
| Backups | Cloud SQL daily backups, plus `gs://hackweek-ctrl-alt-defeat-backups` | |

Secrets live in Secret Manager and reach the server as environment variables:
`database-url` → `DATABASE_URL`, `jwt-secret-key` → `JWT_SECRET_KEY`,
`stats-token` → `STATS_TOKEN`.

The server runs `alembic upgrade head` when it starts, so a deploy applies its
own migrations.

## Domains

Both `sentry.gg` names are A records to `136.82.30.205`, a global external load
balancer (`ctrl-alt-defeat-https`) that routes by host to the two services and
redirects HTTP to HTTPS. The certificate is Google-managed
(`ctrl-alt-defeat-cert-2`). The records live in `getsentry/ops`, in
`terragrunt/regions/multi-tenant/dns/zones-misc/sentry-gg/control/local.hcl`,
and are applied with TACOS.

The client talks to the server's `run.app` URL rather than its `sentry.gg`
name, so either can change without the other. Each service also still answers
on its `run.app` URL:

- https://ctrl-alt-defeat-server-206662247903.us-central1.run.app
- https://ctrl-alt-defeat-client-206662247903.us-central1.run.app

## Deploying

Build from a clean export of a commit, not from the working tree. An untracked
migration in the tree would get uploaded and run against the real database.

```bash
P=hackweek-ctrl-alt-defeat
REG=us-central1-docker.pkg.dev/${P}/ctrl-alt-defeat
SHA=$(git rev-parse --short HEAD)
BUILD=$(mktemp -d)
git archive HEAD server client | tar -x -C "$BUILD"
# gcloud falls back to .gitignore, which drops the tracked export_presets.cfg.
echo .gcloudignore > "$BUILD/client/.gcloudignore"
```

Server:

```bash
cd "$BUILD/server" && cp Dockerfile.production Dockerfile
gcloud builds submit --tag ${REG}/server:${SHA} --project ${P} .
gcloud run deploy ctrl-alt-defeat-server --image ${REG}/server:${SHA} \
  --region us-central1 --project ${P}
```

Client (the API URL is written into the export at build time):

```bash
cd "$BUILD/client"
cat > cloudbuild.yaml <<EOF
steps:
- name: gcr.io/cloud-builders/docker
  args: ["build", "--build-arg", "API_URL=https://ctrl-alt-defeat-server-206662247903.us-central1.run.app", "-t", "${REG}/client:${SHA}", "."]
images: ["${REG}/client:${SHA}"]
options:
  machineType: E2_HIGHCPU_8
EOF
gcloud builds submit --config cloudbuild.yaml --project ${P} .
gcloud run deploy ctrl-alt-defeat-client --image ${REG}/client:${SHA} \
  --region us-central1 --project ${P}
```

Use `${P}`, not `$P`, before a colon: zsh reads `$P:u` as "uppercase $P".

## Connecting to the database

```bash
cloud-sql-proxy --gcloud-auth --port 55432 hackweek-ctrl-alt-defeat:us-central1:ctrl-alt-defeat-db
psql -h 127.0.0.1 -p 55432 -U app -d ctrl_alt_defeat
```

The password is the one in the `database-url` secret.

## Local testing

```bash
docker-compose up --build
```
