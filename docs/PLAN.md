# Plan y pendientes

## Prioridad vigente — aclaración del titular, 5 de noviembre de 2026

Los estados compartidos son muestras para construir y probar el software. No se condiciona el desarrollo a completar estados faltantes ni a elaborar contabilidad personal en el chat. El orden anterior queda como histórico y se antepone el flujo de la aplicación.

1. **Carga y consulta local:** implementada la bandeja PDF/imagen, identificación, dos vistas, originales, duplicados y revisión documental.
2. **Importación financiera:** Openbank, Mifel, BanCoppel, DiDi y Plata PDF conectados al ledger con plan y confirmación atómica, traspasos internos, control de solapamientos y cierres. Extender esta integración a cada institución; transferencias externas/reinversiones/correcciones pendientes.
3. **Panel financiero:** resumen por cuenta y evolución por período documental implementados, con filtro, componentes, cobertura, diferencias y acceso al original. Valuación patrimonial y rentabilidad porcentual pendientes.
4. **Cripto, constancias y datos complementarios:** completar sus flujos visuales y contabilidad específica; incorporar nuevos archivos cuando estén disponibles.
5. **Fiscalidad anual y comparación de inversiones:** implementar después sobre información validada y fuentes oficiales históricas.

La aplicación guarda resultados documentales; Openbank, Mifel, BanCoppel, DiDi y Plata PDF permiten confirmar sus movimientos financieros. Fondeadora permite confirmar estados operativos completos, con revisión explícita de moneda cuando falta; reportes sin saldo y posiciones de inversión permanecen pendientes. SuperTasas confirma efectivo conciliado y conserva posiciones a plazo como observaciones fechadas; pagos a plazo sin desglose bruto/retención permanecen bloqueados. Hey confirma pagos de efectivo y guarda pagarés/propuestas de renovación como observaciones pendientes; una diferencia contractual bloquea el lote completo. Kapital confirma pagos de ambos formatos, timbrado/devolución y pagarés observados; cartera contractual y equivalencias entre identificadores pendientes. Doopla confirma efectivo por componentes y conserva cartera/atrasos observados, con vigencia del anexo y retención desconocida/parcial controladas. Fintual confirma efectivo del portafolio y conserva valuación e ISR informativo como observaciones; contabilidad de unidades/costo y atribución fiscal pendientes. Fintual USD confirma efectivo USD, dividendos e impuesto extranjero, con acciones/resultados observados y fiscalidad mexicana pendiente. YoTePresto confirma efectivo con apertura acreditada, pagos múltiples revisados, cancelaciones enlazadas y continuidad de saldos/acumulados por préstamo; no reparte agregados ni duplica originales. CETESdirecto confirma efectivo liquidado e ISR desde filas, conservando cobros sin asignación de capital/interés y resultados observados; desglose por operación y títulos/costo pendientes. Nu confirma Cuenta/Cajitas agregadas/garantía con aperturas y distribución de interés/ISR acreditadas, fecha de reconocimiento al cierre y traspasos enlazados; saldos individuales y contratos congelados permanecen documentales. Las demás salidas todavía no se transforman en movimientos financieros confirmados. Los PDF reales solo se utilizan para validar formatos.

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
| 5 | Más instituciones y conciliación | 30 entradas documentales PDF/imagen, más dos lectores cripto (15 perfiles de formato, 32 entradas); conciliación PDF optativa de BanCoppel, CETESdirecto, DiDi, Doopla, Fintual, Alpaca, Hey, Kapital, Mifel y SuperTasas implementada; Fondeadora con revisión operativa y traspasos; Nu con resumen/cambios por Cajita y cierres individuales pendientes; YoTePresto con controles de resumen, efectivo y cartera; Plata con dos productos, resumen agregado y control temporal | Manual por formato, contrapartidas parciales/múltiples, faltantes, retenciones documentadas |
| 6 | Interfaz local profesional | Bandeja y libro financiero Openbank/Mifel/BanCoppel/DiDi/Plata y Fondeadora operativa implementados; SuperTasas con efectivo y observaciones a plazo, Hey/Kapital con pagos y pagarés observados, Doopla con efectivo por componentes y cartera observada, Fintual con efectivo y fondos observados, Fintual con portafolio USD y posiciones observadas; integración de otras instituciones y resumen patrimonial pendientes | Institución/producto y resumen separados, evidencia accesible, pendientes claros, estilo GitHub y estado offline |
| 7 | Cripto y acciones | Capturas BingX/Pionex y PDF/imagen Alpaca disponibles; contabilidad e interfaz pendientes | Historial desde primera operación, archivos, transferencias propias, bots y derivados sin duplicación |
| 8 | SAT y constancias | Constancias documentales Nu/Openbank disponibles; motor de declaración pendiente | Reglas oficiales versionadas por ejercicio, retenciones conciliadas y alcance fiscal revisado |
| 9 | Comparador de inversiones | Pendiente | Ofertas verificadas, fuentes y fechas, riesgo/liquidez/fiscalidad, disponibilidad gratuita comprobada |

## Problemas abiertos

1. **Persistencia:** almacenamiento SQLite y reapertura/copia en disco verificados; bandeja y revisión documental visual implementadas; confirmación financiera Openbank/Mifel/BanCoppel/DiDi/Plata y Fondeadora operativa conectada; SuperTasas con efectivo y observaciones a plazo, Hey/Kapital con pagos y pagarés observados, Doopla con efectivo por componentes y cartera observada, Fintual con efectivo y fondos observados, Fintual con portafolio USD y posiciones observadas; faltan las demás instituciones.
2. **Identidad de importación:** huella documental y referencia estable implementadas; cada adaptador debe obtener referencias fiables y dejar pendiente cualquier identidad ambigua.
3. **Historia incompleta:** registrar períodos realmente cubiertos y documentos faltantes; no inferir faltantes solo por nombre de archivo o fecha del correo.
4. **Vínculos complejos:** separar conciliación por tramos, tránsito, comisiones y conversión de monedas.
5. **Semántica institucional:** algunos resúmenes mezclan capital/interés, presentan neto con ISR aparte o agrupan días. Requieren adaptadores y revisión, no fórmula universal.
6. **Tasas:** hacen falta condiciones históricas y reglas contractuales; no sustituirlas por promociones actuales.
7. **Fiscalidad:** clasificar cada retención según producto y ejercicio; las constancias anuales concilian, no añaden retenciones duplicadas.

Las discrepancias particulares y el inventario de documentos del titular se conservarán en almacenamiento privado; aquí se registran únicamente problemas generales.

Identidad corregida por el titular: Fintual MXN y Fintual USD pertenecen a Fintual. El perfil Alpaca queda como custodio/formato técnico, fuera del catálogo de instituciones. Cada portafolio conserva unidad, cuenta y movimientos separados.

YoTePresto: candidato de apertura no publicado permanece bloqueado hasta revisión expresa del usuario o enlace a un cierre contiguo confirmado compatible. No se requiere completar archivos personales para desarrollar los casos admitidos con pruebas ficticias.

YoTePresto: pagos múltiples y cancelaciones de préstamo, pago, comisión y retención implementados, con selección de originales, revisiones por operación y controles históricos. Las ausencias/contradicciones de evidencia bloquean el documento y no se resuelven inventando datos.


Nu: integración financiera de agregados implementada con revisión explícita por producto; no asigna globales automáticamente ni deduce pagos diarios. Faltan cierres/rendimientos por Cajita individual cuando no están publicados, contratos congelados, cashback y confirmación financiera desde imágenes.
