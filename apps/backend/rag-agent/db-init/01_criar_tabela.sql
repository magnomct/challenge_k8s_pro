-- Executado automaticamente pelo Postgres apenas na PRIMEIRA inicialização
-- do volume (docker-entrypoint-initdb.d). Se o volume já existir, este
-- script é ignorado — não é um mecanismo de migração contínua (para isso,
-- em produção real, usar uma ferramenta como Alembic ou Flyway).

CREATE TABLE IF NOT EXISTS interacoes (
    id                 SERIAL PRIMARY KEY,
    documento          VARCHAR(255),
    pergunta           TEXT NOT NULL,
    resposta           TEXT NOT NULL,
    dentro_do_escopo   BOOLEAN NOT NULL,
    melhor_distancia   REAL,
    fontes             TEXT,
    criado_em          TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_criado_em ON interacoes (criado_em);
CREATE INDEX IF NOT EXISTS idx_escopo ON interacoes (dentro_do_escopo);
