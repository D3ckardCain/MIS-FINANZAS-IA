# Plan y pendientes

## Prioridad vigente — aclaración del titular, 5 de noviembre de 2026

Los estados compartidos son muestras para construir y probar el software. No se condiciona el desarrollo a completar estados faltantes ni a elaborar contabilidad personal en el chat. El orden anterior queda como histórico y se antepone el flujo de la aplicación.

1. **Carga y consulta local:** implementada la bandeja PDF/imagen, identificación, dos vistas, originales, duplicados y revisión documental.
2. **Importación financiera:** Openbank, Mifel, BanCoppel y DiDi PDF conectados al ledger con plan y confirmación atómica, traspasos internos, control de solapamientos y cierres. Extender esta integración a cada institución; transferencias externas/reinversiones/correcciones pendientes.
3. **Panel financiero:** resúmenes y evolución por institución/producto sobre movimientos confirmados, con cobertura y diferencias visibles.
4. **Cripto, constancias y datos complementarios:** completar sus flujos visuales y contabilidad específica; incorporar nuevos archivos cuando estén disponibles.
5. **Fiscalidad anual y comparación de inversiones:** implementar después sobre información validada y fuentes oficiales históricas.

La aplicación guarda resultados documentales; Openbank, Mifel, BanCoppel y DiDi PDF permiten confirmar sus movimientos financieros. Las demás salidas todavía no se transforman en movimientos financieros confirmados. Los PDF reales solo se utilizan para validar formatos.

## Orden anterior — conservado como historial

Este orden fue sustituido por la aclaración anterior.

| Prioridad | Trabajo | Estado | Resultado esperado |
| --- | --- | --- | --- |
| 1 | Plata: lector específico de débito y ahorro | Implementado para formato conocido; revisión pendiente | Separar agregado y detalle, cashback, transferencias propias, rendimientos, retenciones y registros posteriores al corte; pruebas y manual |
| 2 | Conciliación y cobertura por institución | Pendiente después de Plata | Revisar diferencias y completar estados faltantes, preservando evidencia y sin ajustes ficticios |
| 3 | Criptomonedas y wallets | Pendiente después de conciliación | Validar capturas reales BingX/Pionex e incorporar fuentes identificadas de wallets, desde la primera operación |
| 4 | Aplicación e importación revisada | Pendiente después de cripto | Panel estilo GitHub, categorías e instituciones separadas y confirmación transaccional para incorporar datos a la base |
| 5 | Fiscalidad anual y comparación de inversiones | Etapa posterior | Reglas oficiales históricas, retenciones conciliadas y ofertas verificadas, respetando operación sin pagos obligatorios |

No se han importado movimientos reales. La existencia de lectores, revisión documental o pruebas aprobadas no equivale a importación, conciliación completa ni aplicación visual terminada.

## Base implementada y etapas generales

Cada etapa se entrega con manual y criterios verificables. Las cifras de pruebas de los incrementos antiguos son hitos históricos, no el total actual.

| Orden | Incremento | Estado | Criterio de aceptación |
| --- | --- | --- | --- |
| 1 | Reglas y núcleo de movimientos | Implementado, pruebas sintéticas | Transferencias y reinversiones no duplican capital externo ni ingreso; pendientes visibles |
| 2 | Persistencia local y evidencia | Implementado; 37 pruebas aprobadas en CI | SQLite, transacciones atómicas, identidad documental, revisión, correcciones trazables, copia y restauración verificadas |
| 3 | Openbank: lectores débito e inversiones, vista previa | Vista previa implementada; 52 pruebas aprobadas en CI | Estado leído por sus fechas internas, operación separada de ahorro, vista previa y conciliación documental; confirmar antes de incorporar |
| 4 | Tasas históricas y contratos | Pendiente | Vigencias, topes, condiciones, plazos y redondeo; cobro real separado de estimación |
| 5 | Más instituciones y conciliación | 30 entradas documentales PDF/imagen, más dos lectores cripto (15 instituciones, 32 entradas); conciliación PDF optativa de BanCoppel, CETESdirecto, DiDi, Doopla, Fintual, Alpaca, Hey, Kapital, Mifel y SuperTasas implementada; Fondeadora con revisión operativa y traspasos; Nu con resumen/cambios por Cajita y cierres individuales pendientes; YoTePresto con controles de resumen, efectivo y cartera; Plata con dos productos, resumen agregado y control temporal | Manual por formato, contrapartidas parciales/múltiples, faltantes, retenciones documentadas |
| 6 | Interfaz local profesional | Bandeja y libro financiero Openbank/Mifel/BanCoppel/DiDi implementados; integración de otras instituciones y resumen patrimonial pendientes | Institución/producto y resumen separados, evidencia accesible, pendientes claros, estilo GitHub y estado offline |
| 7 | Cripto y acciones | Capturas BingX/Pionex y PDF/imagen Alpaca disponibles; contabilidad e interfaz pendientes | Historial desde primera operación, archivos, transferencias propias, bots y derivados sin duplicación |
| 8 | SAT y constancias | Constancias documentales Nu/Openbank disponibles; motor de declaración pendiente | Reglas oficiales versionadas por ejercicio, retenciones conciliadas y alcance fiscal revisado |
| 9 | Comparador de inversiones | Pendiente | Ofertas verificadas, fuentes y fechas, riesgo/liquidez/fiscalidad, disponibilidad gratuita comprobada |

## Problemas abiertos

1. **Persistencia:** almacenamiento SQLite y reapertura/copia en disco verificados; bandeja y revisión documental visual implementadas; confirmación financiera Openbank/Mifel/BanCoppel/DiDi conectada; faltan las demás instituciones.
2. **Identidad de importación:** huella documental y referencia estable implementadas; cada adaptador debe obtener referencias fiables y dejar pendiente cualquier identidad ambigua.
3. **Historia incompleta:** registrar períodos realmente cubiertos y documentos faltantes; no inferir faltantes solo por nombre de archivo o fecha del correo.
4. **Vínculos complejos:** separar conciliación por tramos, tránsito, comisiones y conversión de monedas.
5. **Semántica institucional:** algunos resúmenes mezclan capital/interés, presentan neto con ISR aparte o agrupan días. Requieren adaptadores y revisión, no fórmula universal.
6. **Tasas:** hacen falta condiciones históricas y reglas contractuales; no sustituirlas por promociones actuales.
7. **Fiscalidad:** clasificar cada retención según producto y ejercicio; las constancias anuales concilian, no añaden retenciones duplicadas.

Las discrepancias particulares y el inventario de documentos del titular se conservarán en almacenamiento privado; aquí se registran únicamente problemas generales.
