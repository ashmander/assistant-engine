"""Utilidades del asistente RAG de EcoMarket: configuración, carga y chunking de
las fuentes de conocimiento y búsqueda exacta de pedidos.

Chunking elegido en BaseDeConocimiento.md:
- Política (PDF): por párrafos.
- Catálogo (PDF tipo lista): recursivo de 1000 caracteres con 200 de solapamiento.
- Inventario (Excel) y FAQ (JSON): un registro por chunk.
- Pedidos (Excel): no se indexan; se consultan por número de seguimiento.
"""

import json
import re
import tomllib
from pathlib import Path

import pandas as pd
import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR.parent / "data"

with (BASE_DIR / "settings_rag.toml").open("rb") as archivo:
    SETTINGS = tomllib.load(archivo)


def chunks_politica() -> list[dict]:
    """Divide la política PDF en párrafos.

    Cada bloque de texto de pymupdf es un párrafo. El título de una sección se
    une al primer párrafo que le sigue para no perder el tema.
    """
    chunks, titulo = [], ""
    with pymupdf.open(DATA_DIR / "politica_devoluciones.pdf") as doc:
        for pagina in doc:
            for bloque in pagina.get_text("blocks"):
                texto = " ".join(bloque[4].split())
                if re.match(r"^\d+\.\s", texto) and len(texto) < 80:
                    titulo = texto + "\n"
                elif texto:
                    chunks.append({"texto": titulo + texto, "fuente": "politica"})
                    titulo = ""
    return chunks


def chunks_catalogo() -> list[dict]:
    """Divide el catálogo PDF (lista de productos por categoría) en chunks de 1000 con solapamiento de 200."""
    with pymupdf.open(DATA_DIR / "catalogo_productos.pdf") as doc:
        texto = "\n".join(" ".join(b[4].split()) for pagina in doc for b in pagina.get_text("blocks"))
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    return [{"texto": t, "fuente": "catalogo"} for t in splitter.split_text(texto)]


def chunks_inventario() -> list[dict]:
    """Convierte cada producto del inventario en un chunk de texto."""
    chunks = []
    for p in pd.read_excel(DATA_DIR / "inventario_productos.xlsx").itertuples():
        stock = f"{p.stock_disponible} unidades disponibles" if p.stock_disponible > 0 else "AGOTADO"
        devolucion = f"sí, plazo de {p.dias_para_devolucion} días" if p.es_devolvible == "si" else "no"
        precio = f"{p.precio_cop:,}".replace(",", ".")
        texto = (f"Producto: {p.producto} (SKU {p.sku}). Categoría: {p.categoria}. {p.descripcion} "
                 f"Precio: {precio} pesos. Stock: {stock}. "
                 f"Admite devolución: {devolucion}. Motivo: {p.motivo_politica}.")
        chunks.append({"texto": texto, "fuente": "inventario"})
    return chunks


def chunks_faq() -> list[dict]:
    """Convierte cada pregunta frecuente (pregunta + respuesta) en un chunk."""
    faq = json.loads((DATA_DIR / "preguntas_frecuentes.json").read_text("utf-8"))
    return [{"texto": f"Pregunta: {f['pregunta']} Respuesta: {f['respuesta']}", "fuente": "faq"} for f in faq]


def buscar_pedido(tracking_number: str) -> str | None:
    """Busca un pedido por coincidencia exacta y lo devuelve como texto.

    No se incluyen el nombre del cliente ni los productos (privacidad, Entrega 1).
    """
    pedidos = pd.read_excel(DATA_DIR / "pedidos.xlsx").fillna("")
    fila = pedidos[pedidos["tracking_number"] == tracking_number]
    if fila.empty:
        return None
    p = fila.iloc[0]
    return (f"Pedido {p.tracking_number}. Estado: {p.estado}. Ciudad: {p.ciudad}. "
            f"Fecha estimada de entrega: {p.fecha_estimada_entrega}. Transportadora: {p.transportadora}. "
            f"Enlace de rastreo: {p.enlace_rastreo}. Observaciones: {p.observaciones or 'ninguna'}.")
