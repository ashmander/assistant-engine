# Fase 2: Creación de la Base de Conocimiento de Documentos

**1. Identificación de Documentos**
En la Entrega 1 el asistente solo atendía estado de pedidos y devoluciones, y recibía todo el archivo de datos en el *prompt*. Para responder cualquier tipo de solicitud definimos cinco documentos, elegidos por cubrir los temas que más consulta un cliente de e-commerce y por tener formatos distintos:
*   **Política de devoluciones, envíos y garantías (`politica_devoluciones.pdf`):** Texto largo con secciones numeradas. Es la fuente oficial de plazos, condiciones y excepciones; un error aquí genera reclamos.
*   **Catálogo de productos (`catalogo_productos.pdf`):** Lista corta de productos por categoría. Responde preguntas como "¿qué productos venden?", que no se pueden armar juntando fichas sueltas.
*   **Inventario de productos (`inventario_productos.xlsx`):** Una fila por producto con precio, stock y regla de devolución propia.
*   **Preguntas frecuentes (`preguntas_frecuentes.json`):** Pares pregunta-respuesta sobre pagos, cuenta, EcoPuntos y facturación, temas que no están en la política.
*   **Pedidos (`pedidos.xlsx`):** Una fila por pedido con estado, fechas y transportadora. Responde "¿dónde está mi pedido?", la consulta más frecuente.

**2. Segmentación (Chunking)**
Para este critero se hicieron varios experimentos en el notebook y se concluye que el tipo de informacion que se procesa es vital para saber el tipo de chuck que se debe aplicar. No es lo mismo aplicar chucks para textos planos en PDF que para registros en excel. Tener un vector que contenga varios registros de excel puede dar informacion innecesaria al cliente. Por eso se definieron los siguients chucks:
*   **Política (PDF): por párrafos.** Fue la mejor estrategia (MRR@5 de 0.777 en promedio y 0.894 con nomic). En una política cada párrafo suele contener una regla completa, que es justo lo que pregunta el cliente. Las de tamaño fijo rindieron peor (0.74) porque cortan oraciones a la mitad, y la recursiva depende de ajustar tamaño y solapamiento. Además, los párrafos (~250 caracteres) nunca superan el límite de tokens del modelo.
*   **Catálogo (PDF tipo lista): recursiva de 1.000 caracteres con 200 de solapamiento.** La lista completa queda en solo 2 fragmentos, de modo que una sola búsqueda la trae entera. Nomic la recuperó en primer lugar en todas las preguntas de catálogo.
*   **Inventario y FAQ (Excel y JSON): un registro = un fragmento.** Cada fila o pregunta frecuente es una unidad completa; aplanar la tabla y cortarla mezcla varios registros en un mismo vector. Con nomic, esta opción subió de 0.805 a 0.900.

Cada fragmento lleva metadatos (`fuente`, `seccion` o `registro_id`, `pagina`) para filtrar la búsqueda, citar la fuente y actualizar un registro sin reindexar todo.

**3. Indexación**
El proceso para pasar de documentos a vectores consultables es:
1.  **Carga:** Leer cada fuente con su librería (`pymupdf` para PDF, `pandas` para Excel, `json` para FAQ).
2.  **Limpieza:** Eliminar saltos de línea y encabezados repetidos del PDF, y convertir cada registro a texto (`Producto: ... Precio: ... Devolución: ...`).
3.  **Segmentación:** Aplicar la estrategia de cada documento (sección 2) y adjuntar metadatos.
4.  **Vectorización:** Pasar cada fragmento por nomic-embed-text-v2-moe vía Ollama, con el prefijo `search_document:` y normalización para usar similitud coseno.
5.  **Carga en Qdrant:** Insertar `(id, vector, texto, metadatos)` con un `id` fijo (p. ej. `inventario:EM-007`) que permite actualizar un registro (*upsert*) cuando cambia.
6.  **Consulta:** La pregunta del cliente se vectoriza con el mismo modelo (prefijo `search_query:`) y se recuperan los 5 fragmentos más parecidos, que se pasan como contexto a Llama 3.

**4. Consideraciones adicionales**
*   **Pedidos:** No se indexan en Qdrant. Los embeddings recuperan mal códigos exactos como `ECO-1003` (MRR@5 de 0.75) y los pedidos cambian en tiempo real. Si la pregunta trae un código de pedido, se busca por coincidencia exacta en la tabla; si no lo trae, el asistente lo pide, como en la Entrega 1.
*   **Privacidad:** No se indexan el nombre del cliente ni los productos de cada pedido, siguiendo las reglas de la Entrega 1.
*   **Preguntas fuera de alcance:** Si la similitud máxima es menor a 0.374, el asistente responde que no tiene esa información y ofrece un agente humano. Con ese umbral se aceptó el 97% de las preguntas válidas y se rechazó el 100% de las fuera de alcance.
*   **Actualización:** Inventario y FAQ se actualizan registro por registro; la política se reindexa completa cuando se publica una nueva versión.

**5. Limitaciones**
El corpus es pequeño (~9.500 caracteres de política y 90 registros) y el umbral se estimó con solo 10 preguntas fuera de alcance, por lo que debe revalidarse con consultas reales. Si el catálogo crece, se partirá en más fragmentos y convendría segmentarlo por categoría.
