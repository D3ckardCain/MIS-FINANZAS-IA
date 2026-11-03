# Registro de avances

## 2026-11-03 — Primera base funcional

- Consolidado el alcance de inversiones, reglas de capital, reinversión, cashback, evidencia e ISR.
- Documentadas alternativas, límites y etapas; arquitectura inicial local sin dependencias de pago.
- Implementado núcleo en memoria con Decimal y movimientos inmutables.
- Incluidos 16 casos de prueba sintéticos: transferencias, contraparte faltante/incompatible, reinversión, cashback, importación repetida por ID, conflicto, retención desconocida/cero, origen desconocido, saldo inicial, unidades, fechas efectivas, precisión, validaciones y vínculo reutilizado.
- Verificación previa a publicación: 16 pruebas aprobadas mediante unittest sobre los mismos contenidos del repositorio, cargados en memoria.
- No se importaron estados ni Excel. No hay base de datos, interfaz ni motor fiscal implementados.
- Siguiente incremento: persistencia local y trazabilidad documental, antes de incorporar datos reales.

## 2026-11-03 — Persistencia y evidencia

- Implementado Store SQLite sin dependencias externas: documentos por huella SHA-256, decisiones de revisión, lotes atómicos, importes decimales exactos y múltiples evidencias.
- Correcciones explícitas con versión esperada, motivo e historia conservada; documento corregido no sustituye movimientos automáticamente.
- Implementadas copia consistente a destino vacío y recuperación de imagen SQLite.
- Añadidas pruebas de documentos solapados, conflictos, revisión, correcciones, recuperación y conexiones separadas.
- Verificación previa a publicación: 35 pruebas aprobadas y 2 omitidas por no disponer de escritura local. Las dos pruebas de archivo se ejecutarán mediante GitHub Actions.
- CI limitada a Ubuntu estándar en repositorio público, sin cachés ni artifacts; ejecución local independiente.
- No se importaron datos reales ni Excel. Siguiente módulo: vista previa del primer adaptador documental.
