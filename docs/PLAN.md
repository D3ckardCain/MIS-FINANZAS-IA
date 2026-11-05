# Plan y pendientes

Orden inicial revisable. Cada etapa se entrega con manual y criterios verificables.

| Orden | Incremento | Estado | Criterio de aceptación |
| --- | --- | --- | --- |
| 1 | Reglas y núcleo de movimientos | Implementado, pruebas sintéticas | Transferencias y reinversiones no duplican capital externo ni ingreso; pendientes visibles |
| 2 | Persistencia local y evidencia | Implementado; 37 pruebas aprobadas en CI | SQLite, transacciones atómicas, identidad documental, revisión, correcciones trazables, copia y restauración verificadas |
| 3 | Openbank: lectores débito e inversiones, vista previa | Vista previa implementada; 52 pruebas aprobadas en CI | Estado leído por sus fechas internas, operación separada de ahorro, vista previa y conciliación documental; confirmar antes de incorporar |
| 4 | Tasas históricas y contratos | Pendiente | Vigencias, topes, condiciones, plazos y redondeo; cobro real separado de estimación |
| 5 | Más instituciones y conciliación | 26 entradas documentales con PDF/imagen; conciliación PDF optativa de BanCoppel, CETESdirecto, DiDi y Doopla implementada; mapeo económico pendiente | Manual por formato, contrapartidas parciales/múltiples, faltantes, retenciones documentadas |
| 6 | Interfaz local profesional | Jerarquía de categorías/instituciones y dos vistas aprobada; interfaz pendiente | Institución/producto y resumen separados, evidencia accesible, pendientes claros, estilo GitHub y estado offline |
| 7 | Cripto y acciones | Lectores iniciales de capturas BingX/Pionex implementados; contabilidad e interfaz pendientes | Historial desde primera operación, archivos, transferencias propias, bots y derivados sin duplicación |
| 8 | SAT y constancias | Pendiente | Reglas oficiales versionadas por ejercicio, retenciones conciliadas y alcance fiscal revisado |
| 9 | Comparador de inversiones | Pendiente | Ofertas verificadas, fuentes y fechas, riesgo/liquidez/fiscalidad, disponibilidad gratuita comprobada |

## Problemas abiertos

1. **Persistencia:** almacenamiento SQLite y reapertura/copia en disco verificados; falta integrar el flujo visual de revisión antes de guardar registros reales.
2. **Identidad de importación:** huella documental y referencia estable implementadas; cada adaptador debe obtener referencias fiables y dejar pendiente cualquier identidad ambigua.
3. **Historia incompleta:** registrar períodos realmente cubiertos y documentos faltantes; no inferir faltantes solo por nombre de archivo o fecha del correo.
4. **Vínculos complejos:** separar conciliación por tramos, tránsito, comisiones y conversión de monedas.
5. **Semántica institucional:** algunos resúmenes mezclan capital/interés, presentan neto con ISR aparte o agrupan días. Requieren adaptadores y revisión, no fórmula universal.
6. **Tasas:** hacen falta condiciones históricas y reglas contractuales; no sustituirlas por promociones actuales.
7. **Fiscalidad:** clasificar cada retención según producto y ejercicio; las constancias anuales concilian, no añaden retenciones duplicadas.

Las discrepancias particulares y el inventario de documentos del titular se conservarán en almacenamiento privado; aquí se registran únicamente problemas generales.
