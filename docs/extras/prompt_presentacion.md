necesito que fagis una presentació basant-te en el document adjunt i que es centri en l'objectiu del projecte, que es fa missió i que ens diferència envers la resta.
--> seria ideal que hagués un exemple enmig de la presentació per tal que es segueixi el que s'està  fent.
L'arquitectura de 3 fases
fase1 :
pipeline d'extracció, enriquiment i verificació 
extracció --> descobriment de urls
--> extraccio de contingut
motor NLP + enriquiment --> extraccio d'entitats, extracció d'afirmacions, classificacio de la tematica, anàlisis de sentiment, qualitat de l'editorial, llegibilitat, objectivitat, constructivitat per determinar el seu impacte social, generem embeddings (per fer us  després de la IA)
Fact checking
- filtro de admision: relevancia temàtica, impacte positiu, no-duplicitat
- selecció d'afirmacions verificables: (priorització per article i deduplicació semàntica (s'eliminen duplicats))
- recuperació d'evidència: SearXNG + Qdrant (embeddings generats anteriorment).
- ranking de evidencia: afinidad semàntica, recencia (evidencia anterior menos peso), fiabilidad de la fuente
- verificacion mediante LLM: verificador de los hechos de la noticia
- recalibracio de confiança: 


--- Finalment també hi ha una part de verificador, on donat el text redactat pels nostres periodistes o els extrets d'altres fonts externes ens donen un resum de les mètriques:
- Llegibilitat
- Cobertura
- Objectivitat
...

Fase 2: ecosistema de grafos y sistema de recomendacion
--> basado en usuarios-comunidad
--> similitud de contenido
--> retroalimentacion cada vez que un usuario lee una nueva notícia
--> recomendaciones en tiempo real
--> afinidad con los gustos más novedosos
--> motor de tendencias basandose en notícias 
--> recomendaciones explicativas y que permiten 

Fase 3: ponerlo todo en una App movil de tal manera que 
los usuarios similar a una app tipo netflix en la cual también se puedan ver grafos. 



es muy importante que durante todo el proceso se vea un ejemplo de tal manera que se pueda seguir y entender bien todo el proceso