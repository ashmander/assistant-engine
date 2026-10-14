# Fase 1: Selección de Componentes Clave del Sistema RAG

**1. Modelo de Embeddings: `nomic-embed-text-v2-moe`**
Para convertir los documentos de EcoMarket en vectores proponemos **nomic-embed-text-v2-moe**, un modelo de embeddings **multilingüe y de código abierto** (Apache 2.0) que corre en **Ollama**, el mismo servicio que ya ejecuta Llama 3 (8B) desde la Entrega 1. Así no se suma infraestructura nueva ni costo en licencias, y los datos no salen de EcoMarket.

**2. ¿Por qué este modelo y no otro?**
No lo elegimos por suposición: en el notebook `notebooks/experimentacion_rag.ipynb` comparamos 7 modelos (seis open source de Hugging Face y Ollama, y uno propietario de OpenAI) más BM25 como referencia, con 82 preguntas escritas como las haría un cliente (formales, coloquiales, sin tildes y con errores). Nomic obtuvo el mejor resultado de recuperación (MRR@5 de 0.894), empatado con OpenAI (0.891) y por encima de BGE-M3 (0.863) y E5 (0.848). Los modelos más débiles fueron el de paráfrasis MiniLM (0.610) y el monolingüe en español BETO (0.599): en español importa el idioma, pero importa más que el modelo esté entrenado para búsqueda.

**3. Justificación (criterios clave)**
*   **Precisión:** Mejor MRR@5 y mejor acierto en primera posición (86%). Recupera perfecto el catálogo de productos (1.0), donde E5 cae a 0.55-0.77, y es el mejor de los modelos densos con códigos de pedido.
*   **Español:** Es el más robusto ante preguntas con errores de escritura (1.0) y se mantiene estable con lenguaje coloquial y sin tildes, que es como escriben los clientes.
*   **Costo:** Gratis, local y sin costo por token. Responde una consulta en ~11 ms.
*   **¿Open source o propietario?** Open source. El modelo de OpenAI (`text-embedding-3-small`) no mejora la precisión, es unas 30 veces más lento por la red (324 ms), cobra por token y envía los datos de los clientes a un tercero, lo que contradice la política de privacidad de la Entrega 1.

**4. Base de Datos Vectorial: Qdrant**
Para almacenar los vectores proponemos **Qdrant** en modo local (embebido en Python), con la opción de migrar a un servidor Qdrant (Docker) si la base crece. Es open source, guarda junto a cada vector el texto y sus metadatos (fuente, sección, ID) y permite filtrar la búsqueda, por ejemplo, solo en la política de devoluciones.

**5. Comparación de opciones**
Con el corpus real de EcoMarket (129 fragmentos) todas las bases devolvieron exactamente los mismos resultados, así que la decisión se tomó por escalabilidad, costo y facilidad de uso:
*   **Pinecone:** Cero operación y escala automática, pero es un servicio pago en la nube, tuvo la mayor latencia (~100 ms por la red) y aloja los datos de EcoMarket en un tercero.
*   **ChromaDB:** La más fácil de usar y sin infraestructura, pero en la prueba de escala su índice por defecto perdió precisión al crecer (con 100.000 vectores solo encontró el 7% de los resultados correctos) y habría que ajustarlo.
*   **Weaviate:** Completa (búsqueda híbrida, esquema tipado), pero exige operar un servidor desde el primer día, algo innecesario para el volumen de EcoMarket, y también perdió precisión al escalar.
*   **Qdrant:** Mantuvo el 100% de precisión hasta 100.000 vectores, tiene filtros nativos por metadatos y el mismo código pasa de local a servidor o a la nube sin reescribirse.

**6. Justificación (criterios clave)**
*   **Escalabilidad:** El modo local hace búsqueda exacta, por lo que no pierde precisión. Su latencia crece con el tamaño (39 ms con 100.000 vectores), pero con el volumen real de EcoMarket (cientos a pocos miles de fragmentos) se mantiene por debajo de 5 ms. Si crece mucho, se migra al servidor con índice HNSW.
*   **Costo:** Cero en licencias (Apache 2.0), operando en servidores propios.
*   **Facilidad de uso:** Se instala como una librería de Python, persiste en disco, tiene integración oficial con LangChain y permite actualizar un registro (*upsert*) sin reindexar todo.

**7. Limitaciones**
El set de evaluación es pequeño (72 preguntas con respuesta), por lo que las diferencias entre los mejores modelos no son concluyentes y se desempató con costo, robustez e integración. La prueba de escala usó vectores aleatorios y parámetros por defecto, el peor caso para Chroma y Weaviate; con datos reales o ajustes su pérdida de precisión sería menor.
