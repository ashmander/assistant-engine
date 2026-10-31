"""Interfaz web del agente de EcoMarket con Streamlit (Fase 4).

Uso (desde la carpeta entrega3):
    uv run streamlit run app.py
"""

import sys
import uuid
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "agente"))

from agente import crear_agente, responder  # noqa: E402
from herramientas import SETTINGS, obtener_vectorstore  # noqa: E402
from observabilidad import activar_trazas  # noqa: E402

NOMBRES = {
    "buscar_informacion_ecomarket": "Búsqueda en la base de conocimiento (RAG)",
    "consultar_estado_pedido": "Consulta de estado del pedido",
    "verificar_elegibilidad_devolucion": "Verificación de elegibilidad",
    "generar_etiqueta_devolucion": "Generación de etiqueta de devolución",
    "agente": "Agente",
}
# Sin números de seguimiento: son la única llave de un pedido y no deben quedar a la vista
EJEMPLOS = [
    "Hola, ¿qué puedes hacer por mí?",
    "¿Cuánto tarda el reembolso con tarjeta de crédito?",
    "¿Qué productos no se pueden devolver?",
    "¿Dónde está mi pedido?",
    "Quiero devolver un producto",
]


@st.cache_resource(show_spinner="Cargando el agente y la base de conocimiento...")
def iniciar() -> tuple:
    """Se ejecuta una sola vez por servidor: trazas, índice RAG y agente."""
    trazas = activar_trazas()
    obtener_vectorstore()
    return crear_agente(), trazas


def icono(resultado: dict) -> str:
    if not resultado.get("ok"):
        return "❌"
    return "⚠️" if resultado.get("elegible") is False or resultado.get("encontrado") is False else "✅"


def mostrar_pasos(pasos: list[dict], indice: int) -> None:
    """Muestra las herramientas usadas y, si se generó una etiqueta, el botón para descargarla."""
    if not pasos:
        st.caption("Respondió directamente, sin usar herramientas.")
        return
    with st.expander(f"Acciones del agente ({len(pasos)})"):
        for paso in pasos:
            st.markdown(f"{icono(paso['resultado'])} **{NOMBRES.get(paso['herramienta'], paso['herramienta'])}**")
            st.json({"argumentos": paso["argumentos"], "resultado": paso["resultado"]}, expanded=False)
    for paso in pasos:
        ruta = paso["resultado"].get("ruta_pdf")
        if paso["herramienta"] == "generar_etiqueta_devolucion" and ruta and (BASE_DIR / ruta).exists():
            st.download_button(f"Descargar guía {paso['resultado']['codigo_rma']} (PDF)",
                               (BASE_DIR / ruta).read_bytes(), file_name=Path(ruta).name,
                               mime="application/pdf", key=f"pdf-{indice}")


def nueva_conversacion() -> None:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.mensajes = []


st.set_page_config(page_title="EcoMarket - Asistente", page_icon="🌱")
agente, trazas = iniciar()
if "thread_id" not in st.session_state:
    nueva_conversacion()

with st.sidebar:
    st.header("🌱 EcoMarket")
    st.write("Asistente de atención al cliente: resuelve dudas, consulta pedidos y "
             "gestiona devoluciones (verifica elegibilidad y genera la guía).")
    st.button("Nueva conversación", on_click=nueva_conversacion, width="stretch")
    st.subheader("Prueba con")
    for ejemplo in EJEMPLOS:
        if st.button(ejemplo, width="stretch"):
            st.session_state.pendiente = ejemplo
    st.divider()
    st.caption(f"Modelo: {SETTINGS['general']['llm']} (Ollama) · Fecha de referencia: "
               f"{SETTINGS['general']['fecha_referencia']}")
    st.caption("Trazas: [Phoenix](http://localhost:6006) activo" if trazas else "Trazas: Phoenix no está corriendo")

st.title("Asistente de devoluciones EcoMarket")

for i, mensaje in enumerate(st.session_state.mensajes):
    with st.chat_message(mensaje["rol"]):
        st.markdown(mensaje["texto"])
        if mensaje["rol"] == "assistant":
            mostrar_pasos(mensaje["pasos"], i)

pregunta = st.chat_input("Escribe tu consulta (por ejemplo: quiero devolver un producto)")
pregunta = pregunta or st.session_state.pop("pendiente", None)
if pregunta:
    st.session_state.mensajes.append({"rol": "user", "texto": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            texto, pasos = responder(agente, pregunta, st.session_state.thread_id)
        st.markdown(texto)
        mostrar_pasos(pasos, len(st.session_state.mensajes))
    st.session_state.mensajes.append({"rol": "assistant", "texto": texto, "pasos": pasos})
