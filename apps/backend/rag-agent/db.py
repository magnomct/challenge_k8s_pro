"""Persistência das interações do agente em PostgreSQL.

Cada pergunta/resposta é registrada com um flag indicando se estava dentro do
escopo do documento. Isso permite, no futuro:
- Analisar quais perguntas os usuários mais fazem (para melhorar o documento
  ou o prompt).
- Detectar padrões de perguntas fora de escopo (para eventualmente ampliar a
  base de documentos).
- Servir como dataset real para uma futura etapa de fine-tuning ou ajuste do
  agente.

Todas as funções são "best-effort": se o PostgreSQL não estiver configurado
ou disponível, o restante da aplicação continua funcionando normalmente —
apenas o histórico deixa de ser salvo (ver tratamento de erro em app.py).
"""
import os
from datetime import datetime

import psycopg2


def _conectar():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER"),
        password=os.environ.get("POSTGRES_PASSWORD"),
        dbname=os.environ.get("POSTGRES_DB"),
        connect_timeout=5,
    )


def criar_tabela():
    """Cria a tabela de interações se ainda não existir. Chamar uma vez na inicialização.

    Redundante com o script em DB/init/01_criar_tabela.sql (que roda
    automaticamente na primeira subida do container Postgres) — mantido aqui
    também como segunda camada de segurança, caso a aplicação rode contra um
    Postgres que não passou por aquele script de inicialização.
    """
    conn = _conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS interacoes (
                id                 SERIAL PRIMARY KEY,
                documento          VARCHAR(255),
                pergunta           TEXT NOT NULL,
                resposta           TEXT NOT NULL,
                dentro_do_escopo   BOOLEAN NOT NULL,
                melhor_distancia   REAL,
                fontes             TEXT,
                criado_em          TIMESTAMP NOT NULL DEFAULT now()
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_criado_em ON interacoes (criado_em)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_escopo ON interacoes (dentro_do_escopo)")
        conn.commit()
    finally:
        conn.close()


def registrar_interacao(documento: str, pergunta: str, resposta: str,
                          dentro_do_escopo: bool, melhor_distancia,
                          fontes: str = ""):
    """Insere uma interação (pergunta/resposta) no histórico."""
    # Proteção: garante float nativo do Python mesmo que o chamador passe um
    # tipo numpy (ex: numpy.float32), que o driver não sabe serializar direto.
    if melhor_distancia is not None:
        melhor_distancia = float(melhor_distancia)

    conn = _conectar()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO interacoes
                (documento, pergunta, resposta, dentro_do_escopo, melhor_distancia, fontes, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (documento, pergunta, resposta, dentro_do_escopo, melhor_distancia, fontes, datetime.now()),
        )
        conn.commit()
    finally:
        conn.close()


def listar_interacoes(limit: int = 50, offset: int = 0,
                      dentro_do_escopo=None, documento: str = None):
    """Consulta o histórico de interações com paginação e filtros opcionais.

    Retorna uma lista de dicts (um por linha), ordenada do mais recente para
    o mais antigo. Usada pelo endpoint GET /history da API.
    """
    conn = _conectar()
    try:
        cursor = conn.cursor()

        # Monta query dinâmica com filtros opcionais
        conditions = []
        params = []

        if dentro_do_escopo is not None:
            conditions.append("dentro_do_escopo = %s")
            params.append(dentro_do_escopo)

        if documento is not None:
            conditions.append("documento ILIKE %s")
            params.append(f"%{documento}%")

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        query = f"""
            SELECT id, documento, pergunta, resposta, dentro_do_escopo,
                   melhor_distancia, fontes, criado_em
            FROM interacoes
            {where_clause}
            ORDER BY criado_em DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return rows
    finally:
        conn.close()


def obter_estatisticas():
    """Obtém estatísticas gerais e agrupadas por dia."""
    conn = _conectar()
    try:
        cursor = conn.cursor()

        # Totais globais
        cursor.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN dentro_do_escopo THEN 1 ELSE 0 END) as in_scope,
                SUM(CASE WHEN NOT dentro_do_escopo THEN 1 ELSE 0 END) as out_of_scope
            FROM interacoes
            """
        )
        row = cursor.fetchone()
        total = row[0] or 0
        in_scope = row[1] or 0
        out_of_scope = row[2] or 0
        accuracy = (in_scope / total * 100) if total > 0 else 0

        # Agrupamento por dia (últimos 30 dias)
        cursor.execute(
            """
            SELECT
                TO_CHAR(criado_em, 'YYYY-MM-DD') as date,
                SUM(CASE WHEN dentro_do_escopo THEN 1 ELSE 0 END) as in_scope,
                SUM(CASE WHEN NOT dentro_do_escopo THEN 1 ELSE 0 END) as out_of_scope,
                COUNT(*) as total
            FROM interacoes
            WHERE criado_em >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY TO_CHAR(criado_em, 'YYYY-MM-DD')
            ORDER BY date ASC
            """
        )
        daily_rows = cursor.fetchall()
        daily = []
        for d_row in daily_rows:
            daily.append({
                "date": d_row[0],
                "in_scope": d_row[1] or 0,
                "out_of_scope": d_row[2] or 0,
                "total": d_row[3] or 0
            })

        return {
            "total": total,
            "in_scope": in_scope,
            "out_of_scope": out_of_scope,
            "accuracy_pct": round(accuracy, 1),
            "daily": daily
        }
    finally:
        conn.close()
