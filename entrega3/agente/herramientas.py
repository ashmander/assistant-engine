"""Herramientas (tools) del agente de devoluciones de EcoMarket (Fase 2).

Reutiliza el código de la Entrega 2 (entrega2/rag) sin modificarlo:
- buscar_informacion_ecomarket: el RAG (Qdrant + nomic) como una herramienta más.
- consultar_estado_pedido: búsqueda exacta del pedido, sin datos sensibles.
- verificar_elegibilidad_devolucion: reglas deterministas de la política.
- generar_etiqueta_devolucion: código RMA + guía en PDF; vuelve a verificar la
  elegibilidad antes de emitirla (no confía en lo que diga el LLM).

Cada herramienta devuelve un JSON con "ok": true/false. Los errores se devuelven
como datos ("error" + "detalle") para que el agente los explique al cliente, y
cada llamada queda en logs/acciones.jsonl (auditoría de negocio).
"""

import functools
import hashlib
import json
import sys
import time
import tomllib
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from langchain_core.tools import tool
from reportlab.lib.pagesizes import A6, landscape
from reportlab.pdfgen import canvas

BASE_DIR = Path(__file__).parent
ENTREGA3_DIR = BASE_DIR.parent
sys.path.insert(0, str(ENTREGA3_DIR.parent / "entrega2" / "rag"))

from asistente_rag_langchain import PATRON_PEDIDO, crear_vectorstore, recuperar_contexto  # noqa: E402
from utilidades import DATA_DIR, SETTINGS as SETTINGS_RAG, buscar_pedido  # noqa: E402

with (BASE_DIR / "settings_agente.toml").open("rb") as archivo:
    SETTINGS = tomllib.load(archivo)

DEVOLUCIONES = SETTINGS["devoluciones"]
FECHA_REFERENCIA = date.fromisoformat(SETTINGS["general"]["fecha_referencia"])
ETIQUETAS_DIR = ENTREGA3_DIR / "etiquetas"
LOG_ACCIONES = ENTREGA3_DIR / "logs" / "acciones.jsonl"

PALABRAS_VACIAS = {"de", "del", "la", "el", "los", "las", "para", "con", "en", "mi", "un", "una", "x"}


# --- Utilidades --------------------------------------------------------------

def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar nombres de productos."""
    sin_tildes = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def normalizar_tracking(texto: str) -> str | None:
    """Convierte 'eco 1011', 'ECO1011' o 'ECO-1011' en 'ECO-1011'; None si no tiene el formato."""
    codigo = PATRON_PEDIDO.search(texto or "")
    return f"ECO-{codigo.group(1)}" if codigo else None


def error(codigo: str, detalle: str) -> dict:
    return {"ok": False, "error": codigo, "detalle": detalle}


def registrar_accion(herramienta: str, argumentos: dict, resultado: dict, duracion_ms: float) -> None:
    """Agrega una línea JSON al registro de acciones (auditoría)."""
    LOG_ACCIONES.parent.mkdir(exist_ok=True)
    linea = {"timestamp": datetime.now().isoformat(timespec="seconds"), "herramienta": herramienta,
             "argumentos": argumentos, "ok": resultado.get("ok"), "resultado": resultado,
             "duracion_ms": round(duracion_ms, 1)}
    with LOG_ACCIONES.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linea, ensure_ascii=False, default=str) + "\n")


def auditada(funcion):
    """Envuelve una herramienta: captura excepciones, registra la acción y devuelve JSON."""
    @functools.wraps(funcion)
    def envoltura(**kwargs) -> str:
        inicio = time.perf_counter()
        try:
            resultado = funcion(**kwargs)
        except Exception as e:  # el agente recibe el error como dato, no como excepción
            resultado = error("error_interno", f"{type(e).__name__}: {e}")
        registrar_accion(funcion.__name__, kwargs, resultado, (time.perf_counter() - inicio) * 1000)
        return json.dumps(resultado, ensure_ascii=False, default=str)
    return envoltura


@functools.cache
def obtener_vectorstore():
    """Índice RAG de la Entrega 2; se crea una sola vez (la primera consulta general)."""
    return crear_vectorstore()


def leer_pedido(tracking: str) -> pd.Series | None:
    pedidos = pd.read_excel(DATA_DIR / "pedidos.xlsx")
    fila = pedidos[pedidos["tracking_number"] == tracking]
    return None if fila.empty else fila.iloc[0]


def buscar_producto_en_pedido(pedido: pd.Series, producto: str) -> list[str]:
    """Productos del pedido que contienen todas las palabras significativas de 'producto'."""
    palabras = [p for p in normalizar(producto).split() if p not in PALABRAS_VACIAS] or [normalizar(producto)]
    productos = [p.strip() for p in str(pedido["productos"]).split(";")]
    return [p for p in productos if all(palabra in normalizar(p) for palabra in palabras)]


# --- Lógica de negocio (sin LLM) ----------------------------------------------

def evaluar_elegibilidad(numero_seguimiento: str, producto: str) -> dict:
    """Aplica la política de devoluciones a un producto de un pedido.

    Devuelve ok=False si los datos no permiten evaluar (formato, pedido o
    producto inexistente) y ok=True con elegible=True/False si se pudo evaluar.
    """
    tracking = normalizar_tracking(numero_seguimiento)
    if not tracking:
        return error("formato_invalido", "El número de seguimiento debe tener el formato ECO-1234.")
    if not producto or not producto.strip():
        return error("producto_faltante", "Falta indicar qué producto del pedido se quiere devolver.")

    pedido = leer_pedido(tracking)
    if pedido is None:
        return error("pedido_no_encontrado", f"No existe ningún pedido con el número de seguimiento {tracking}.")

    coincidencias = buscar_producto_en_pedido(pedido, producto)
    if not coincidencias:
        return error("producto_no_en_pedido",
                     f"El producto '{producto}' no forma parte del pedido {tracking}.")
    if len(coincidencias) > 1:
        return error("producto_ambiguo", f"'{producto}' coincide con varios productos del pedido: "
                                         f"{', '.join(coincidencias)}. Indica cuál.")
    nombre = coincidencias[0]

    inventario = pd.read_excel(DATA_DIR / "inventario_productos.xlsx")
    ficha = inventario[inventario["producto"].map(normalizar) == normalizar(nombre)].iloc[0]
    base = {"ok": True, "pedido": tracking, "producto": nombre, "sku": ficha.sku,
            "categoria": ficha.categoria, "estado_pedido": pedido.estado}

    if pedido.estado != DEVOLUCIONES["estado_entregado"]:
        motivos = {
            "Cancelado": "El pedido fue cancelado, por lo que no hay producto para devolver.",
            "Devolucion en proceso": "Este pedido ya tiene una devolución en proceso.",
            "Devuelto al remitente": "El pedido fue devuelto al remitente y nunca se entregó.",
        }
        motivo = motivos.get(pedido.estado, f"El pedido aún no ha sido entregado (estado: {pedido.estado}). "
                                            "El plazo de devolución empieza a contar desde la entrega.")
        return base | {"elegible": False, "codigo_motivo": "pedido_no_entregado", "motivo": motivo}

    if ficha.es_devolvible != "si":
        return base | {"elegible": False, "codigo_motivo": "producto_no_devolvible", "motivo": ficha.motivo_politica}

    fecha_entrega = pd.Timestamp(pedido.fecha_estimada_entrega).date()
    fecha_limite = fecha_entrega + timedelta(days=int(ficha.dias_para_devolucion))
    dias_restantes = (fecha_limite - FECHA_REFERENCIA).days
    base |= {"fecha_entrega": fecha_entrega, "plazo_dias": int(ficha.dias_para_devolucion),
             "fecha_limite_devolucion": fecha_limite}
    if dias_restantes < 0:
        return base | {"elegible": False, "codigo_motivo": "fuera_de_plazo",
                       "motivo": f"El plazo de {ficha.dias_para_devolucion} días para devolver este producto "
                                 f"venció el {fecha_limite}."}

    return base | {"elegible": True, "dias_restantes": dias_restantes,
                   "motivo": f"Cumple la política: producto devolvible, dentro del plazo de "
                             f"{ficha.dias_para_devolucion} días desde la entrega."}


def codigo_rma(tracking: str, sku: str) -> str:
    """RMA + 6 dígitos (política, sección 6). Determinista: el mismo producto del mismo pedido
    siempre recibe el mismo código, así repetir la solicitud no crea etiquetas duplicadas."""
    return f"RMA{int(hashlib.sha256(f'{tracking}|{sku}'.encode()).hexdigest(), 16) % 1_000_000:06d}"


def crear_pdf_etiqueta(etiqueta: dict) -> Path:
    """Dibuja la guía de devolución en un PDF tamaño A6."""
    ETIQUETAS_DIR.mkdir(exist_ok=True)
    ruta = ETIQUETAS_DIR / f"{etiqueta['codigo_rma']}.pdf"
    ancho, alto = landscape(A6)
    pdf = canvas.Canvas(str(ruta), pagesize=(ancho, alto))
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(20, alto - 35, "EcoMarket - Guía de devolución")
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(20, alto - 70, etiqueta["codigo_rma"])
    pdf.setFont("Helvetica", 9)
    lineas = [
        f"Pedido: {etiqueta['pedido']}    Producto: {etiqueta['producto']} ({etiqueta['sku']})",
        f"Transportadora: {etiqueta['transportadora']} (envío prepagado)",
        f"Destino: {etiqueta['destino']}",
        f"Entregar en un punto de la transportadora antes del {etiqueta['fecha_limite_envio']}",
        f"Motivo: {etiqueta['motivo_cliente']}",
        f"Emitida: {etiqueta['fecha_emision']}",
    ]
    for i, linea in enumerate(lineas):
        pdf.drawString(20, alto - 100 - i * 16, linea[:95])
    pdf.save()
    return ruta


def emitir_etiqueta(numero_seguimiento: str, producto: str, motivo_cliente: str) -> dict:
    """Vuelve a verificar la elegibilidad y, si se cumple, emite el RMA y la guía en PDF."""
    verificacion = evaluar_elegibilidad(numero_seguimiento, producto)
    if not verificacion["ok"]:
        return verificacion
    if not verificacion["elegible"]:
        return error("no_elegible", verificacion["motivo"])

    pedido = leer_pedido(verificacion["pedido"])
    etiqueta = {
        "codigo_rma": codigo_rma(verificacion["pedido"], verificacion["sku"]),
        "pedido": verificacion["pedido"], "producto": verificacion["producto"], "sku": verificacion["sku"],
        "transportadora": pedido.transportadora, "destino": DEVOLUCIONES["centro_devoluciones"],
        "fecha_emision": FECHA_REFERENCIA,
        "fecha_limite_envio": FECHA_REFERENCIA + timedelta(days=DEVOLUCIONES["dias_para_entregar_paquete"]),
        "motivo_cliente": motivo_cliente or "No indicado",
    }
    etiqueta["ruta_pdf"] = str(crear_pdf_etiqueta(etiqueta).relative_to(ENTREGA3_DIR))
    return {"ok": True} | etiqueta


# --- Herramientas del agente ------------------------------------------------

@tool
@auditada
def buscar_informacion_ecomarket(pregunta: str) -> dict:
    """Busca en la base de conocimiento de EcoMarket (política de devoluciones, reembolsos, envíos,
    garantías, catálogo, inventario y preguntas frecuentes). Úsala para preguntas generales.

    Args:
        pregunta: la pregunta del cliente, en lenguaje natural.
    """
    contexto = recuperar_contexto(obtener_vectorstore(), pregunta)
    if contexto is None:
        return {"ok": True, "encontrado": False, "mensaje": SETTINGS_RAG["mensajes"]["sin_informacion"].strip()}
    return {"ok": True, "encontrado": True, "contexto": contexto}


@tool
@auditada
def consultar_estado_pedido(numero_seguimiento: str) -> dict:
    """Consulta el estado, la transportadora y la fecha estimada de entrega de un pedido.

    Args:
        numero_seguimiento: número de seguimiento escrito por el cliente, formato ECO-1234.
    """
    tracking = normalizar_tracking(numero_seguimiento)
    if not tracking:
        return error("formato_invalido", "El número de seguimiento debe tener el formato ECO-1234.")
    pedido = buscar_pedido(tracking)
    if pedido is None:
        return error("pedido_no_encontrado", f"No existe ningún pedido con el número de seguimiento {tracking}.")
    return {"ok": True, "pedido": pedido}


@tool
@auditada
def verificar_elegibilidad_devolucion(numero_seguimiento: str, producto: str) -> dict:
    """Verifica si un producto de un pedido se puede devolver: pedido entregado, producto devolvible
    según la política y dentro del plazo. Úsala antes de generar cualquier etiqueta.

    Args:
        numero_seguimiento: número de seguimiento del pedido, formato ECO-1234.
        producto: nombre (o parte del nombre) del producto que se quiere devolver.
    """
    return evaluar_elegibilidad(numero_seguimiento, producto)


@tool
@auditada
def generar_etiqueta_devolucion(numero_seguimiento: str, producto: str, motivo_cliente: str) -> dict:
    """Genera el código de autorización RMA y la guía de envío prepagada de una devolución.
    Solo funciona si el producto es elegible (se vuelve a verificar internamente).

    Args:
        numero_seguimiento: número de seguimiento del pedido, formato ECO-1234.
        producto: nombre del producto a devolver.
        motivo_cliente: motivo de la devolución según el cliente (por ejemplo, "no me gustó").
    """
    return emitir_etiqueta(numero_seguimiento, producto, motivo_cliente)


HERRAMIENTAS = [buscar_informacion_ecomarket, consultar_estado_pedido,
                verificar_elegibilidad_devolucion, generar_etiqueta_devolucion]
