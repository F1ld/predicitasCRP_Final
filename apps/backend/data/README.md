# Compatibilidad histórica, no ubicación canónica

Los dos CSV de esta carpeta se conservan sin cambiar bytes/fechas, para no romper
consumidores externos desconocidos. Desde fase 3 las muestras canónicas están en
[`data/samples/importacion/`](../../../data/samples/importacion/).

No regenerar ni sincronizar automáticamente estas copias. El exportador exige un
destino nuevo explícito en runtime o almacenamiento externo autorizado. Las imágenes
Docker ya no incluyen esta carpeta; ninguna ruta operativa de API la necesita.

Su retirada no forma parte de esta entrega: requiere revisión de consumidores y respaldo.
