"""API REST (FastAPI) para o agente de perguntas e respostas sobre documentos.

Swagger UI disponível em /docs — use para testar todos os endpoints
interativamente, sem precisar de frontend.

Rodar localmente:
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""
import os
import tempfile
import uuid
from datetime import datetime
from typing import Optional

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db
from agent import montar_agente, responder
from loader import carregar_e_dividir
from vectorstore import construir_vectorstore

# Carrega variáveis de um arquivo .env local (não tem efeito se o arquivo não existir;
# em produção/K8s, as variáveis de ambiente vêm de ConfigMap/Secret).
load_dotenv()

# ---------------------------------------------------------------------------
# Modelos Pydantic (request/response) — geram o schema automático no Swagger
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    """Resposta do upload de PDF."""
    session_id: str = Field(..., description="ID da sessão para usar nas perguntas")
    filename: str = Field(..., description="Nome do arquivo processado")
    chunks: int = Field(..., description="Quantidade de trechos indexados")


class AskRequest(BaseModel):
    """Corpo da requisição de pergunta."""
    session_id: str = Field(..., description="ID da sessão (retornado pelo upload)")
    question: str = Field(..., description="Pergunta em linguagem natural sobre o documento")
    model: str = Field(
        "meta/llama3-8b-instruct",
        description="Modelo de linguagem a usar",
    )
    k: int = Field(4, ge=2, le=8, description="Nº de trechos buscados")
    relevance_threshold: float = Field(
        1.8, ge=0.1, le=2.0, description="Limiar de relevância (menor = mais rígido)"
    )


class SourceInfo(BaseModel):
    """Informação de uma fonte usada na resposta."""
    page: str = Field(..., description="Número da página")
    excerpt: str = Field(..., description="Trecho do conteúdo (primeiros 200 chars)")


class AskResponse(BaseModel):
    """Resposta do agente a uma pergunta."""
    answer: str = Field(..., description="Resposta do agente")
    in_scope: bool = Field(..., description="Se a pergunta estava dentro do escopo do documento")
    best_distance: Optional[float] = Field(None, description="Distância do trecho mais próximo")
    sources: list[SourceInfo] = Field(default_factory=list, description="Fontes usadas")


class HistoryItem(BaseModel):
    """Item do histórico de interações."""
    id: int
    document: Optional[str] = None
    question: str
    answer: str
    in_scope: bool
    best_distance: Optional[float] = None
    sources: Optional[str] = None
    created_at: datetime


class HealthResponse(BaseModel):
    """Resposta do healthcheck."""
    status: str = Field(..., description="Status da aplicação")
    database: str = Field(..., description="Status da conexão com o banco")


class StatsItem(BaseModel):
    """Estatísticas de acertos/erros por data."""
    date: str = Field(..., description="Data (YYYY-MM-DD)")
    in_scope: int = Field(..., description="Perguntas dentro do escopo")
    out_of_scope: int = Field(..., description="Perguntas fora do escopo")
    total: int = Field(..., description="Total de interações")


class StatsSummary(BaseModel):
    """Resumo geral + série temporal."""
    total: int
    in_scope: int
    out_of_scope: int
    accuracy_pct: float = Field(..., description="Percentual de acertos")
    daily: list[StatsItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Aplicação FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RAG Agent API — Agente de IA para Documentos Internos",
    description=(
        "API REST para o agente de perguntas e respostas sobre documentos "
        "internos usando RAG (Retrieval-Augmented Generation). "
        "Faça upload de um PDF, envie perguntas e consulte o histórico."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sessões ativas: session_id -> {vectorstore, rag_chain, filename}
_sessions: dict[str, dict] = {}

# Servir o frontend estático
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    """Tenta criar a tabela no PostgreSQL na inicialização."""
    try:
        db.criar_tabela()
        app.state.db_available = True
    except Exception:
        app.state.db_available = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root():
    """Serve o frontend HTML."""
    index = Path(__file__).parent / "static" / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "RAG Agent API v2.0 — acesse /docs para Swagger UI"}


@app.get("/health", response_model=HealthResponse, tags=["Infraestrutura"])
async def health():
    """Healthcheck — usado por readinessProbe/livenessProbe do Kubernetes."""
    db_status = "connected" if getattr(app.state, "db_available", False) else "unavailable"
    return HealthResponse(status="ok", database=db_status)


@app.post("/upload", response_model=UploadResponse, tags=["Documentos"])
async def upload_pdf(
    file: UploadFile = File(..., description="Arquivo PDF para processar"),
    model: str = Query(
        "meta/llama3-8b-instruct",
        description="Modelo de linguagem a usar",
    ),
    k: int = Query(4, ge=2, le=8, description="Nº de trechos buscados"),
):
    """Faz upload de um PDF, indexa e cria uma sessão de chat.

    Retorna um `session_id` que deve ser usado nas perguntas subsequentes.
    """
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="Variável de ambiente NVIDIA_API_KEY não configurada.",
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Envie um arquivo PDF válido.")

    # Salva temporariamente o PDF recebido
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        chunks = carregar_e_dividir(tmp_path)
        vectorstore = construir_vectorstore(chunks)
        rag_chain, _ = montar_agente(vectorstore, modelo=model, k=k)
    finally:
        os.unlink(tmp_path)

    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "vectorstore": vectorstore,
        "rag_chain": rag_chain,
        "filename": file.filename,
    }

    return UploadResponse(
        session_id=session_id,
        filename=file.filename,
        chunks=len(chunks),
    )


@app.post("/ask", response_model=AskResponse, tags=["Chat"])
async def ask_question(req: AskRequest):
    """Envia uma pergunta sobre o documento carregado.

    O agente verifica a relevância da pergunta antes de chamar o LLM — se os
    trechos recuperados estiverem muito distantes, a pergunta é recusada sem
    gastar chamada de API.
    """
    session = _sessions.get(req.session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Sessão '{req.session_id}' não encontrada. Faça upload de um PDF primeiro.",
        )

    resultado = responder(
        req.question,
        session["vectorstore"],
        session["rag_chain"],
        k=req.k,
        limiar_distancia=req.relevance_threshold,
    )

    # Montar fontes para a resposta
    sources = []
    for doc in resultado["docs"]:
        sources.append(SourceInfo(
            page=str(doc.metadata.get("page", "?")),
            excerpt=doc.page_content[:200],
        ))

    # Registro no PostgreSQL (best-effort)
    if getattr(app.state, "db_available", False):
        try:
            fontes_texto = " | ".join(
                f"pág. {doc.metadata.get('page', '?')}" for doc in resultado["docs"]
            )
            db.registrar_interacao(
                documento=session["filename"],
                pergunta=req.question,
                resposta=resultado["resposta"],
                dentro_do_escopo=resultado["dentro_do_escopo"],
                melhor_distancia=resultado["melhor_distancia"],
                fontes=fontes_texto,
            )
        except Exception:
            app.state.db_available = False

    return AskResponse(
        answer=resultado["resposta"],
        in_scope=resultado["dentro_do_escopo"],
        best_distance=resultado["melhor_distancia"],
        sources=sources,
    )


@app.get("/history", response_model=list[HistoryItem], tags=["Histórico"])
async def get_history(
    limit: int = Query(50, ge=1, le=500, description="Número máximo de registros"),
    offset: int = Query(0, ge=0, description="Offset para paginação"),
    in_scope: Optional[bool] = Query(None, description="Filtrar por escopo (true/false)"),
    document: Optional[str] = Query(None, description="Filtrar por nome do documento"),
):
    """Retorna o histórico de interações salvas no PostgreSQL.

    Use este endpoint como painel de histórico de respostas — suporta
    paginação e filtros por escopo e documento.
    """
    if not getattr(app.state, "db_available", False):
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL indisponível — histórico não está acessível.",
        )

    try:
        rows = db.listar_interacoes(
            limit=limit,
            offset=offset,
            dentro_do_escopo=in_scope,
            documento=document,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar histórico: {e}")

    return [
        HistoryItem(
            id=row["id"],
            document=row["documento"],
            question=row["pergunta"],
            answer=row["resposta"],
            in_scope=row["dentro_do_escopo"],
            best_distance=row["melhor_distancia"],
            sources=row["fontes"],
            created_at=row["criado_em"],
        )
        for row in rows
    ]


@app.get("/stats", response_model=StatsSummary, tags=["Histórico"])
async def get_stats():
    """Retorna estatísticas agregadas de acertos/erros para o gráfico."""
    if not getattr(app.state, "db_available", False):
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL indisponível.",
        )

    try:
        stats = db.obter_estatisticas()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter stats: {e}")

    return stats
