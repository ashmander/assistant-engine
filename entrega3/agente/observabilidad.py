"""Observabilidad del agente con Arize Phoenix (local, OpenTelemetry).

Si Phoenix está corriendo (uv run phoenix serve), cada conversación queda como
una traza en http://localhost:6006: llamadas al LLM, prompts, herramientas
usadas, argumentos, resultados, latencias y errores. Si no está corriendo, el
agente funciona igual, sin trazas.
"""

import socket
from urllib.parse import urlparse

from herramientas import SETTINGS

CONFIG = SETTINGS["observabilidad"]


def phoenix_disponible(endpoint: str) -> bool:
    """Revisa si hay un servidor escuchando en el endpoint de Phoenix."""
    url = urlparse(endpoint)
    try:
        with socket.create_connection((url.hostname, url.port), timeout=0.5):
            return True
    except OSError:
        return False


def activar_trazas() -> bool:
    """Registra Phoenix como destino de las trazas e instrumenta LangChain. Devuelve si quedó activo."""
    if not CONFIG["habilitada"] or not phoenix_disponible(CONFIG["endpoint"]):
        return False

    from openinference.instrumentation.langchain import LangChainInstrumentor
    from phoenix.otel import register

    proveedor = register(project_name=CONFIG["proyecto"], endpoint=CONFIG["endpoint"], verbose=False)
    LangChainInstrumentor().instrument(tracer_provider=proveedor)
    return True
