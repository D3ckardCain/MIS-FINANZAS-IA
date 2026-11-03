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

### Verificación completa de persistencia

- [GitHub Actions: 37 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/41577502496).
- Entorno: Ubuntu 24.04, Python 3.12.3, SQLite 3.45.1.
- Confirmados cierre/reapertura de archivos, copia a otro archivo y dos conexiones con control de versión.
- Resultado vinculado al commit 4f741507c18a5313d604d38019d863077dd6fe2a.
- Actualizada la acción checkout a v7 tras el aviso de deprecación de Node 20 observado en la primera ejecución.
- Finalizado el incremento de persistencia. Continúan pendientes los límites expresados en el manual; no se incorporaron registros reales.

## 2026-11-03 — Dos lectores y organización del panel

- Registrada la decisión del titular: categorías separadas, instituciones dentro de ellas, vistas de débito e inversiones por institución y resumen global independiente.
- Implementados dos lectores independientes de Openbank con resumen, filas, página/línea, controles contables y propuestas de transferencias.
- Contrastadas extracción por columnas y extracción lógica para conservar descripciones partidas.
- Lectura PDF local mediante pypdf 6.10.0, licencia BSD-3-Clause según metadatos del paquete; biblioteca externa solo para este extra.
- Añadidas 15 pruebas sintéticas del lector, incluida lectura de PDF generado en memoria; aprobadas localmente.
- Vista previa exclusivamente: no se aprobó ni guardó ningún movimiento financiero real.
- Pendientes interfaz, revisión de identidad y confirmación transaccional de importación.

### Verificación completa de los dos lectores

- [Suite completa: 52 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/41579036184).
- Commit probado: 42934e73c5075d5ed4bc92da5d7edbe748600717.
- Instalación del extra PDF verificada en entorno virtual; generación y lectura del PDF sintético sin archivos financieros privados.
- Cerrado el incremento de lectura y vista previa. La estructura del panel está documentada en PANEL.md; la interfaz y la confirmación de importación siguen pendientes.
