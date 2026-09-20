"""Carrega e divide documentos PDF em chunks prontos para indexação."""
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter


def carregar_e_dividir(caminho_pdf: str, chunk_size: int = 1000, chunk_overlap: int = 150):
    """Lê um PDF e retorna uma lista de chunks (Document) prontos para indexação.

    Args:
        caminho_pdf: caminho local para o arquivo PDF.
        chunk_size: tamanho máximo de cada pedaço de texto.
        chunk_overlap: sobreposição entre pedaços consecutivos.
    """
    loader = PyPDFLoader(caminho_pdf)
    paginas = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_documents(paginas)
