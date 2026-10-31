# Comandos útiles de la Entrega 3 (ejecutar desde la carpeta entrega3)
.PHONY: help install phoenix app cli eval eval-sin logs clean

help:      ## Lista los comandos
	@grep -E "^[a-z-]+:.*##" Makefile | sed "s/:.*## /\t/"

install:   ## Instala dependencias y descarga los modelos de Ollama
	cd .. && uv sync
	ollama pull qwen3.5
	ollama pull nomic-embed-text-v2-moe

phoenix:   ## Trazas en http://localhost:6006 (levantar antes que app)
	uv run phoenix serve

app:       ## Interfaz Streamlit en http://localhost:8501
	uv run streamlit run app.py

cli:       ## Agente en modo interactivo por terminal
	uv run python agente/agente.py --pasos

eval:      ## Evaluación del agente (con razonamiento)
	uv run python evaluacion/evaluar_agente.py --razonamiento si

eval-sin:  ## Evaluación del agente sin razonamiento
	uv run python evaluacion/evaluar_agente.py --razonamiento no

logs:      ## Últimas 10 acciones de auditoría
	@tail -n 10 logs/acciones.jsonl

clean:     ## Borra etiquetas PDF y logs generados
	rm -rf etiquetas logs
