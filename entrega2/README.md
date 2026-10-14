# Entrega 2 - Sistema RAG para EcoMarket

## Estructura

- `ComponentesSistemaRAG.md`: Fase 1, candidatos de modelos de embeddings y bases de datos vectoriales.
- `BaseDeConocimiento.md`: Fase 2, documentos, estrategias de chunking e indexación.
- `data/`: fuentes de conocimiento ficticias de EcoMarket.
  - `politica_devoluciones.pdf`: política de devoluciones, reembolsos, envíos y garantías.
  - `catalogo_productos.pdf`: lista de los 30 productos por categoría (generada desde el inventario).
  - `inventario_productos.xlsx`: ficha de 30 productos (los 10 primeros vienen de la Entrega 1).
  - `preguntas_frecuentes.json`: 30 preguntas frecuentes.
  - `pedidos.xlsx`: 30 pedidos (los 10 primeros vienen de la Entrega 1).
- `notebooks/experimentacion_rag.ipynb`: experimentos para justificar con datos las elecciones de las Fases 1 y 2.
- `notebooks/resultados/`: CSV generados al ejecutar el notebook.
- `rag/`: Fase 3, asistente con RAG (ver sección Fase 3).
  - `asistente_rag_langchain.py`: el asistente (embeddings, Qdrant, recuperación y chain con el LLM).
  - `utilidades.py`: configuración, carga y chunking de las fuentes y búsqueda exacta de pedidos.
  - `settings_rag.toml`: modelos, parámetros y prompts.
- `docker-compose.yml`: servidor local de Weaviate (solo para el notebook).
- `.env.example`: plantilla de API keys (OpenAI, Pinecone).

## Requisitos

1. Python 3.11 y [uv](https://docs.astral.sh/uv/).
2. [Ollama](https://ollama.com) corriendo, con los modelos:

```bash
ollama pull nomic-embed-text-v2-moe   # modelo de embeddings candidato
ollama pull llama3:8b                 # LLM de chat (Entrega 1)
```

3. Instalar dependencias. El repositorio usa **un solo ambiente** para todas
   las entregas, definido en el `pyproject.toml` de la raíz:

```bash
uv sync      # desde la raíz del repositorio; crea .venv
```

   En VS Code, seleccionar el kernel `assistant-engine` (`.venv/bin/python` de la raíz).

4. Levantar Weaviate (Docker, desde esta carpeta):

```bash
docker compose up -d      # detener: docker compose down
```

5. API keys de OpenAI y Pinecone: copiar `.env.example` como `.env` y completar.
   `.env` está en `.gitignore` y nunca se sube al repositorio.

```bash
cp .env.example .env
```

## Ejecución

```bash
uv run jupyter lab notebooks/experimentacion_rag.ipynb
```

La primera ejecución descarga ~5 GB de modelos de Hugging Face. Si Weaviate,
Pinecone, OpenAI u Ollama no están disponibles, el notebook los omite y los
lista como limitaciones en el resumen final.

## Fase 3: Asistente con RAG

`rag/asistente_rag_langchain.py` integra el LLM de la Entrega 1 (Llama 3 8B)
con los componentes elegidos en las Fases 1 y 2, usando **LangChain** como en
`rag_ejemplo.py`:

- **Embeddings:** `nomic-embed-text-v2-moe` vía `OllamaEmbeddings`.
- **Base vectorial:** `QdrantVectorStore` (en memoria) con la política, el
  catálogo, el inventario y las FAQ: tres tipos de archivo (PDF, Excel y JSON).
- **Pedidos:** no se indexan. Se buscan por coincidencia exacta del número de
  seguimiento en `pedidos.xlsx`, sin el nombre del cliente ni los productos.
- **Fuera de alcance:** si la similitud máxima es menor que 0.374, se responde
  un mensaje fijo y se ofrece un agente humano, sin llamar al LLM.
- **Generación:** chain `ChatPromptTemplate | ChatOllama | StrOutputParser` con
  las reglas de la Entrega 1 (`settings_rag.toml`).

### Uso

Requiere Ollama corriendo con `llama3:8b` y `nomic-embed-text-v2-moe`. No necesita Docker ni API keys.
Ejecutar comando estando en la carpeta de entrega2.

```bash
uv run python rag/asistente_rag_langchain.py                                  # modo interactivo
uv run python rag/asistente_rag_langchain.py "¿Puedo devolver la miel orgánica?"
uv run python rag/asistente_rag_langchain.py "mi pedido ECO 1003 no ha llegado"
uv run python rag/asistente_rag_langchain.py "dame la lista de productos que venden"
```

### Cómo se conectan las piezas

```
pregunta
   │
   ├─ ¿trae un código ECO-1234? ──sí──► búsqueda exacta en pedidos.xlsx (sin datos sensibles) ─┐
   │                                                                                          │
   no                                                                                         │
   ▼                                                                                          │
embedding de la pregunta (nomic, "search_query: ")                                            │
   ▼                                                                                          │
Qdrant: top 5 por similitud coseno (política, catálogo, inventario, FAQ)                      │
   ▼                                                                                          │
¿similitud máxima < 0.374? ──sí──► "no tengo información" + agente humano (sin LLM)           │
   │                                                                                          │
   no                                                                                         │
   ▼                                                                                          ▼
contexto ───────────────────────────────────► ChatPromptTemplate | ChatOllama(llama3:8b) | StrOutputParser ──► respuesta
```

| Archivo / función | Qué hace |
|---|---|
| `utilidades.chunks_politica` | Divide la política PDF en párrafos (el título de la sección se une al primer párrafo) |
| `utilidades.chunks_catalogo` | Divide el catálogo PDF con `RecursiveCharacterTextSplitter` (1000/200) |
| `utilidades.chunks_inventario`, `chunks_faq` | Un producto o una pregunta frecuente por chunk |
| `utilidades.buscar_pedido` | Busca el pedido por número de seguimiento y devuelve solo los campos permitidos |
| `NomicEmbeddings` | `OllamaEmbeddings` con los prefijos de nomic (`search_document:` / `search_query:`) |
| `crear_vectorstore` | Convierte los chunks en `Document` y los indexa con `QdrantVectorStore.from_documents` |
| `crear_chain` | Chain LCEL: prompt de la Entrega 1 → Llama 3 8B → texto |
| `recuperar_contexto` | Pedido por código, o top 5 por similitud con umbral de fuera de alcance |
| `responder` | Recupera el contexto y ejecuta el chain (o devuelve el mensaje fijo) |
| `main` | Pregunta única o modo interactivo, como `rag_ejemplo.py` |

**Conclusión:** la privacidad de los pedidos no puede depender solo del prompt.
Se protege en la recuperación: los pedidos no están en el índice vectorial y
solo se consultan con su número de seguimiento.

### Cambios respecto a la Entrega 1

| Entrega 1 | Entrega 2 |
|---|---|
| Un script por tipo de consulta (pedidos, devoluciones) | Un solo asistente para cualquier consulta |
| Se inyectaba **todo** el archivo de datos en el prompt | Se inyectan solo los 5 chunks más relevantes |
| Sin manejo de preguntas fuera del dominio | Umbral de similitud: responde que no tiene información y ofrece un agente humano |
| Prompts en `settings_*.toml` | Se mantiene el patrón: `settings_rag.toml` (role + instruction prompt) |

### Limitaciones y suposiciones

- **Índice en memoria:** se reconstruye en cada ejecución (~100 chunks, pocos segundos). En producción se usaría Qdrant persistente o un servidor Qdrant, con *upsert* por registro cuando cambie un producto o una FAQ.
- **Ejecución local:** se asume un equipo con Ollama y unos 6 GB de memoria libre para Llama 3 8B y nomic.
- **Umbral fijo (0.374):** se estimó con un set pequeño.
- **Preguntas de enumeración:** el catálogo permite listar los productos, pero preguntas como "¿cuáles tienen stock?" o "¿cuál es el más barato?" requieren consultas estructuradas, no búsqueda por similitud.