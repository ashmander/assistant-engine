# Fase 1: Selección de Componentes Clave del Sistema RAG

> Las secciones 1 a 4 listan las alternativas candidatas y justifican **por qué
> entran en la lista**. La sección 5 presenta la **elección final**, justificada
> con los resultados del notebook `notebooks/experimentacion_rag.ipynb`
> (CSV completos en `notebooks/resultados/`).

## 1. Contexto y restricciones heredadas de la Entrega 1

En la Entrega 1 (`Seleccion Modelo.md`, `Evaluacion de Asistente.md`) se definió:

- **LLM:** Llama 3 (8B) ejecutado localmente con Ollama.
- **Costo:** costo cero en licencias; operación local o en servidores propios.
- **Privacidad:** los datos de clientes y pedidos no deben salir de la
  infraestructura de EcoMarket ni usarse para reentrenar modelos.
- **Idioma:** los clientes escriben en español, con modismos, sin tildes y con
  errores de escritura.
- **Alcance:** el asistente debe responder lo que esté en la base de conocimiento
  y reconocer cuándo **no** tiene información para responder (escalar a humano).

Estas restricciones definen los criterios con los que se armaron las listas.

## 2. Criterios de evaluación

| Criterio | Cómo se mide en el notebook |
|---|---|
| Precisión de recuperación en español | Hit@1, Hit@3, MRR sobre un set de preguntas etiquetadas |
| Robustez lingüística | Desglose por variante de pregunta: formal, coloquial, sin tildes, con errores |
| Detección de preguntas fuera de alcance | AUC del puntaje máximo de similitud (dentro vs fuera de alcance) |
| Costo | Licencia, costo por token, hardware requerido |
| Eficiencia | Tiempo de indexación, chunks/segundo, latencia por consulta, dimensión del vector |
| Escalabilidad (BD vectorial) | Latencia de inserción y búsqueda con 1k, 10k y 100k vectores |
| Facilidad de uso / operación | Infraestructura requerida, persistencia, filtros por metadatos, integración con LangChain |

## 3. Modelos de Embeddings candidatos

### 3.1 Por qué estos modelos y no otros

La lista se armó con cuatro filtros:

1. **Multilingües o entrenados en español.** Se descartaron modelos solo inglés
   (p. ej. `all-MiniLM-L6-v2`, `nomic-embed-text` v1, `mxbai-embed-large`) porque
   el corpus y las preguntas son en español.
2. **Ejecutables localmente y gratuitos** (licencias MIT / Apache 2.0), en línea
   con la decisión de costo cero y privacidad de la Entrega 1.
3. **Tamaños variados** (de ~110M a ~570M de parámetros) para medir si un modelo
   más grande compensa su costo de cómputo en un corpus pequeño como el de EcoMarket.
4. **Referencias de comparación:** un modelo propietario y un baseline léxico,
   para responder la pregunta guía
   "¿código abierto o propietario?" con datos y no solo con supuestos.

### 3.2 Lista de candidatos

| # | Modelo | Tipo / Acceso | Params | Dim. | Máx. tokens | Por qué está en la lista |
|---|---|---|---|---|---|---|
| 1 | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Open source (HF), Apache 2.0 | 118M | 384 | 128 | El modelo multilingüe más liviano y popular de sentence-transformers. Corre en CPU sin problema. Representa la opción "mínimo costo de cómputo". |
| 2 | `intfloat/multilingual-e5-small` | Open source (HF), MIT | 118M | 384 | 512 | Mismo tamaño que el #1 pero entrenado específicamente para recuperación (query/passage) y con contexto de 512 tokens. Permite aislar el efecto del entrenamiento con el mismo tamaño. |
| 3 | `intfloat/multilingual-e5-base` | Open source (HF), MIT | 278M | 768 | 512 | Versión mediana de la familia E5. Permite medir si duplicar el tamaño mejora la recuperación. |
| 4 | `BAAI/bge-m3` | Open source (HF), MIT | 568M | 1024 | 8192 | Estado del arte open source multilingüe (100+ idiomas) en benchmarks como MIRACL/MTEB. Representa la opción "máxima calidad local". Ventana larga útil para chunks grandes. |
| 5 | `hiiamsid/sentence_similarity_spanish_es` | Open source (HF), Apache 2.0 | 110M | 768 | 512 | Basado en BETO (BERT entrenado en español). Representa la alternativa **monolingüe en español** frente a los multilingües. |
| 6 | `nomic-embed-text-v2-moe` (Ollama) | Open source, Apache 2.0, vía Ollama | 475M (305M activos) | 768 | 512 | Multilingüe, arquitectura Mixture-of-Experts. Corre en **Ollama**, el mismo runtime del LLM de la Entrega 1, lo que simplifica el despliegue (un solo servicio). Ya está disponible localmente. |
| 7 | `text-embedding-3-small` (OpenAI) | Propietario, API de pago | N/D | 1536 | 8191 | Referencia **propietaria** de bajo costo (~USD 0.02 por millón de tokens). Se evalúa solo si existe `OPENAI_API_KEY`; sirve para saber si la opción propietaria ofrece una ventaja que justifique enviar datos a un tercero. |
| 8 | BM25 (`rank-bm25`) | Baseline léxico, sin red neuronal | — | — | — | No es un modelo de embeddings. Se incluye como piso de referencia: si un modelo denso no supera a BM25, no aporta valor. Además, es fuerte en coincidencias exactas (códigos de pedido, SKUs). |

### 3.3 Qué se espera aprender del experimento

- Si los modelos entrenados para recuperación (E5, BGE-M3, Nomic) superan a los
  de paráfrasis (MiniLM) y al monolingüe (BETO).
- Si el modelo más grande (BGE-M3) justifica su costo frente a los pequeños.
- Qué modelos manejan peor códigos exactos (`ECO-1003`) y si hace falta
  búsqueda híbrida (denso + BM25).
- Si algún modelo separa bien preguntas dentro y fuera de alcance mediante un
  umbral de similitud.

## 4. Bases de Datos Vectoriales candidatas

### 4.1 Por qué estas opciones y no otras

1. **Las tres que menciona la consigna** (Pinecone, ChromaDB, Weaviate) para
   compararlas directamente.
2. **Dos alternativas open source muy usadas** que cubren extremos que las
   anteriores no cubren: FAISS (librería pura, máximo rendimiento, sin servidor)
   y Qdrant (base de datos completa que también corre embebida en Python).
3. Las cinco tienen **integración oficial con LangChain**, el framework sugerido
   para la Fase 3.
4. Cubren los tres modelos de despliegue posibles: **embebida en el proceso**
   (Chroma, FAISS, Qdrant local), **servidor propio** (Qdrant, Weaviate, Chroma
   server) y **SaaS administrado** (Pinecone, Weaviate Cloud, Qdrant Cloud).

### 4.2 Lista de candidatos

| # | Opción | Licencia / Modelo | Despliegue | Ventajas esperadas | Desventajas esperadas |
|---|---|---|---|---|---|
| 1 | **ChromaDB** | Open source (Apache 2.0) | Embebida en Python, persistente en disco, o servidor | Usada en `rag_ejemplo.py`; cero infraestructura; filtros por metadatos; muy fácil de usar | Pensada para un solo nodo; escalabilidad horizontal limitada |
| 2 | **FAISS** (Meta) | Open source (MIT) | Librería en proceso | Muy rápida; muchos tipos de índice (Flat, HNSW, IVF, PQ); referencia de rendimiento | No es una BD: no guarda textos ni metadatos, no tiene filtros ni API de actualización cómoda; persistencia manual |
| 3 | **Qdrant** | Open source (Apache 2.0) | Modo local en Python, servidor Docker, o Qdrant Cloud (capa gratuita) | Filtros potentes por payload; búsqueda híbrida (denso + disperso); el mismo código pasa de local a servidor | El modo local en Python es búsqueda exacta (no HNSW); el servidor requiere operar un contenedor |
| 4 | **Weaviate** | Open source (BSD-3) | Servidor Docker, modo embebido o Weaviate Cloud | Búsqueda híbrida BM25 + vector integrada; esquema tipado; módulos de vectorización | Más pesado de operar (servidor, esquema); curva de aprendizaje mayor |
| 5 | **Pinecone** | Propietario (SaaS) | Solo nube administrada (serverless) | Cero operación; escala automática; capa gratuita | Requiere internet y API key; los datos salen de EcoMarket (choca con la política de privacidad de la Entrega 1); costo al crecer; vendor lock-in |

**Nota de ejecución:** Chroma, FAISS y Qdrant corren embebidos en Python.
Weaviate corre en Docker (`docker-compose.yml`) y Pinecone en su nube
(`PINECONE_API_KEY` en `.env`). Si alguno no está disponible al ejecutar el
notebook, se declara como limitación.

### 4.3 Descartadas de la lista

- **pgvector (PostgreSQL):** buena opción si EcoMarket ya usa Postgres, pero
  requiere un servidor de base de datos y no aporta un punto de comparación
  distinto a Qdrant/Weaviate para este taller.
- **Milvus:** orientada a miles de millones de vectores; sobredimensionada para
  una base de conocimiento de cientos de fragmentos.
- **Elasticsearch / OpenSearch:** potentes para híbrido, pero su costo
  operativo es alto para el tamaño del caso.

### 4.4 Qué se espera aprender del experimento

- Si todas devuelven los mismos resultados que una búsqueda exacta (recall@k vs
  fuerza bruta), es decir, si el índice aproximado pierde precisión.
- Cómo crecen los tiempos de inserción y búsqueda al pasar de 1k a 100k vectores.
- Qué tan simple es cada API (soporte de metadatos, persistencia, infraestructura).

## 5. Elección

**Método de evaluación (resumen):** 82 preguntas escritas como las haría un
cliente (72 con respuesta en la base, 10 fuera de alcance), sobre las cinco
fuentes (política, catálogo, inventario, FAQ y pedidos), en cuatro variantes:
formal, coloquial, sin tildes y con errores. Un chunk recuperado es relevante si
contiene la evidencia etiquetada. Métricas: MRR@5, Hit@k, AUC para detectar
preguntas fuera de alcance, velocidad y latencia. Cada modelo se probó con las
9 estrategias de chunking de `BaseDeConocimiento.md`.

### 5.1 Modelo de embeddings: `nomic-embed-text-v2-moe` (vía Ollama)

Resultados con la mejor estrategia de chunking de cada modelo:

| Modelo | MRR@5 | IC 95% | Hit@1 | AUC fuera de alcance | Dim. | Chunks/s | Latencia consulta |
|---|---|---|---|---|---|---|---|
| **nomic-v2-moe** | **0.894** | 0.83 - 0.95 | **0.861** | 0.994 | 768 | 89 | 10.7 ms |
| openai-3-small | 0.891 | 0.83 - 0.95 | 0.833 | 0.996 | 1536 | 51 | 324 ms |
| bge-m3 | 0.863 | 0.80 - 0.92 | 0.778 | 0.992 | 1024 | 92 | 13.8 ms |
| e5-small | 0.848 | 0.77 - 0.91 | 0.778 | 0.992 | 384 | 674 | 5.2 ms |
| e5-base | 0.824 | 0.75 - 0.89 | 0.750 | 0.985 | 768 | 256 | 6.7 ms |
| BM25 (baseline léxico) | 0.656 | 0.56 - 0.75 | 0.528 | 0.778 | — | — | — |
| minilm-multilingüe | 0.610 | 0.51 - 0.71 | 0.514 | 0.938 | 384 | 845 | 5.4 ms |
| beto-español | 0.599 | 0.51 - 0.69 | 0.472 | 0.922 | 768 | 288 | 6.7 ms |

Robustez en español (MRR@5 por variante de pregunta):

| Modelo | Formal | Coloquial | Sin tildes | Con errores |
|---|---|---|---|---|
| **nomic-v2-moe** | 0.880 | 0.818 | 0.923 | **1.000** |
| openai-3-small | 0.876 | 0.859 | 0.885 | 1.000 |
| bge-m3 | 0.847 | 0.826 | 0.938 | 0.870 |
| e5-small | 0.863 | 0.727 | 0.938 | 0.796 |
| beto-español | 0.667 | 0.561 | 0.500 | 0.494 |
| minilm-multilingüe | 0.574 | 0.659 | 0.846 | 0.370 |

MRR@5 por fuente:

| Modelo | Política | Catálogo | Inventario | FAQ | Pedidos |
|---|---|---|---|---|---|
| **nomic-v2-moe** | **0.870** | **1.000** | 0.917 | 0.967 | **0.750** |
| openai-3-small | 0.853 | 1.000 | 1.000 | 1.000 | 0.604 |
| bge-m3 | 0.840 | 1.000 | 0.917 | 0.922 | 0.681 |
| e5-small | 0.833 | 0.767 | 0.917 | 0.917 | 0.723 |
| e5-base | 0.816 | 0.547 | 0.875 | 0.950 | 0.712 |

**Justificación:**

- **Precisión:** tiene el mejor MRR@5 y Hit@1. Su intervalo de confianza se
  solapa con los de OpenAI, BGE-M3 y E5-small, así que estadísticamente forman
  un grupo empatado. Dentro de ese grupo, nomic es el más robusto a errores de
  escritura (1.0), el mejor de los densos con códigos de pedido (0.75) y en la
  política (0.870), y recupera perfecto el catálogo (1.0), donde E5-small cae a
  0.767 y E5-base a 0.547.
- **Español:** es multilingüe. Los modelos entrenados para recuperación
  (nomic, E5, BGE-M3) superan claramente al monolingüe en español (BETO, 0.60)
  y al de paráfrasis (MiniLM, 0.61). El idioma importa, pero el tipo de
  entrenamiento importa más.
- **Costo:** gratis y open source (Apache 2.0). Corre en **Ollama**, el mismo
  servicio que ya ejecuta Llama 3 como LLM de chat (Entrega 1): no agrega
  infraestructura.
- **¿Open source o propietario?** El modelo propietario (OpenAI
  `text-embedding-3-small`) **no mejora** la precisión (0.891 vs 0.894), es
  unas 30 veces más lento por la red (324 ms vs 10.7 ms), tiene costo por token
  y envía a un tercero los datos de EcoMarket, lo que contradice la política de
  privacidad de la Entrega 1. Elegimos open source.
- **Desventajas aceptadas:** indexa más lento que E5-small (89 vs 674
  chunks/s), algo irrelevante para una base de cientos de chunks. Usa 768
  dimensiones (el doble que E5-small).
- **Alternativa:** `multilingual-e5-small`, si el volumen creciera mucho o se
  quisiera prescindir de Ollama para los embeddings (a costa de peor
  recuperación del catálogo).
- **Descartados por datos:** MiniLM solo admite 128 tokens. Recorta el 100% de
  los chunks de 1024 caracteres y no recupera ningún pedido por su código
  (MRR 0.0). BETO se degrada con texto sin tildes o con errores.

### 5.2 Base de datos vectorial: Qdrant

Corpus real (129 chunks, vectores de nomic, chunking por párrafos):

| Base | Inserción | Latencia p50 | Recall@5 vs exacto | MRR@5 | Filtro por metadatos |
|---|---|---|---|---|---|
| ChromaDB | 19 ms | 0.36 ms | 1.0 | 0.894 | Nativo |
| FAISS (Flat) | 0.2 ms | 0.007 ms | 1.0 | 0.894 | No (post-filtrado manual) |
| FAISS (HNSW) | 2 ms | 0.016 ms | 1.0 | 0.894 | No (post-filtrado manual) |
| **Qdrant (local)** | 5 ms | 0.28 ms | 1.0 | 0.894 | **Nativo** |
| Weaviate (Docker) | 1063 ms | 0.87 ms | 1.0 | 0.894 | Nativo |
| Pinecone (nube) | 1616 ms | 100 ms | 1.0 | 0.894 | Nativo |

Prueba de escala (vectores sintéticos de 768 dimensiones):

| Base | Recall@10 1k | Recall@10 10k | Recall@10 100k | Latencia p50 100k | Inserción 100k |
|---|---|---|---|---|---|
| ChromaDB | 0.98 | 0.42 | 0.07 | 2.3 ms | 32 s |
| FAISS (Flat) | 1.00 | 1.00 | 1.00 | 4.1 ms | 0.02 s |
| FAISS (HNSW) | 0.99 | 0.52 | 0.10 | 0.5 ms | 34 s |
| **Qdrant (local)** | **1.00** | **1.00** | **1.00** | 39 ms | 9 s |
| Weaviate | 1.00 | 0.69 | 0.16 | 2.6 ms | 34 s |

**Justificación:**

- **Con el corpus real todas aciertan igual** (recall 1.0, mismo MRR). La
  decisión se basa entonces en costo, privacidad, facilidad de uso y
  escalabilidad.
- **Precisión garantizada:** el modo local de Qdrant hace búsqueda exacta. En
  la prueba de escala mantiene recall 1.0 hasta 100k vectores. Con la
  configuración por defecto, Chroma, Weaviate y FAISS-HNSW pierden precisión al
  crecer (0.07 a 0.16 con 100k).
- **Funcionalidad:** filtros nativos por metadatos (p. ej. buscar solo en
  `fuente = politica`), payload con el texto y la fuente, y persistencia en
  disco. FAISS es el más rápido, pero no guarda textos ni metadatos ni filtra:
  habría que construir esa capa a mano.
- **Escalabilidad:** el mismo cliente Python pasa del modo embebido a un
  servidor Qdrant (Docker) o a un cluster con HNSW, sharding y réplicas, sin
  reescribir el código. También soporta búsqueda híbrida con vectores dispersos
  si más adelante se necesita.
- **Costo y privacidad:** open source (Apache 2.0), sin costo, con los datos
  dentro de EcoMarket.
- **Desventaja aceptada:** al ser búsqueda exacta, la latencia del modo local
  crece de forma lineal (39 ms con 100k vectores). Con el tamaño real de
  EcoMarket (cientos a pocos miles de chunks) se mantiene por debajo de 5 ms. Si
  la base creciera a cientos de miles de chunks, se migraría al servidor Qdrant
  con índice HNSW.
- **Por qué no las demás:**
  - **Pinecone:** sin ventaja de precisión, latencia unas 300 veces mayor por la
    red (100 ms), costo al crecer y datos alojados en un tercero.
  - **Weaviate:** equivalente en funciones, pero exige operar un servidor desde
    el primer día, sin beneficio para este volumen.
  - **ChromaDB:** la alternativa más cercana (simple, embebida, la usa el
    ejemplo del curso), pero su índice HNSW por defecto (`search_ef = 10`)
    perdió precisión al escalar y habría que ajustarlo.

### 5.3 Limitaciones de la evaluación

- **Set de evaluación pequeño** (72 preguntas con respuesta): los intervalos de
  confianza miden unos ±0.06. Las diferencias dentro del grupo líder no son
  concluyentes, por lo que también se usaron criterios de costo, robustez e
  integración.
- **Prueba de escala con vectores aleatorios:** es el peor caso para los
  índices aproximados (HNSW), porque los embeddings reales sí se agrupan por
  tema. Además se usaron los parámetros por defecto. La pérdida de recall de
  Chroma, Weaviate y FAISS-HNSW sería menor con datos reales o con parámetros
  ajustados.
- **Latencias de Weaviate y Pinecone:** incluyen el arranque y la red. La
  inserción de 1 s de Weaviate en el corpus real es sobre todo costo de arranque
  (1.000 vectores sintéticos tardaron 0.15 s).
- **Hardware:** todo se midió en un Apple M5 Pro (24 GB, aceleración MPS). Los
  tiempos absolutos cambian en otro equipo; las comparaciones relativas
  deberían mantenerse.
