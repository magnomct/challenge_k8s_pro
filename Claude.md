# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agente de IA para documentos internos (RAG) com deploy em Kubernetes. O projeto usa uma API REST (FastAPI) com Swagger para testes, PostgreSQL para histórico de interações, e manifests K8s prontos para produção.

### Directory Structure

- `apps/` — Código fonte das aplicações
  - `apps/backend/rag-agent/` — Backend FastAPI (API REST, agente RAG, banco)
- `kubernetes/` — Manifests Kubernetes organizados por componente
- `terraform-iac/` — Terraform stacks para infraestrutura OCI
  - `terraform-iac/ansible/` — Playbooks Ansible para configuração e deploy
- `docs/` — ADRs e documentação

## API (FastAPI + Swagger)

O backend expõe uma API REST com Swagger UI automático em `/docs`:

```bash
# Rodar localmente
cd apps/backend/rag-agent
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Swagger UI: http://localhost:8000/docs
```

### Endpoints

| Método | Rota       | Descrição                                           |
| ------ | ---------- | --------------------------------------------------- |
| GET    | `/health`  | Healthcheck (readinessProbe/livenessProbe do K8s)   |
| POST   | `/upload`  | Upload de PDF, indexação, retorna session_id         |
| POST   | `/ask`     | Pergunta sobre o documento (requer session_id)      |
| GET    | `/history` | Painel de histórico de respostas (paginação/filtros) |

## Deploy Workflow — Docker Compose (Dev Local)

```bash
# Subir stack completa (Postgres + backend FastAPI)
docker compose up -d --build

# Swagger UI: http://localhost:8000/docs
# Health: http://localhost:8000/health
```

## Deploy Workflow — Kubernetes

```bash
# Criar secret com credenciais (uma vez)
kubectl create secret generic rag-agent-secrets \
  --from-literal=nvidia-api-key='nvapi-...' \
  --from-literal=postgres-password='senha-segura'

# Aplicar todos os manifests
kubectl apply -k kubernetes/

# Verificar
kubectl get pods -l app.kubernetes.io/part-of=challenge-k8s-pro
```

## Terraform (OCI)

```bash
cd terraform-iac
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars   # preencher credenciais OCI

terraform init
terraform plan
terraform apply
```

## Observabilidade (Prometheus + Grafana)

A aplicação expõe métricas Prometheus em `/metrics` via `prometheus-fastapi-instrumentator`.

### Dev local (Docker Compose)

```bash
# Subir stack completa incluindo observabilidade
docker compose up -d --build

# Endpoints de monitoramento
# Métricas:   http://localhost:8000/metrics
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000 (admin/admin)
```

### Métricas customizadas de negócio

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `rag_uploads_total` | Counter | PDFs enviados |
| `rag_questions_total{scope}` | Counter | Perguntas (in_scope/out_of_scope) |
| `rag_response_latency_seconds` | Histogram | Latência do agente RAG |
| `rag_faiss_distance` | Histogram | Melhor distância FAISS |

### Kubernetes

Manifests em `kubernetes/monitoring/`. O Prometheus descobre pods automaticamente via annotations:
```yaml
prometheus.io/scrape: "true"
prometheus.io/port: "8000"
prometheus.io/path: "/metrics"
```

## CI/CD (GitHub Actions)

Workflows em `.github/workflows/`:

- **`ci.yml`** — Push na `main`: Lint → Build → Push GHCR → Deploy OCI
- **`pr-checks.yml`** — PRs: Lint → Build dry-run → Validate K8s manifests

Imagem publicada em `ghcr.io/magnomct/rag-agent`.

## Kubernetes Conventions

Full rules in `.claude/rules/kubernetes-manifests.md`. Key points:

**File structure** — one resource per file, organized by application:
```
kubernetes/
├── kustomization.yaml
├── backend/
│   ├── deployment.yaml
│   ├── service.yaml
│   └── pdb.yaml
└── postgres/
    ├── statefulset.yaml
    ├── service.yaml
    └── configmap.yaml
```

**Required for every Deployment:**
- Labels: `app.kubernetes.io/name`, `version`, `component`, `part-of`, `managed-by`, `environment`
- Minimum 2 replicas
- RollingUpdate strategy (maxUnavailable: 0)
- readinessProbe + livenessProbe
- Resources (requests/limits)
- Service NodePort
- PodDisruptionBudget

**Security (non-negotiable):**
- `runAsNonRoot: true`, `runAsUser: 1001`
- `allowPrivilegeEscalation: false`
- `readOnlyRootFilesystem: true`, drop ALL capabilities
- Volumes mounted `readOnly: true` (except emptyDir for tmp/cache)

## Terraform Conventions

Full rules in `.claude/rules/terraform-naming-conventions.md`. Key points:

**File naming** — dot-separated semantic hierarchy:
```
vpc.tf                    # aws_vpc + aws_internet_gateway
vpc.public-subnets.tf
vpc.private-subnets.tf
```

**Variables** — grouped objects, no `default` values:
```hcl
variable "vpc" {
  type = object({
    name                 = string
    cidr                 = string
    public_subnet_cidrs  = list(string)
    private_subnet_cidrs = list(string)
    ...
  })
}
```

**Resource identifiers** — no type repetition, always singular:
```hcl
resource "aws_route_table" "public" {}   # correct
resource "aws_route_table" "public_route_table" {}  # wrong
```

**Block ordering** — `count`/`for_each` first, `tags` last (before `depends_on`/`lifecycle`).

**Providers** — native `hashicorp/aws` resources only. No community modules.