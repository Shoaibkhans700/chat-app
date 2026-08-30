# chat-app

A small, real-shaped chat application built specifically to practice and demonstrate a
**production-style DevOps pipeline**: Docker → Kubernetes (EKS) → Jenkins CI → Amazon ECR →
Argo CD (GitOps) → AWS RDS. The application itself (login, register, 1:1 chat) is
intentionally simple — the point of this project is the path code takes from a `git push`
to running safely in a cluster, talking to a managed database.

```
chat-app/
├── backend/          FastAPI + SQLAlchemy + PostgreSQL
├── frontend/          React (Vite) + Nginx
├── k8s/                Kubernetes manifests (apply these to EKS)
├── gitops-repo-example/  What a *separate* Argo-CD-watched repo would contain
├── docker-compose.yml   Local dev only (frontend + backend + local Postgres)
└── Jenkinsfile
```

---

## 1. Project overview

- **Login / Register** — JWT-based auth, bcrypt password hashing, protected chat route.
- **Chat** — a list of other users, a 1:1 conversation window, message persistence,
  history reload on login, lightweight 3-second polling for new messages (no WebSockets —
  kept simple on purpose).
- **Health** — `/health` (liveness) and `/ready` (readiness, checks the DB connection),
  wired into both the Docker `HEALTHCHECK` and the Kubernetes probes.

---

## 2. Architecture

```
Internet
   │
   ▼
Route 53  (DNS)
   │
   ▼
AWS ALB  (provisioned by the AWS Load Balancer Controller, driven by k8s/ingress.yaml)
   │
   ▼
Kubernetes Ingress
   │
   ▼
frontend-service (ClusterIP)
   │
   ▼
Frontend Pods (Nginx serving the React build)
   │  nginx proxies /api/* internally
   ▼
backend-service (ClusterIP, never exposed via Ingress)
   │
   ▼
Backend Pods (FastAPI/Uvicorn)
   │
   ▼
AWS RDS PostgreSQL   (private subnet, NOT a Kubernetes StatefulSet)
```

**Why RDS instead of a Kubernetes StatefulSet:** running Postgres yourself in Kubernetes
means you own replication, backups, patching, storage failover, and PITR recovery — all
solved problems for RDS. RDS gives automated backups, Multi-AZ failover, point-in-time
restore, and OS/engine patching without any of that operational burden, and it decouples
the database's lifecycle from the cluster's (you can tear down/rebuild EKS without
touching the data). The tradeoff — less control, an AWS bill, cross-service network setup —
is worth it for anything beyond a toy. This project treats Kubernetes as the place
*stateless application workloads* run, and RDS as the place *state* lives, which is the
standard split in real deployments.

---

## 3. Technology stack

**Backend:** Python, FastAPI, SQLAlchemy (Core+ORM), PostgreSQL, `python-jose` (JWT),
`passlib[bcrypt]`, Uvicorn.

**Frontend — React + Vite, not plain HTML/CSS/JS.** The brief allows either; React+Vite
was chosen because (a) it demonstrates a genuine **multi-stage Docker build** (Vite build
stage → static Nginx serve stage), which is one of the DevOps skills this project exists
to practice, and (b) component-based routing (login/register/chat as real routes, an auth
guard) is a closer match to what you'd actually maintain at a job than a hand-rolled
vanilla-JS SPA. The frontend stays intentionally small — three pages, two components, no
state-management library, no UI kit — so the *application* complexity doesn't compete with
the *infrastructure* complexity that's the actual point of the exercise.

**Database:** PostgreSQL — locally via Docker Compose, in the cluster via AWS RDS.

**Infra:** Docker, Kubernetes (EKS), Jenkins, Amazon ECR, Argo CD, AWS ALB via the AWS
Load Balancer Controller, Route 53, CloudWatch.

---

## 4. Database schema

```sql
users
  id             SERIAL PRIMARY KEY
  username       VARCHAR(50)  UNIQUE NOT NULL
  email          VARCHAR(255) UNIQUE NOT NULL
  password_hash  VARCHAR(255) NOT NULL
  created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()

messages
  id             SERIAL PRIMARY KEY
  sender_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
  receiver_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
  message        TEXT NOT NULL
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()

  INDEX ix_messages_conversation (sender_id, receiver_id, created_at)
```

Tables are created automatically on backend startup via
`Base.metadata.create_all()` (see `backend/app/main.py`). That's fine for a demo project;
for anything real, swap this for **Alembic** migrations run as an explicit step (a
Kubernetes `Job`, or a Jenkins pipeline stage) so schema changes are versioned and
reviewable instead of implicit.

---

## 5. API endpoints

All routes except `/register`, `/login`, `/health`, `/ready` require
`Authorization: Bearer <token>`.

| Method | Path              | Description                                  |
|--------|-------------------|-----------------------------------------------|
| POST   | `/register`       | Create a user                                  |
| POST   | `/login`          | Exchange username/password for a JWT           |
| GET    | `/me`             | Current authenticated user                     |
| GET    | `/users`          | All users except the caller                    |
| GET    | `/messages/{id}`  | Full conversation with user `{id}`             |
| POST   | `/messages`       | Send a message                                 |
| GET    | `/health`         | Liveness — process is up                       |
| GET    | `/ready`          | Readiness — process is up **and DB is reachable** |

Interactive docs are auto-generated by FastAPI at `/docs` (Swagger UI) and `/redoc`.

**POST /register**
```json
// request
{ "username": "alice", "email": "alice@example.com", "password": "password123" }
// response  201
{ "id": 1, "username": "alice", "email": "alice@example.com", "created_at": "2026-08-30T07:00:00Z" }
```

**POST /login**
```json
// request
{ "username": "alice", "password": "password123" }
// response  200
{ "access_token": "eyJhbGciOi...", "token_type": "bearer" }
```

**POST /messages**
```json
// request  (Authorization: Bearer <token>)
{ "receiver_id": 2, "message": "hey bob" }
// response  201
{ "id": 10, "sender_id": 1, "receiver_id": 2, "message": "hey bob", "created_at": "2026-08-30T07:01:00Z" }
```

---

## 6. Local setup (no Docker)

```bash
# --- backend ---
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edit DB_* if your local Postgres differs
uvicorn app.main:app --reload --port 8000

# --- frontend, in a second terminal ---
cd frontend
npm install
npm run dev                    # http://localhost:5173, proxies /api -> :8000
```

You'll need a local Postgres running with credentials matching `.env` (or just use
Docker Compose below, which handles that for you).

---

## 7. Docker / Docker Compose setup (recommended for local dev)

```bash
docker compose up --build          # frontend :3000, backend :8000, postgres :5432
docker compose up -d --build       # same, detached
docker compose logs -f backend     # tail one service's logs
docker compose down                # stop
docker compose down -v             # stop and wipe the local Postgres volume
```

Open **http://localhost:3000**, register two users (two browser tabs / one incognito),
and message between them.

Build and run a single image manually, if you need to:
```bash
docker build -t chat-backend:local ./backend
docker run -p 8000:8000 --env-file backend/.env chat-backend:local

docker build -t chat-frontend:local ./frontend
docker run -p 3000:8080 -e BACKEND_URL=http://host.docker.internal:8000 chat-frontend:local
```

---

## 8. AWS RDS setup

1. **Create the instance** (console or CLI):
   ```bash
   aws rds create-db-instance \
     --db-instance-identifier chatapp-db \
     --db-instance-class db.t4g.micro \
     --engine postgres \
     --engine-version 16 \
     --master-username chatapp \
     --master-user-password '<choose-a-strong-password>' \
     --allocated-storage 20 \
     --db-name chatapp \
     --vpc-security-group-ids <sg-id-allowing-5432-from-eks-nodes> \
     --db-subnet-group-name <your-private-subnet-group> \
     --no-publicly-accessible \
     --backup-retention-period 7
   ```
2. **Port:** 5432 (default, matches `DB_PORT`).
3. **Security group:** create/attach a security group whose **only** inbound rule is
   TCP 5432 from the EKS node/pod security group (or the VPC CIDR the cluster's pods use).
   Do not open 5432 to `0.0.0.0/0`.
4. **Network placement:** put the RDS instance in **private subnets** with
   `--no-publicly-accessible`. Nothing outside the VPC should be able to reach it directly.
5. **How EKS connects:** pods read `DB_HOST`/`DB_PORT`/`DB_NAME` from the `database-config`
   ConfigMap and `DB_USERNAME`/`DB_PASSWORD` from the `database-secret` Secret
   (`k8s/configmap.yaml` / `k8s/secret.yaml`), then SQLAlchemy connects over the VPC. As
   long as EKS worker nodes/pods sit in subnets that route to RDS's subnet and the security
   group allows it, no public exposure is needed anywhere in the path.
6. Once created, copy the RDS **endpoint** into `k8s/configmap.yaml`'s `DB_HOST`, and put
   the real username/password into a Secret (see §10 below — not the placeholder file).

---

## 9. Kubernetes deployment (manifests in `k8s/`)

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml          # replace placeholders first! see §10
kubectl apply -f k8s/backend-deployment.yaml
kubectl apply -f k8s/backend-service.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml

# or, all at once:
kubectl apply -f k8s/
```

Before applying, replace the two placeholders in `k8s/backend-deployment.yaml` and
`k8s/frontend-deployment.yaml`: `<ECR_REPOSITORY>` and `<IMAGE_TAG>` (see §11–12).

**Service types, explained:** both `backend-service` and `frontend-service` are
`ClusterIP`. The backend is *only* ever called by the frontend's Nginx proxy from inside
the cluster, so it has no business being reachable externally — keeping it off the
Ingress keeps the attack surface to one entry point. The frontend is reached via the
Ingress → AWS ALB, and with the ALB controller's `target-type: ip`, the ALB routes
straight to pod IPs, so `ClusterIP` is sufficient there too — no `NodePort` needed.

---

## 10. Kubernetes Secrets — and the better production approach

`k8s/secret.yaml` as committed contains **placeholder** base64 values, not real
credentials. Kubernetes Secrets are base64-**encoded**, not encrypted — anyone who can run
`kubectl get secret database-secret -o yaml` can trivially decode them, so treat a Secret
object as "obfuscated," not "protected."

For local/demo use, replace the placeholders with real values applied out-of-band (never
commit the result):
```bash
kubectl create secret generic database-secret \
  --namespace chat-app \
  --from-literal=DB_USERNAME='<real-username>' \
  --from-literal=DB_PASSWORD='<real-password>' \
  --dry-run=client -o yaml | kubectl apply -f -
```

For production, use **AWS Secrets Manager** + the **External Secrets Operator**: store the
RDS credentials in Secrets Manager (which supports encryption at rest, automatic
rotation, and IAM-scoped access), and let the External Secrets Operator sync them into a
Kubernetes Secret automatically. The credential value then never has to be typed into a
YAML file, a `kubectl` command, or Git history at all.

---

## 11. Building and pushing images to ECR

```bash
aws ecr create-repository --repository-name chat-backend
aws ecr create-repository --repository-name chat-frontend

aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

IMAGE_TAG=$(git rev-parse --short HEAD)

docker build -t <account-id>.dkr.ecr.us-east-1.amazonaws.com/chat-backend:$IMAGE_TAG ./backend
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/chat-backend:$IMAGE_TAG

docker build -t <account-id>.dkr.ecr.us-east-1.amazonaws.com/chat-frontend:$IMAGE_TAG ./frontend
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/chat-frontend:$IMAGE_TAG
```

**Tagging strategy:** tag images with the **git commit SHA** (`chat-backend:a1b2c3d`)
rather than `${BUILD_NUMBER}`. The commit SHA is traceable straight back to the exact
source that produced the image, is immutable, and survives Jenkins build-history resets —
`BUILD_NUMBER` is just a counter with none of those guarantees. The `Jenkinsfile` in this
repo uses `GIT_COMMIT.take(7)` for exactly this reason.

---

## 12. EKS deployment

```bash
eksctl create cluster --name chat-app-cluster --region us-east-1 \
  --nodegroup-name workers --nodes 2 --node-type t3.medium --managed

aws eks update-kubeconfig --name chat-app-cluster --region us-east-1

# Install the AWS Load Balancer Controller (required for k8s/ingress.yaml)
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=chat-app-cluster \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller

# Install metrics-server (required for k8s/hpa.yaml)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

kubectl apply -f k8s/
kubectl get ingress -n chat-app     # note the ALB hostname, point Route 53 at it
```

---

## 13. Jenkins CI

The `Jenkinsfile` at the repo root implements:

```
Git checkout → Unit tests → Docker build (backend+frontend, parallel)
  → Security scan (Trivy) → Push to ECR → Update GitOps repo
```

Configure two credentials in Jenkins before running it: `aws-credentials` (ECR push
access) and `gitops-repo-creds` (push access to the GitOps repo). Point a Jenkins
multibranch/pipeline job at this repository and it picks up the `Jenkinsfile`
automatically.

---

## 14. GitOps with Argo CD

**Why Jenkins doesn't run `kubectl apply` directly:** if Jenkins applies manifests
straight to the cluster, the cluster's actual state can drift from what's in Git (a
manual `kubectl edit`, a failed apply, a rollback someone did by hand) with nothing
tracking or correcting that drift. In the GitOps model, Jenkins' job ends at "image is
built and the desired-state repo is updated" — Argo CD is the only thing that ever talks
to the cluster, continuously reconciling live state to match Git, and self-healing any
manual changes back to what Git says. This also means the cluster's entire desired state
is auditable through `git log` on one repo.

```
Application repo (this one)
        │  Jenkins: build, test, scan, push image
        ▼
   Amazon ECR
        │  Jenkins: git-clone the GitOps repo, sed the image tag, commit, push
        ▼
GitOps repo (chat-app-gitops)  ◄── Argo CD watches this continuously
        │
        ▼
       EKS
```

`gitops-repo-example/` in this repo shows what that second repository holds: the same
kind of manifests as `k8s/`, but with the `image:` line pinned to a real tag instead of a
placeholder (see `gitops-repo-example/backend-deployment.yaml`), plus the Argo CD
`Application` object (`gitops-repo-example/argocd-application.yaml`) that tells Argo CD to
watch it.

```bash
# Install Argo CD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Point the CLI at it (after port-forwarding or exposing the argocd-server Service)
argocd login <argocd-server-address>
argocd app create -f gitops-repo-example/argocd-application.yaml
argocd app sync chat-app
argocd app get chat-app
```

---

## 15. AWS architecture

```
Route 53 (chat.example.com)
        │
        ▼
AWS ALB — public subnets
        │
        ▼
EKS worker nodes — private subnets
   ├── Frontend Pods
   └── Backend Pods
        │
        ▼
AWS RDS PostgreSQL — private subnets, no public access
```

- **VPC / subnets:** a VPC with public subnets (ALB, NAT gateways) and private subnets
  (EKS worker nodes, RDS). Nothing that touches the database sits in a public subnet.
- **EKS worker nodes:** run in private subnets, reach the internet (for pulling images,
  etc.) via a NAT gateway, not a public IP of their own.
- **RDS:** private subnet, `--no-publicly-accessible`, reachable only from the EKS
  node/pod security group on 5432.
- **Security Groups:** one for the ALB (80/443 from the internet), one for EKS nodes
  (traffic from the ALB SG), one for RDS (5432 from the EKS node SG only).
- **IAM:** the AWS Load Balancer Controller and any pod that calls AWS APIs (e.g. via
  External Secrets Operator) use **IRSA** (IAM Roles for Service Accounts) — scoped,
  short-lived credentials per service account rather than long-lived keys baked into
  images.
- **ECR:** private image registry for `chat-backend` / `chat-frontend`.
- **ALB:** provisioned by the AWS Load Balancer Controller from `k8s/ingress.yaml`;
  terminates TLS (ACM certificate) and forwards to pod IPs.
- **CloudWatch:** container logs and metrics via the CloudWatch Container Insights
  add-on; RDS metrics (CPU, connections, storage) are already collected by default per
  RDS instance.

---

## 16. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `CrashLoopBackOff` | `kubectl logs <pod> -n chat-app --previous` to see why it died on the last attempt — usually a config/env error or an unhandled startup exception. |
| `ImagePullBackOff` | Wrong image tag/repo, or the node's IAM role can't pull from ECR. Check `kubectl describe pod` for the exact error; confirm `aws ecr get-login-password` was used to auth, or that the node role has `AmazonEC2ContainerRegistryReadOnly`. |
| Database connection failure | Check `/ready` (`kubectl exec` into a pod, `curl localhost:8000/ready`); verify `DB_HOST` in the ConfigMap matches the real RDS endpoint. |
| RDS security group blocking traffic | Confirm the RDS SG allows inbound 5432 from the EKS node/pod SG specifically, not just "looks right" — a common miss is allowing the wrong SG or CIDR. |
| Wrong DB credentials | `kubectl get secret database-secret -n chat-app -o jsonpath='{.data.DB_USERNAME}' \| base64 -d` to confirm what's actually deployed, vs. what RDS was created with. |
| Kubernetes Secret problems | `kubectl describe secret database-secret -n chat-app` (Kubernetes won't show values, but confirms the keys exist); re-apply with `--dry-run=client -o yaml \| kubectl apply -f -` if a key is missing. |
| Readiness probe failure | Pod is up but `/ready` is failing — almost always a DB reachability issue; check security groups and credentials first. |
| Liveness probe failure | `/health` itself is failing or timing out — check pod resource limits (is it CPU-throttled?) and `kubectl logs` for a crash. |
| 502 Bad Gateway | The Ingress/ALB reached a backend that isn't responding correctly - check target group health in the AWS console and pod readiness. |
| 503 Service Unavailable | No healthy pods behind the Service - check `kubectl get endpoints -n chat-app`. |
| 504 Gateway Timeout | Backend is up but too slow to respond in time - check backend CPU/memory usage and RDS latency/CPU. |
| ECR authentication failure | Docker login token expired (they last 12h) - rerun `aws ecr get-login-password \| docker login ...`. |
| Argo CD `OutOfSync` | Live cluster state differs from the GitOps repo - `argocd app diff chat-app` to see exactly what, then `argocd app sync chat-app` (or let `selfHeal` handle it automatically). |
| Jenkins pipeline failure | Check the specific failed stage's console log first; most commonly credentials (`aws-credentials`/`gitops-repo-creds`) expired or aren't scoped to the right job. |

---

## 17. Request flow, end to end

```
User's browser
   │  HTTPS request to chat.example.com
   ▼
Route 53           → resolves the domain to the ALB
   ▼
AWS ALB             → TLS termination, forwards per Ingress rules
   ▼
Kubernetes Ingress   → routes all paths to frontend-service
   ▼
frontend-service     → load-balances across Frontend Pods
   ▼
Frontend Pod (Nginx)  → serves the React app; for /api/* calls, proxies internally to:
   ▼
backend-service       → load-balances across Backend Pods
   ▼
Backend Pod (FastAPI)  → validates the JWT, runs the query
   ▼
AWS RDS PostgreSQL     → the only place data is persisted
```

**Where each piece of the pipeline shows up:**
- **Docker** — packages the backend (Python/Uvicorn) and frontend (Nginx serving a Vite
  build) into images; used for both local dev (`docker-compose.yml`) and what actually
  runs in the cluster.
- **Kubernetes** — runs and self-heals the application pods (`k8s/*-deployment.yaml`),
  load-balances internally (`k8s/*-service.yaml`), exposes the app externally
  (`k8s/ingress.yaml`), and scales the backend under load (`k8s/hpa.yaml`).
- **Jenkins** — the CI half: tests, builds, scans, and pushes images; then updates the
  GitOps repo. Never touches the live cluster directly.
- **ECR** — stores the built images that both Jenkins pushes to and the cluster pulls
  from.
- **Argo CD** — the CD half: the only thing that actually applies changes to the
  cluster, driven entirely by the GitOps repo's contents.
- **RDS** — the single source of truth for all persisted data (`users`, `messages`);
  outside Kubernetes entirely, in private subnets.
- **Secrets** — DB credentials and the JWT signing key never appear in code or images;
  they're injected at pod-start from a Kubernetes Secret (ideally backed by AWS Secrets
  Manager via the External Secrets Operator in production).

---

## 18. Useful commands

```bash
# Docker / Compose
docker build -t chat-backend ./backend
docker run -p 8000:8000 --env-file backend/.env chat-backend
docker compose up --build
docker compose logs -f backend

# Kubernetes
kubectl get pods -n chat-app
kubectl get svc -n chat-app
kubectl get ingress -n chat-app
kubectl logs -f deployment/backend -n chat-app
kubectl describe pod <pod-name> -n chat-app
kubectl apply -f k8s/
kubectl rollout status deployment/backend -n chat-app
kubectl rollout undo deployment/backend -n chat-app

# AWS
aws ecr describe-repositories
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
aws eks update-kubeconfig --name chat-app-cluster --region us-east-1
aws rds describe-db-instances --db-instance-identifier chatapp-db

# Helm
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system

# Argo CD
argocd app create -f gitops-repo-example/argocd-application.yaml
argocd app sync chat-app
argocd app get chat-app
argocd app diff chat-app
```

---

## 19. Testing the application

```bash
# Health/readiness
curl http://localhost:8000/health
curl http://localhost:8000/ready

# Register + login + send a message, end to end
curl -X POST localhost:8000/register -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"password123"}'

TOKEN=$(curl -s -X POST localhost:8000/login -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"password123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl localhost:8000/users -H "Authorization: Bearer $TOKEN"
```

Or just open the frontend, register two users in two browser tabs, and chat between them.
