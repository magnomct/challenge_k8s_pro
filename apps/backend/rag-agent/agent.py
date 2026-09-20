"""Monta a chain RAG: busca no índice + prompt + modelo de linguagem (Nemotron).

Inclui uma trava de escopo em duas camadas:
1. Uma checagem de relevância por similaridade ANTES de chamar o LLM — se os
   trechos recuperados estiverem muito distantes da pergunta, recusamos sem
   gastar chamada de API.
2. Um prompt rígido que instrui o modelo a nunca usar conhecimento externo,
   como segunda linha de defesa (caso a pergunta seja parecida o suficiente
   com o domínio do documento, mas peça algo que não está nele).
"""
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

MODELO_PADRAO = "nvidia/nemotron-3-super-120b-a12b"

MENSAGEM_FORA_DE_ESCOPO = (
    "Não tenho essa informação no documento. Minha função é responder apenas "
    "sobre o conteúdo do manual interno carregado."
)

PROMPT_TEMPLATE = """
Você é um assistente que responde EXCLUSIVAMENTE com base no contexto abaixo,
extraído de um documento interno da empresa.

Regras obrigatórias e inegociáveis:
1. Use SOMENTE as informações do contexto abaixo. Nunca utilize conhecimento
   externo, geral ou suposições, mesmo que você "saiba" a resposta.
2. Você PODE (e deve, quando fizer sentido) combinar, resumir e relacionar
   informações presentes em diferentes trechos do contexto para formar uma
   resposta completa — isso não é "extrapolar", é interpretar o que já está
   escrito. Extrapolar seria afirmar algo que o contexto não permite concluir.
3. A frase de recusa abaixo é reservada para quando a pergunta não tem
   NENHUMA relação com o contexto. Se parte da pergunta puder ser respondida
   com o contexto e parte não, responda a parte que puder e diga
   explicitamente, na mesma resposta, que o documento não determina a outra
   parte — NUNCA recuse a pergunta inteira só porque uma parte dela não está
   coberta.
4. Frase de recusa (usar exatamente esta, e só quando a regra 3 mandar):
   "{mensagem_fora_de_escopo}"
5. Não invente fatos, números, nomes ou afirmações que não decorram do que
   está escrito no contexto.

Contexto:
{{context}}

Pergunta: {{question}}
""".format(mensagem_fora_de_escopo=MENSAGEM_FORA_DE_ESCOPO)


def _format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


def montar_agente(vectorstore, modelo: str = MODELO_PADRAO, k: int = 4, temperature: float = 0.2):
    """Monta e retorna (rag_chain, retriever) prontos para uso.

    rag_chain.invoke("pergunta") -> string com a resposta
    retriever.invoke("pergunta") -> lista de Document usados como fonte
    """
    llm = ChatNVIDIA(model=modelo, temperature=temperature)
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)

    rag_chain = (
        {"context": retriever | _format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return rag_chain, retriever


def checar_relevancia(vectorstore, pergunta: str, k: int = 4, limiar_distancia: float = 1.0):
    """Busca os documentos mais próximos e avalia se são relevantes o suficiente.

    FAISS retorna distância L2 (quanto MENOR, mais similar). Se a menor
    distância encontrada for maior que `limiar_distancia`, consideramos que a
    pergunta está fora do escopo do documento e nem chamamos o LLM.

    O valor padrão (1.0) é um ponto de partida — o ideal é calibrar
    empiricamente: rode algumas perguntas dentro e fora do escopo, observe as
    distâncias retornadas (exibidas na interface) e ajuste o limiar.

    Retorna: (relevante: bool, docs_com_score: list[(Document, float)])
    """
    docs_com_score = vectorstore.similarity_search_with_score(pergunta, k=k)
    if not docs_com_score:
        return False, []

    # FAISS retorna numpy.float32 — convertemos para float nativo aqui, na
    # origem, para que nenhum código downstream (MySQL, exibição na UI etc.)
    # precise se preocupar com esse tipo.
    docs_com_score = [(doc, float(score)) for doc, score in docs_com_score]

    melhor_distancia = min(score for _, score in docs_com_score)
    relevante = melhor_distancia <= limiar_distancia
    return relevante, docs_com_score


def responder(pergunta: str, vectorstore, rag_chain, k: int = 4, limiar_distancia: float = 1.0):
    """Fluxo completo: checa relevância e só então chama o LLM se fizer sentido.

    Retorna um dicionário com:
        resposta: str
        docs: list[Document] (fontes usadas, vazio se fora de escopo)
        dentro_do_escopo: bool
        melhor_distancia: float | None
    """
    relevante, docs_com_score = checar_relevancia(
        vectorstore, pergunta, k=k, limiar_distancia=limiar_distancia)
    melhor_distancia = min((s for _, s in docs_com_score), default=None)

    if not relevante:
        return {
            "resposta": MENSAGEM_FORA_DE_ESCOPO,
            "docs": [],
            "dentro_do_escopo": False,
            "melhor_distancia": melhor_distancia,
        }

    resposta = rag_chain.invoke(pergunta)
    docs = [doc for doc, _ in docs_com_score]

    # Segunda camada: mesmo com docs relevantes, o prompt pode ter recusado
    # (ex: pergunta ambígua que parecia relacionada mas não estava no texto).
    dentro_do_escopo = MENSAGEM_FORA_DE_ESCOPO not in resposta

    return {
        "resposta": resposta,
        "docs": docs if dentro_do_escopo else [],
        "dentro_do_escopo": dentro_do_escopo,
        "melhor_distancia": melhor_distancia,
    }
