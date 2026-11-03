# Registro de avances

## 2026-11-03 — Primera base funcional

- Consolidado el alcance de inversiones, reglas de capital, reinversión, cashback, evidencia e ISR.
- Documentadas alternativas, límites y etapas; arquitectura inicial local sin dependencias de pago.
- Implementado núcleo en memoria con Decimal y movimientos inmutables.
- Incluidos 16 casos de prueba sintéticos: transferencias, contraparte faltante/incompatible, reinversión, cashback, importación repetida por ID, conflicto, retención desconocida/cero, origen desconocido, saldo inicial, unidades, fechas efectivas, precisión, validaciones y vínculo reutilizado.
- Verificación previa a publicación: 16 pruebas aprobadas mediante unittest sobre los mismos contenidos del repositorio, cargados en memoria.
- No se importaron estados ni Excel. No hay base de datos, interfaz ni motor fiscal implementados.
- Siguiente incremento: persistencia local y trazabilidad documental, antes de incorporar datos reales.
