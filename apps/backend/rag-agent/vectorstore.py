"""Cria, salva e carrega o índice vetorial (FAISS) a partir dos chunks do documento."""
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from langchain_community.vectorstores import FAISS

EMBEDDING_MODEL_PADRAO = "nvidia/nv-embedqa-e5-v5"


def construir_vectorstore(chunks, embedding_model: str = EMBEDDING_MODEL_PADRAO):
    """Gera embeddings para os chunks e retorna um índice FAISS em memória."""
    embeddings = NVIDIAEmbeddings(model=embedding_model)
    return FAISS.from_documents(chunks, embeddings)


def salvar_vectorstore(vectorstore, caminho: str = "indice_faiss"):
    """Persiste o índice em disco para reuso sem reprocessar o PDF."""
    vectorstore.save_local(caminho)


def carregar_vectorstore(caminho: str, embedding_model: str = EMBEDDING_MODEL_PADRAO):
    """Carrega um índice previamente salvo em disco."""
    embeddings = NVIDIAEmbeddings(model=embedding_model)
    return FAISS.load_local(caminho, embeddings, allow_dangerous_deserialization=True)
