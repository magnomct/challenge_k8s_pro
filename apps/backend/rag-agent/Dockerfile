# --- Estágio único: imagem enxuta baseada em slim (não alpine, pois faiss-cpu
#     e outras libs científicas dependem de glibc; musl do alpine causa dor de
#     cabeça e builds mais lentos para esse tipo de dependência) ---
FROM python:3.12-slim

WORKDIR /app

# curl é usado só para o healthcheck do container
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependências ANTES do código: aproveita o cache de
# camadas do Docker — o pip install só roda de novo se requirements.txt mudar.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Agora sim o código da aplicação e arquivos estáticos
COPY loader.py vectorstore.py agent.py db.py api.py ./
COPY static/ static/

# Usuário não-root — boa prática de segurança em contêineres de produção
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

# Diretório temporário para uploads de PDF (readOnlyRootFilesystem no K8s)
RUN mkdir -p /tmp/uploads && chown appuser:appuser /tmp/uploads

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
