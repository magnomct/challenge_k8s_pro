"""Cria, salva e carrega o índice vetorial (FAISS) a partir dos chunks do documento."""
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

EMBEDDING_MODEL_PADRAO = "all-MiniLM-L6-v2"


def construir_vectorstore(chunks, embedding_model: str = EMBEDDING_MODEL_PADRAO):
    """Gera embeddings para os chunks e retorna um índice FAISS em memória."""
    embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
    return FAISS.from_documents(chunks, embeddings)


def salvar_vectorstore(vectorstore, caminho: str = "indice_faiss"):
    """Persiste o índice em disco para reuso sem reprocessar o PDF."""
    vectorstore.save_local(caminho)


def carregar_vectorstore(caminho: str, embedding_model: str = EMBEDDING_MODEL_PADRAO):
    """Carrega um índice previamente salvo em disco."""
    embeddings = HuggingFaceEmbeddings(model_name=embedding_model)
    return FAISS.load_local(caminho, embeddings, allow_dangerous_deserialization=True)
