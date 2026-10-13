# Fase 2: Creación de la Base de Conocimiento de Documentos

> Las secciones 1 a 3 identifican los documentos de la base de conocimiento y
> listan las estrategias de segmentación (chunking) e indexación candidatas,
> justificando **por qué entran en la lista**. La sección 4 presenta la
> **estrategia elegida**, justificada con los resultados del notebook
> `notebooks/experimentacion_rag.ipynb` (CSV completos en `notebooks/resultados/`).

## 1. Identificación de Documentos

En la Entrega 1 el asistente solo atendía dos tipos de consulta (estado de
pedido y devoluciones) y recibía **todo** el archivo de datos dentro del prompt.
Para responder "cualquier tipo de solicitud" se necesita una base de
conocimiento más amplia y una recuperación selectiva. Se identificaron cinco
fuentes, elegidas por cubrir los temas que más consultan los clientes de un
e-commerce y por representar **formatos distintos** (texto largo no
estructurado, lista corta, tablas y pares pregunta-respuesta), que exigen
tratamientos distintos al segmentar.

| # | Documento | Archivo | Formato | Tipo de contenido | Por qué es crucial |
|---|---|---|---|---|---|
| 1 | Política de devoluciones, reembolsos, envíos y garantías | `data/politica_devoluciones.pdf` | PDF | Texto largo, no estructurado, con secciones numeradas | Es la fuente "legal" de reglas: plazos, condiciones, excepciones, reembolsos. Las respuestas incorrectas aquí generan reclamos. |
| 2 | Catálogo de productos | `data/catalogo_productos.pdf` | PDF | Lista corta: nombres de productos agrupados por categoría (generada desde el inventario) | Responde preguntas de enumeración como "¿qué productos venden?" o "¿qué tienen de jardinería?", que la búsqueda vectorial no puede armar juntando fichas de producto sueltas. |
| 3 | Inventario de productos | `data/inventario_productos.xlsx` | Excel | Tabla: una fila por producto (SKU, precio, stock, si es devolvible, plazo, motivo) | Responde disponibilidad, precio y la regla de devolución **por producto** (evoluciona `products.txt` de la Entrega 1). |
| 4 | Preguntas frecuentes | `data/preguntas_frecuentes.json` | JSON | Lista de pares pregunta-respuesta con categoría | Cubre temas que no están en la política: pagos, cuenta, EcoPuntos, empaques, facturación. Es el formato más cercano a cómo pregunta el cliente. |
| 5 | Pedidos | `data/pedidos.xlsx` | Excel | Tabla: una fila por pedido (tracking, estado, fechas, transportadora, observaciones) | Responde "¿dónde está mi pedido?", la consulta más frecuente (evoluciona `orders.txt` de la Entrega 1). |

**Consideraciones sobre los pedidos:**

- Contiene datos personales (nombre del cliente) y la lista de productos del
  pedido. Siguiendo las reglas de la Entrega 1 (no revelar productos del pedido,
  privacidad), estos campos son **candidatos a no indexarse**.
- Es información que cambia en tiempo real. Una alternativa a indexarla en la BD
  vectorial es consultarla por **búsqueda exacta** por número de seguimiento. El
  notebook mide qué tan bien recuperan los modelos de embeddings un código como
  `ECO-1003` para decidir con datos.

## 2. Segmentación (Chunking)

### 2.1 Por qué importa

El chunk es la unidad que se recupera y se inyecta al prompt del LLM:

- **Chunks muy grandes:** mezclan varios temas, diluyen el vector (peor
  similitud) y consumen la ventana de contexto de Llama 3 8B (8k tokens).
- **Chunks muy pequeños:** pierden contexto (p. ej. una excepción separada de la
  regla) y la respuesta queda incompleta.
- **Cortes en mal lugar:** una frase partida a la mitad no es recuperable.

Además, varios modelos tienen un límite de tokens de entrada (MiniLM: 128
tokens); un chunk más largo se **trunca silenciosamente** al generar el embedding.

### 2.2 Estrategias candidatas para texto no estructurado (PDF)

| # | Estrategia | Variantes a probar | Por qué está en la lista |
|---|---|---|---|
| 1 | **Tamaño fijo** (por caracteres, sin respetar estructura) | 256, 512 y 1024 caracteres, solapamiento ~15% | Es la estrategia más simple y el punto de comparación. Permite ver el costo de cortar sin mirar el contenido. |
| 2 | **Por párrafos** | Un párrafo = un chunk | Los párrafos de una política suelen contener una idea completa. Sin parámetros que ajustar. |
| 3 | **Recursiva** (`RecursiveCharacterTextSplitter`) | 256, 512 y 1024 caracteres, solapamiento ~15% | Es la usada en `rag_ejemplo.py` (1000/200). Intenta cortar por párrafo, luego por línea, luego por palabra: respeta estructura pero controla el tamaño. |
| 4 | **Por secciones del documento** | Un encabezado numerado (p. ej. `4. Productos no elegibles`) = un chunk, con el título incluido | La política tiene secciones temáticas claras; cada sección responde un tipo de pregunta. Aprovecha la estructura propia del documento. |
| 5 | **Semántica** | Corte cuando la similitud entre oraciones consecutivas cae (percentil 85 de distancia) | Agrupa oraciones por tema sin depender del formato. Se incluye para medir si su costo (embeber cada oración) se justifica. |

### 2.3 Estrategia para el catálogo (PDF tipo lista)

El catálogo no es texto en párrafos sino una lista corta (~1.200 caracteres).
Se segmenta con `RecursiveCharacterTextSplitter` de **1000 caracteres y 200 de
solapamiento** (la configuración de `rag_ejemplo.py`). El objetivo es que la
lista completa quede en muy pocos chunks, para que una sola búsqueda la
recupere entera. Con el tamaño actual quedan 2 chunks (974 y 416 caracteres),
ambos dentro del límite de 512 tokens de nomic.

### 2.4 Estrategias candidatas para datos estructurados (Excel y JSON)

| # | Estrategia | Por qué está en la lista |
|---|---|---|
| A | **Un registro = un chunk** (una fila del Excel, un par pregunta-respuesta del JSON), serializado como texto `campo: valor` | Cada registro es una unidad de información autocontenida; cortarlo o mezclarlo con otros no tiene sentido semántico. Permite guardar el ID (SKU, tracking, id de FAQ) como metadato. |
| B | **Tabla aplanada a texto + chunking recursivo** | Es lo que pasa si se trata todo como texto plano (lo más simple con un loader genérico). Se incluye para cuantificar la pérdida frente a la opción A. |

### 2.5 Metadatos por chunk

Independiente de la estrategia, cada chunk llevará metadatos: `fuente`
(politica / catalogo / inventario / faq / pedidos), `seccion` o `registro_id`, y `pagina`
cuando aplique. Sirven para filtrar la búsqueda, citar la fuente en la respuesta
y actualizar un registro sin reindexar todo.

## 3. Indexación

Proceso propuesto (independiente del modelo y BD que se elijan):

1. **Carga:** leer cada fuente con su loader (`pymupdf` para el PDF, `pandas`
   para Excel, `json` para FAQ).
2. **Normalización:** limpiar espacios, saltos de línea del PDF y encabezados
   repetidos; serializar registros estructurados como texto `campo: valor`.
3. **Segmentación:** aplicar la estrategia de chunking según el tipo de fuente
   (sección 2) y adjuntar metadatos.
4. **Vectorización:** pasar cada chunk por el modelo de embeddings elegido. Si el
   modelo lo requiere, agregar prefijos (`passage:` / `query:` en E5,
   `search_document:` / `search_query:` en Nomic). Normalizar los vectores (L2)
   para usar similitud coseno.
5. **Carga en la BD vectorial:** insertar `(id, vector, texto, metadatos)` en
   lotes. El `id` es determinístico (p. ej. `inventario:EM-007`) para permitir
   *upsert* cuando cambie un registro.
6. **Consulta:** la pregunta del cliente se vectoriza con el **mismo** modelo y
   se buscan los *k* chunks más similares (opcionalmente filtrando por fuente).
   Si la similitud máxima está por debajo de un umbral, el asistente responde
   que no tiene información y ofrece un agente humano.
7. **Actualización:** inventario y pedidos cambian a diario; se reindexan solo
   los registros modificados (upsert por `id`). La política y las FAQ se
   reindexan completas cuando se publica una nueva versión.

## 4. Elección

Componentes elegidos en `ComponentesSistemaRAG.md`: modelo de embeddings
**nomic-embed-text-v2-moe** y base vectorial **Qdrant**.

### 4.1 Chunking de la política (PDF): por párrafos

MRR@5 promedio de los 7 modelos de embeddings densos (72 preguntas con respuesta):

| Estrategia | MRR@5 | Hit@1 | Hit@5 | Chunks | Largo promedio (caracteres) |
|---|---|---|---|---|---|
| **Por párrafos** | **0.777** | 0.694 | 0.907 | 37 | 254 |
| Por secciones | 0.777 | 0.698 | 0.895 | 15 | 627 |
| Semántico | 0.770 | 0.685 | 0.901 | 16 | 588 |
| Recursivo 512 | 0.770 | 0.681 | 0.915 | 26 | 374 |
| Fijo 512 | 0.746 | 0.649 | 0.901 | 22 | 504 |
| Fijo 256 | 0.738 | 0.661 | 0.877 | 44 | 253 |
| Fijo 1024 | 0.736 | 0.645 | 0.881 | 11 | 1001 |
| Recursivo 1024 | 0.729 | 0.639 | 0.875 | 12 | 806 |
| Recursivo 256 | 0.728 | 0.641 | 0.857 | 57 | 168 |

**Justificación:**

- **Es la mejor estrategia en promedio y también con el modelo elegido**
  (nomic + párrafos = 0.894, la mejor combinación de todo el experimento).
- **Las estrategias que respetan la estructura del documento** (párrafos,
  secciones, recursiva, semántica) superan a las de tamaño fijo, que cortan
  oraciones a la mitad. En una política, cada párrafo suele contener una regla
  completa (plazo, condición o excepción), que es justo lo que pregunta el
  cliente.
- **Tamaño adecuado:** los extremos rinden peor. Los chunks de 256 caracteres
  pierden contexto y los de 1024 mezclan varios temas en un solo vector. Los
  párrafos (~250 caracteres, máximo ~400) además **no se recortan en ningún
  modelo**, mientras que con MiniLM (límite de 128 tokens) se recortaba el 60%
  de las secciones y el 100% de los chunks de 1024.
- **Simplicidad:** no tiene parámetros que ajustar, a diferencia de la
  estrategia recursiva (tamaño y solapamiento). Tampoco requiere vectorizar cada
  oración como la semántica.
- **Detalle de implementación:** el título de la sección se une al primer
  párrafo, y un párrafo que cruza de página se une con su continuación.
- **Alternativa:** por secciones, empatada en promedio (0.777) pero peor con
  nomic (0.861 vs 0.894). Sus chunks son
  2.5 veces más largos y consumen más contexto del LLM por cada resultado.

### 4.2 Chunking del catálogo (PDF tipo lista): recursivo 1000/200

| Modelo | MRR@5 en preguntas de catálogo |
|---|---|
| **nomic-v2-moe** | **1.000** |
| openai-3-small | 1.000 |
| bge-m3 | 1.000 |
| minilm-multilingüe | 0.800 |
| e5-small | 0.767 |
| e5-base | 0.547 |
| BM25 | 0.240 |

- Con nomic, el chunk del catálogo sale **primero** en las 5 preguntas de
  catálogo ("¿qué productos venden?", "dame la lista de todos los productos",
  "¿qué productos de jardinería tienen?", etc.).
- La lista (~1.200 caracteres) queda en 2 chunks. En la prueba del asistente
  ambos entraron en el top 5, así que el LLM recibió la lista completa.
- BM25 falla (0.24): las preguntas de catálogo casi no comparten palabras con
  la lista de nombres. Es un caso donde la búsqueda semántica es indispensable.
- Sin esta fuente, una pregunta de enumeración solo recuperaba 3 fichas de
  producto sueltas (top 5 de 30), y el asistente no podía dar la lista.

### 4.3 Chunking de datos estructurados (Excel y JSON): un registro = un chunk

| Modelo | Por registro (MRR@5) | Texto aplanado + recursivo (MRR@5) |
|---|---|---|
| **nomic-v2-moe** | **0.900** | 0.805 |
| openai-3-small | 0.910 | 0.853 |
| bge-m3 | 0.865 | 0.840 |
| BM25 | 0.802 | 0.829 |

- **Gana en los tres modelos densos.** La mayor diferencia está en las FAQ
  (nomic: 0.967 vs 0.856) y en los pedidos (0.750 vs 0.542): al aplanar, un
  chunk mezcla varios registros y el vector deja de representar a uno solo.
- Cada fila o pregunta frecuente se serializa en lenguaje natural
  (`Producto: ... Precio: ... Devolución: ...`) y guarda su ID (SKU, tracking,
  `FAQ-xx`) como metadato, lo que permite actualizarla con *upsert*.
- **Privacidad (Entrega 1):** de los pedidos no se indexan el nombre del
  cliente ni los productos.

### 4.4 Pedidos: búsqueda exacta por número de seguimiento

MRR@5 de las preguntas sobre pedidos:

| Método | MRR@5 total | Política | Pedidos |
|---|---|---|---|
| nomic (solo embeddings) | **0.894** | **0.870** | 0.750 |
| nomic + BM25 (híbrido RRF) | 0.791 | 0.702 | 0.938 |
| BM25 (solo léxico) | 0.656 | 0.562 | **1.000** |

- Los embeddings recuperan mal los códigos exactos (`ECO-1003`): ningún modelo
  denso supera 0.75 en pedidos. BM25 los encuentra siempre.
- La búsqueda híbrida para todas las preguntas **empeora** el total
  (0.894 → 0.791), porque degrada las preguntas sobre la política, el
  inventario y las FAQ.
- **Decisión:** si la pregunta contiene un código con el formato `ECO-\d{4}`,
  el pedido se busca por **coincidencia exacta** en la tabla de pedidos. El
  resto de las preguntas va por búsqueda vectorial. Además, los pedidos cambian
  en tiempo real: la consulta directa siempre devuelve el estado vigente, sin
  esperar a reindexar.

### 4.5 Detección de preguntas fuera de alcance: umbral de similitud

- Con nomic, el puntaje máximo de similitud separa casi perfectamente las
  preguntas con y sin respuesta (**AUC 0.994**).
- **Umbral elegido: 0.374.** Acepta el 97% de las preguntas con respuesta y
  rechaza el 100% de las preguntas fuera de alcance del set ("¿Cuál es la
  capital de Francia?", "¿Venden celulares iPhone?").
- Por debajo del umbral, el asistente responde que no tiene esa información y
  ofrece un agente humano. Esto cumple el objetivo del taller de "hacerle saber
  al usuario que no tiene las herramientas para atender su solicitud".

### 4.6 Proceso de indexación final

1. **Carga:** `pymupdf` (PDFs por bloques), `pandas` (Excel), `json` (FAQ).
2. **Chunking:** párrafos para la política, recursivo 1000/200 para el
   catálogo, un registro por chunk para inventario y FAQ. Los pedidos **no** se indexan en Qdrant: se consultan por
   coincidencia exacta (4.4). Si el cliente pregunta por un pedido sin dar el
   código, el asistente se lo pide, como establece la regla 4 de la Entrega 1.
3. **Metadatos:** `fuente`, `seccion` o `registro_id`, `pagina`.
4. **Vectorización:** nomic-embed-text-v2-moe vía Ollama, con prefijo
   `search_document: ` para los chunks y `search_query: ` para las preguntas, y
   normalización L2.
5. **Carga en Qdrant:** colección con distancia coseno. El `id` es
   determinístico para hacer *upsert* (p. ej. `inventario:EM-007`).
6. **Consulta:**
   1. Si la pregunta trae un código `ECO-\d{4}`, se busca el pedido por
      coincidencia exacta.
   2. Si no, se vectoriza la pregunta y se recuperan los 5 chunks más similares.
   3. Si el puntaje máximo es menor que 0.374, se responde "sin información" y
      se escala a un humano.
   4. Si no, los chunks se pasan como contexto a Llama 3 8B.
7. **Actualización:** *upsert* por `id` cuando cambia un producto o una FAQ.
   La política se reindexa completa cuando se publica una nueva versión.

### 4.7 Limitaciones

- **La métrica de cobertura no discriminó:** todas las estrategias obtuvieron
  1.0 porque las evidencias etiquetadas son frases cortas. Con documentos
  reales más largos, las estrategias de tamaño fijo probablemente partirían más
  evidencias.
- **El umbral se estimó con solo 10 preguntas fuera de alcance.** Debe
  revalidarse con consultas reales antes de producción, en particular las que
  están en el borde del dominio (p. ej. productos que EcoMarket no vende).
- **Catálogo en 2 chunks:** si la lista crece, se partirá en más chunks y una
  sola búsqueda podría no traerla completa. A futuro convendría un chunk por
  categoría. Además, en preguntas por categoría el LLM puede preferir las fichas
  del inventario y omitir algún producto.
- **Corpus pequeño** (~9.500 caracteres de política, ~1.200 de catálogo, 90 registros). Con una
  base más grande, las diferencias entre estrategias podrían crecer.
