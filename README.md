# Assistant Engine — EcoMarket

Prototipo de ingeniería de prompts para el asistente de atención al cliente de
EcoMarket (Fase 3), usando **Llama 3 (8B)** de forma local a través de
[Ollama](https://ollama.com), en línea con la arquitectura propuesta en
`Seleccion Modelo.md`.

## Requisitos

1. Tener [Ollama](https://ollama.com/download) instalado y corriendo localmente.
2. Descargar el modelo Llama 3 8B:

```bash
ollama pull llama3:8b
```

3. Instalar las dependencias del proyecto (usa [uv](https://docs.astral.sh/uv/)):

```bash
uv sync
```

## Estructura

- `src/assistant_engine/order_status.py`: script del ejercicio 1 (estado de pedido).
- `src/assistant_engine/settings_order_status.toml`: prompts (role + instruction) y configuración del modelo para el ejercicio 1.
- `src/assistant_engine/data/orders.txt`: base de datos de prueba con 10 pedidos, usada como contexto RAG.
- `src/assistant_engine/product_return.py`: script del ejercicio 2 (devolución de producto).
- `src/assistant_engine/settings_product_return.toml`: prompts (role + instruction) y configuración del modelo para el ejercicio 2.
- `src/assistant_engine/data/products.txt`: catálogo de prueba con la política de devolución por producto, usado como contexto RAG.

## Uso

### Ejercicio 1: Estado de pedido

```bash
uv run python src/assistant_engine/order_status.py ECO-1003
```

### Ejercicio 2: Devolución de producto

```bash
uv run python src/assistant_engine/product_return.py "Cafe organico en grano 500g"
```

Cada script inyecta el archivo de datos completo (`orders.txt` o `products.txt`)
en el prompt como contexto, y el modelo debe responder basándose únicamente en
esa información, evitando alucinaciones.
