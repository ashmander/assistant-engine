"""Asistente de EcoMarket con RAG usando LangChain (Fase 3).

Integra el LLM de la Entrega 1 (Llama 3 8B) con los componentes elegidos en las
Fases 1 y 2, usando LangChain como en rag_ejemplo.py:
- OllamaEmbeddings (nomic-embed-text-v2-moe) como modelo de embeddings.
- QdrantVectorStore (en memoria) como base vectorial.
- ChatPromptTemplate | ChatOllama | StrOutputParser como chain de generación.
- Pedidos: búsqueda exacta por número de seguimiento (no se indexan).
- Fuera de alcance: umbral de similitud.

La carga de las fuentes, el chunking y la búsqueda de pedidos están en
utilidades.py; los prompts y parámetros, en settings_rag.toml.

Uso (desde la carpeta entrega2):
    uv run python rag/asistente_rag_langchain.py                  # modo interactivo
    uv run python rag/asistente_rag_langchain.py "¿Puedo devolver la miel?"
"""

import argparse
import re

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore

from utilidades import SETTINGS, buscar_pedido, chunks_catalogo, chunks_faq, chunks_inventario, chunks_politica

GENERAL = SETTINGS["general"]
PATRON_PEDIDO = re.compile(r"ECO[-\s]?(\d{4})", re.IGNORECASE)


class NomicEmbeddings(OllamaEmbeddings):
    """OllamaEmbeddings con los prefijos que exige nomic.

    Nomic distingue entre documentos ('search_document: ') y preguntas
    ('search_query: '); OllamaEmbeddings no los agrega por sí solo. Como
    OllamaEmbeddings.embed_query llama internamente a embed_documents, ambos
    métodos usan super().embed_documents para no duplicar el prefijo.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return super().embed_documents(["search_document: " + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return super().embed_documents(["search_query: " + text])[0]


def crear_vectorstore() -> QdrantVectorStore:
    """Convierte los chunks en Documents de LangChain y los indexa en Qdrant (en memoria)."""
    chunks = chunks_politica() + chunks_catalogo() + chunks_inventario() + chunks_faq()
    documentos = [Document(page_content=c["texto"], metadata={"fuente": c["fuente"]}) for c in chunks]
    vectorstore = QdrantVectorStore.from_documents(
        documentos,
        embedding=NomicEmbeddings(model=GENERAL["embeddings"]),
        location=":memory:",
        collection_name="ecomarket",
    )
    print(f"Índice creado: {len(documentos)} chunks.")
    return vectorstore


def crear_chain():
    """Arma el chain de generación: prompt (Entrega 1) -> Llama 3 8B -> texto."""
    prompt = ChatPromptTemplate.from_messages([
        ("system", SETTINGS["prompts"]["role_prompt"]),
        ("human", SETTINGS["prompts"]["instruction_prompt"]),
    ])
    llm = ChatOllama(model=GENERAL["llm"], temperature=GENERAL["temperature"])
    return prompt | llm | StrOutputParser()


def recuperar_contexto(vectorstore: QdrantVectorStore, pregunta: str) -> str | None:
    """Devuelve el contexto para la pregunta, o None si está fuera de alcance.

    1. Si la pregunta trae un número de seguimiento, se consulta el pedido.
    2. Si no, se recuperan los k documentos más similares. Si el más similar no
       supera el umbral, la pregunta se considera fuera de alcance.
    """
    codigo = PATRON_PEDIDO.search(pregunta)
    if codigo:
        tracking = f"ECO-{codigo.group(1)}"
        return buscar_pedido(tracking) or f"No existe ningún pedido con el número de seguimiento {tracking}."

    resultados = vectorstore.similarity_search_with_score(pregunta, k=GENERAL["k"])
    if not resultados or resultados[0][1] < GENERAL["umbral_similitud"]:
        return None
    return "\n\n".join(f"[{doc.metadata['fuente']}] {doc.page_content}" for doc, _ in resultados)


def responder(vectorstore: QdrantVectorStore, chain, pregunta: str) -> str:
    """Flujo completo: recuperar contexto y ejecutar el chain."""
    contexto = recuperar_contexto(vectorstore, pregunta)
    if contexto is None:
        return SETTINGS["mensajes"]["sin_informacion"].strip()
    return chain.invoke({"contexto": contexto, "pregunta": pregunta})


def parse_args() -> argparse.Namespace:
    """Lee los argumentos de la línea de comandos."""
    parser = argparse.ArgumentParser(description="Asistente RAG de EcoMarket (LangChain)")
    parser.add_argument("pregunta", nargs="?", help="Pregunta única; si se omite, inicia el modo interactivo")
    return parser.parse_args()


def main(args: argparse.Namespace) -> None:
    vectorstore, chain = crear_vectorstore(), crear_chain()
    if args.pregunta:
        print(responder(vectorstore, chain, args.pregunta))
        return

    print("Asistente de EcoMarket (LangChain) listo. Escribe 'salir' para terminar.")
    while (pregunta := input("\nTu pregunta: ").strip()).lower() != "salir":
        if pregunta:
            print("\n" + responder(vectorstore, chain, pregunta))


if __name__ == "__main__":
    main(parse_args())
