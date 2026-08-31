# Optional: Postgres in Kubernetes, wired to chat-app

**Still not used by the actual chat-app deployment by default** — the main project runs
Postgres on AWS RDS on purpose (see the root README, "Why RDS instead of a Kubernetes
StatefulSet"). This folder is for a local/dev cluster (minikube/kind, or an EKS cluster
you don't want to attach RDS to yet) where you want the whole stack — including the
database — running in Kubernetes with nothing external.

## What's here

| File | Purpose |
|---|---|
| `postgres-secret.yaml` | Postgres's own credentials (`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`) |
| `postgres-service.yaml` | Headless Service — gives the pod a stable DNS name |
| `postgres-statefulset.yaml` | The database itself, with its own PersistentVolumeClaim |
| `database-config-override.yaml` | Re-points chat-app's `database-config` ConfigMap (`DB_HOST` etc.) at this Postgres instead of RDS |
| `database-secret-override.yaml` | Re-points chat-app's `database-secret` Secret (`DB_USERNAME`/`DB_PASSWORD`) to match this Postgres's credentials |

The last two are what actually **connect** chat-app to this database: the backend
Deployment (`k8s/backend-deployment.yaml`) already reads `DB_HOST`/`DB_USERNAME`/
`DB_PASSWORD` from ConfigMap/Secret objects named `database-config`/`database-secret` —
the same names these two overrides target — so applying them after the normal ones swaps
the backend over to this Postgres with **no changes needed to the backend Deployment
itself**.

## Deploy the whole stack, connected

```bash
# 1. Namespace
kubectl apply -f k8s/namespace.yaml

# 2. Postgres itself
kubectl apply -f k8s/optional-local-postgres/postgres-secret.yaml
kubectl apply -f k8s/optional-local-postgres/postgres-service.yaml
kubectl apply -f k8s/optional-local-postgres/postgres-statefulset.yaml

# wait for it to actually be ready before continuing
kubectl rollout status statefulset/postgres -n chat-app
kubectl get pods -n chat-app -l app=postgres

# 3. App config/secrets - apply the normal ones first (needed for
#    backend-config, frontend-config, backend-secret / JWT key)...
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

# ...then the two overrides, which replace *only* database-config /
# database-secret's data to point at Postgres instead of RDS
kubectl apply -f k8s/optional-local-postgres/database-config-override.yaml
kubectl apply -f k8s/optional-local-postgres/database-secret-override.yaml

# 4. The app itself - unmodified, it just picks up whichever DB_HOST/
#    DB_USERNAME/DB_PASSWORD are currently in those ConfigMap/Secret keys
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml
```

## Verify the connection

```bash
kubectl exec -n chat-app deploy/backend -- python -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/ready').read())"
# -> {"status":"ok","database":"reachable"}   means the backend reached Postgres successfully

kubectl logs -n chat-app deploy/backend | grep -i database
```

If `/ready` returns a 503 instead, check in order: is the `postgres-0` pod
`Running`/`1/1 Ready` (`kubectl get pods -n chat-app -l app=postgres`); did the two
override files actually apply *after* `k8s/configmap.yaml`/`k8s/secret.yaml`, not before
(`kubectl get configmap database-config -n chat-app -o yaml` should show `DB_HOST:
postgres-0.postgres...`, not an RDS endpoint or the placeholder); and did the backend pod
restart after the config changed (`kubectl rollout restart deployment/backend -n
chat-app` — ConfigMap/Secret edits aren't picked up by already-running pods
automatically).

## Switching back to RDS

Re-apply the originals — they overwrite the overrides the same way:
```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl rollout restart deployment/backend -n chat-app
```

## Why StatefulSet, not Deployment, for Postgres

A `Deployment`'s pods are interchangeable — any replica can be killed and replaced by an
identical one, which is exactly wrong for a database: replacing "a" Postgres pod isn't the
same as replacing "the one with your data on it." A `StatefulSet` gives the pod a
**stable identity** (`postgres-0`, not a random suffix) and its **own
PersistentVolumeClaim** that's re-attached to that same identity on reschedule — a
`Deployment` has no equivalent to `volumeClaimTemplates`.

## Why this project doesn't use it in production

Running Postgres yourself here means *you* now own: replication and failover, automated
backups and point-in-time recovery, minor-version patching, and storage expansion — all
things RDS does for you. It also ties the database's lifecycle to the cluster's: tearing
down/rebuilding EKS would otherwise take the data with it, unless you separately manage
backup/restore of the PVC. For a local/disposable cluster none of that matters and this is
the simpler path; for anything with real data, that operational cost is why RDS is the
better default — which is why `k8s/configmap.yaml` and `k8s/secret.yaml` in the main
deployment point at RDS, not at this StatefulSet.
