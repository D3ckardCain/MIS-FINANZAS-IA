# Doopla: efectivo por componente y cartera observada

La aplicación prepara el plan del PDF textual del formato admitido. Confirmar incorpora **una cuenta de efectivo de la plataforma**, con cada componente de sus movimientos. La cartera de préstamos, el valor de cuenta y los atrasos permanecen como observaciones fechadas; no crean otra cuenta bancaria o un patrimonio contable total.

## Uso

1. Subir o abrir el documento. Para PDF protegido, introducir la contraseña al procesarlo y en **Desbloquear plan** para releer el original financiero. No se guarda en plan/base de datos y se elimina de la revisión al abandonar/confirmar.
2. Revisar movimientos, resumen observado, cartera y atrasos. Si no se publica moneda, acreditar MXN expresamente para ese documento. El símbolo dólar no basta y una moneda contradictoria no puede sobrescribirse.
3. Confirmar únicamente cuando no haya bloqueos. El original, revisión y estado del libro se comprueban otra vez; todos los componentes y cobertura se guardan en una transacción.

## Qué se registra

| Evidencia | Registro financiero |
| --- | --- |
| Principal de pago | Aportación a efectivo con origen pendiente; no interés o capital externo acreditado |
| Interés de pago | Interés bruto cobrado, una vez |
| IVA de pago | IVA recibido, separado de interés, principal e ISR |
| Depósito / retiro | Aportación / reducción con origen o contrapartida pendientes |
| Inversión / cancelación | Reducción / aportación de efectivo; importes brutos separados del neto del resumen |
| IVA ordinario / moratorio | IVA pagado, conservando su categoría y evidencia; no ISR o comisión |
| ISR de movimiento | Retención efectivamente publicada, sin cálculo anual supuesto |
| Comisión agrupada | Cargo único con IVA incluido; desglose del resumen como observación, sin cobrarlo otra vez |
| Recompensa | Otro ingreso, separado de capital, cashback e interés |
| Cartera y cobranza | Observación fechada, sin nuevo cobro acumulado ni pérdida automática por atraso |

Cada pago requiere cifras publicadas de principal, interés e IVA. Un guion queda desconocido y bloquea el desglose; no se sustituye por cero. Los componentes comparten la fila original y tienen identificadores distintos por documento/página/línea/componente. Pagos iguales legítimos se conservan, sin deduplicarlos por fecha, alias o importe.

## Retención ausente y cobertura parcial

Si el estado no publica ISR, no se genera un movimiento de retención cero. El libro conserva **desconocido** tanto en retención total como en interés neto de retención. Un cero publicado sí se conserva como evidencia explícita.

Si algunos meses publican retención y otros no, se muestra por separado la retención documentada con cobertura parcial; el total y el neto siguen desconocidos. Esta distinción no calcula ISR definitivo, exención, acreditamientos o declaración anual. Interés neto de retención tampoco equivale al resultado después de IVA y comisiones.

## Controles

- Se exige conciliación de las dos vistas, efectivo, componentes, valor de plataforma y cartera. Una sección correcta no compensa otra discrepante y no se confirma solo efectivo si el resto falla.
- El cierre normalizado, interés, IVA recibido, recompensas, comisión con IVA e ISR conocido deben coincidir con sus cifras publicadas. No se cambia el signo del IVA del resumen para hacer cuadrar resultados.
- Se conservan las fechas impresas aunque los movimientos se presenten agrupados y fuera de orden cronológico; no se desplazan cobros al corte o al lunes. Operaciones fuera del período, signos incorrectos y conceptos desconocidos bloquean.
- Se comprueba continuidad de efectivo y valor de plataforma en meses contiguos. Un anexo de cartera idéntico con movimientos de capital en el mes siguiente bloquea por vigencia pendiente, también al importar meses fuera de orden.
- Solapamientos bloqueados, huecos visibles y reintentos idempotentes. Un fallo revierte documento, aprobación, movimientos/componentes y cobertura, sin datos parciales.

## Alcance y límites

El libro muestra cierre de efectivo por fecha, interés bruto, retención con su cobertura, IVA recibido/pagado, recompensas y comisiones. El valor observado de cuenta incluye cartera y no se suma como un segundo saldo confirmado. Los datos acumulados de préstamos no generan otra vez ingreso mensual.

Quedan pendientes la cartera contable por préstamo, origen de fondos y contrapartidas, reinversión confirmada, tratamiento fiscal anual, correcciones e importación financiera desde imágenes. Atraso o cobranza no determina automáticamente una pérdida. El OCR local continúa disponible como evidencia revisable.

Procesamiento local y offline después de instalar las dependencias existentes. Sin servicios, APIs o pagos nuevos. Pruebas exclusivamente ficticias; los documentos del titular no se incorporan al repositorio ni se confirman como contabilidad personal.
