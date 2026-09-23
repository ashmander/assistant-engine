# Propuesta de IA Generativa para Asistente de EcoMarket

**1. Tipo de modelo más adecuado**
Para el asistente de EcoMarket, proponemos una **solución híbrida** basada en un Modelo de Lenguaje Pequeño (SLM) de código abierto, específicamente **Llama 3 (8B)**, operando bajo una arquitectura de Generación Aumentada por Recuperación (RAG), complementada con un sistema de enrutamiento (hand-off) a agentes humanos para las consultas complejas.

**2. ¿Por qué este modelo y no otro?**
Seleccionamos Llama 3 (8B) en lugar de modelos masivos como GPT-4 porque el 80% de nuestras consultas son transaccionales y repetitivas (estados de pedido, devoluciones). Un modelo masivo generaría sobrecostos innecesarios por token y subutilización de capacidades. Llama 3 (8B) ofrece el equilibrio perfecto: tiene la precisión necesaria para extraer datos exactos de una base de datos mediante RAG y cuenta con la fluidez conversacional suficiente para atender al cliente de manera amable y natural. Además, al ser open-source, evitamos problemas de licencias y límites de uso (vendor lock-in).

**3. Arquitectura propuesta e Integración**
La arquitectura no requerirá *fine-tuning* (afinamiento de pesos), ya que esto es costoso y los datos de pedidos cambian en tiempo real. En su lugar, usaremos un modelo de propósito general optimizado para seguir instrucciones, integrado mediante **RAG (Retrieval-Augmented Generation)**. 
*   **Flujo:** Cuando un cliente pregunta por su pedido, el sistema consulta la base de datos de EcoMarket (catálogo, envíos), extrae la información relevante y se la pasa al modelo en el *prompt*. El modelo formula la respuesta basándose estrictamente en esos datos, evitando alucinaciones.
*   **Gestión del 20% complejo:** El modelo tendrá un prompt de clasificación (Router). Si detecta sentimientos negativos, quejas o problemas técnicos, derivará inmediatamente el chat a un agente humano, garantizando la empatía requerida.

**4. Justificación (Criterios clave)**
*   **Costo:** Costo cero en licencias de API, operando de manera local o en servidores propios.
*   **Facilidad de integración:** Al usar un modelo open-source ligero, la integración con nuestra aplicación existente es directa y no dependemos de servicios de terceros.
*   **Calidad de respuesta:** Garantizada por el control del contexto (prompt engineering + RAG). El modelo solo responde con la verdad de nuestra base de datos.
*   **Escalabilidad:** Para evitar cuellos de botella en la base de datos si la lista de pedidos crece, implementaremos una política de retención: el modelo solo leerá una base de datos activa con pedidos recientes; los pedidos históricos resueltos se migrarán a un almacenamiento frío (Cold Storage) no conectado al LLM, optimizando así los tiempos de búsqueda y respuesta.