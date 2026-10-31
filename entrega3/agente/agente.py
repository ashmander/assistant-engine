"""Agente de devoluciones de EcoMarket con LangChain (Fase 2).

Extiende el asistente RAG de la Entrega 2 con un agente que decide, en cada
mensaje, si responde directamente o usa alguna de sus herramientas:
- buscar_informacion_ecomarket (el RAG de la Entrega 2 como herramienta).
- consultar_estado_pedido.
- verificar_elegibilidad_devolucion.
- generar_etiqueta_devolucion.

El agente es langchain.agents.create_agent (ciclo ReAct sobre LangGraph) con
qwen3.5 en Ollama y memoria por conversación (InMemorySaver + thread_id).

Uso (desde la carpeta entrega3):
    uv run python agente/agente.py                       # modo interactivo
    uv run python agente/agente.py "Quiero devolver la compostera del pedido ECO-1011"
"""

import argparse
import json
import uuid

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from herramientas import HERRAMIENTAS, SETTINGS
from observabilidad import activar_trazas

GENERAL = SETTINGS["general"]
MENSAJES = SETTINGS["mensajes"]


def crear_agente():
    """Inicializa el LLM, las herramientas y la memoria del agente."""
    llm = ChatOllama(model=GENERAL["llm"], temperature=GENERAL["temperature"], reasoning=GENERAL["razonamiento"])
    system_prompt = SETTINGS["prompts"]["system_prompt"].format(fecha_referencia=GENERAL["fecha_referencia"])
    return create_agent(llm, tools=HERRAMIENTAS, system_prompt=system_prompt, checkpointer=InMemorySaver())


def extraer_pasos(mensajes: list) -> list[dict]:
    """Lista de herramientas usadas en el último turno: nombre, argumentos y resultado."""
    inicio = max(i for i, m in enumerate(mensajes) if isinstance(m, HumanMessage))
    resultados = {m.tool_call_id: m.content for m in mensajes[inicio:] if isinstance(m, ToolMessage)}
    pasos = []
    for m in mensajes[inicio:]:
        for llamada in getattr(m, "tool_calls", None) or []:
            contenido = resultados.get(llamada["id"], "")
            try:
                resultado = json.loads(contenido)
            except json.JSONDecodeError:
                resultado = {"ok": False, "error": "respuesta_no_json", "detalle": contenido}
            pasos.append({"herramienta": llamada["name"], "argumentos": llamada["args"], "resultado": resultado})
    return pasos


def responder(agente, pregunta: str, thread_id: str) -> tuple[str, list[dict]]:
    """Ejecuta un turno de la conversación. Devuelve la respuesta y las herramientas usadas.

    Si el LLM no está disponible o el agente entra en un bucle, responde con un
    mensaje amigable en lugar de fallar.
    """
    config = {"configurable": {"thread_id": thread_id}, "metadata": {"session_id": thread_id},
              "recursion_limit": GENERAL["max_pasos"]}
    try:
        estado = agente.invoke({"messages": [HumanMessage(pregunta)]}, config)
    except GraphRecursionError:
        return MENSAJES["error_llm"].strip(), [{"herramienta": "agente", "argumentos": {},
                                                "resultado": {"ok": False, "error": "limite_de_pasos"}}]
    except Exception as e:  # Ollama caído, modelo no descargado, timeout...
        return MENSAJES["error_llm"].strip(), [{"herramienta": "agente", "argumentos": {},
                                                "resultado": {"ok": False, "error": type(e).__name__,
                                                              "detalle": str(e)}}]
    mensajes = estado["messages"]
    texto = next(m.content for m in reversed(mensajes) if isinstance(m, AIMessage) and m.content)
    return texto, extraer_pasos(mensajes)


def parse_args() -> argparse.Namespace:
    """Lee los argumentos de la línea de comandos."""
    parser = argparse.ArgumentParser(description="Agente de devoluciones de EcoMarket (LangChain)")
    parser.add_argument("pregunta", nargs="?", help="Pregunta única; si se omite, inicia el modo interactivo")
    parser.add_argument("--pasos", action="store_true", help="Muestra las herramientas que usó el agente")
    return parser.parse_args()


def imprimir(texto: str, pasos: list[dict], mostrar_pasos: bool) -> None:
    if mostrar_pasos:
        for paso in pasos:
            print(f"  [{paso['herramienta']}] {paso['argumentos']} -> ok={paso['resultado'].get('ok')}")
    print(texto)


def main(args: argparse.Namespace) -> None:
    if activar_trazas():
        print("Trazas activas en Phoenix: http://localhost:6006")
    agente, thread_id = crear_agente(), str(uuid.uuid4())
    if args.pregunta:
        imprimir(*responder(agente, args.pregunta, thread_id), args.pasos)
        return

    print("Agente de EcoMarket listo. Escribe 'salir' para terminar.")
    while (pregunta := input("\nTú: ").strip()).lower() != "salir":
        if pregunta:
            print()
            imprimir(*responder(agente, pregunta, thread_id), args.pasos)


if __name__ == "__main__":
    main(parse_args())
