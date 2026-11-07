# YoTePresto: pagos múltiples y cancelaciones trazables

La aplicación confirma el efectivo de la plataforma con sus componentes y controles por préstamo. Cartera, tasas y atrasos se conservan como observaciones, sin crear otra cuenta bancaria, duplicar acumulados o registrar una pérdida por atraso.

## Flujo

1. Subir o abrir el PDF. Si está protegido, introducir contraseña para procesarlo y para **Desbloquear plan**. Solo se usa en memoria; no queda en la base, el plan o el historial.
2. Acreditar la apertura de efectivo. El candidato aritmético no es una cifra publicada: comprobarlo con fuentes propias, marcar la declaración y aplicar. Un cierre contiguo confirmado compatible puede acreditar el enlace. El saldo global no sustituye a la apertura de efectivo.
3. Si aparecen operaciones sin desglose, completar **Desglose de operaciones** y elegir el préstamo acreditado de cada pago. Revisar con fuentes propias los cinco componentes de pago o los dos de retención. No se completan por porcentaje ni se acepta un guion como cero.
4. Para cada cancelación, elegir su original compatible. Si cancela un préstamo, acreditar también el ID del préstamo. Si no existe original, incorporar su documento; si hay varios candidatos, elegir expresamente uno. Marcar la verificación y pulsar **Aplicar revisión de operaciones**.
5. Revisar el plan listo y confirmar. El original, versión, decisiones y estado financiero se comprueban otra vez. Apertura, moneda y desgloses pueden revisarse por separado; las decisiones válidas se conservan en el plan pendiente.

La revisión documenta una declaración del usuario sobre sus fuentes; no afirma que el PDF publicara ese desglose ni que la app inspeccionara automáticamente esas fuentes. La app verifica importes, referencias, saldos, acumulados, signos y coherencia. Las decisiones quedan ligadas a documento, revisión y huella del plan, y no se aplican a otros documentos.

## Pagos y retenciones

| Componente | Tratamiento |
| --- | --- |
| Principal recuperado | Aportación a efectivo con origen pendiente; no interés ni capital externo acreditado |
| Interés ordinario / moratorio | Dos componentes de interés cobrado |
| IVA ordinario / moratorio | Dos componentes de IVA recibido, separados del interés |
| Retención ISR / IVA | ISR retenido e IVA pagado por su fecha publicada |
| Comisión con IVA | Cargo una sola vez; el resumen no genera otro |
| Fondeo / retiro / préstamo | Aportación o reducción operativa con origen/contrapartida pendientes |

Un pago único puede desglosarse sin intervención cuando su préstamo preexistente, principal por cambio de saldo y componentes publicados acreditan exactamente el total. Con pagos o retenciones múltiples, se revisan los componentes por fila cuando no están publicados. Cada suma debe coincidir con su operación y con los totales mensuales, y el principal neto debe coincidir por préstamo. Para un préstamo abierto en el mes con saldo inicial cero se coteja el capital prestado explícito; no se obtiene de una valuación. La revisión no habilita ajustes para hacer cuadrar cifras contradictorias.

El importe de «Pagos recibidos» se conserva y se contrasta tanto con pagos brutos como con el neto de cancelaciones. La app muestra ambas cifras y la base que coincide; no sustituye la cifra impresa ni vuelve a registrar la ganancia publicada como ingreso.

## Cancelaciones

| Cancelación | Reverso registrado |
| --- | --- |
| Préstamo | Aportación de retorno a efectivo, sin nueva ganancia o capital externo |
| Pago | Principal, interés ordinario/moratorio e IVA exactamente contrarios a los componentes originales |
| Comisión | Devolución de comisión, sin ingreso por interés |
| Retención | Devolución del ISR e IVA originales, separados de ganancias y aportaciones |

El original puede estar en el mismo documento o en un mes confirmado anterior. Debe coincidir en cuenta, referencia, concepto compatible, importe opuesto y fecha no posterior a la cancelación. Estos controles generan candidatos; no convierten fecha/importe en un identificador económico único. La selección explícita resuelve cuál original se declara cancelado.

Cada reverso conserva el documento/evento original y los identificadores de sus componentes. No se edita ni borra el original. Un original no se puede cancelar dos veces, incluso en archivos distintos. Si el importe del original fue corregido en el libro, su versión congelada no basta para revertir el importe antiguo: la revisión queda bloqueada hasta resolver la evidencia.

Una cancelación de préstamo exige acreditar su ID, sin confundir el retorno con principal pagado por el prestatario. No se infiere reinversión por volver a prestar el efectivo recuperado.

## Consulta y conciliación histórica

Interés, IVA, ISR y comisiones se muestran netos de sus reversos/devoluciones. La devolución de ISR no es ingreso ni capital externo; puede dar una retención neta negativa en el mes de devolución. Esto no determina el impuesto anual.

Entre meses contiguos se cotejan efectivo, saldo global y saldos de préstamos compartidos. Los cambios de acumulados de principal, interés e IVA se contrastan con los pagos y cancelaciones clasificados del mes, también al incorporar meses fuera de orden. Una disminución se conserva; si no coincide con reversos documentados, bloquea en vez de inventar una pérdida o devolución.

Los acumulados no generan cobros: sirven de control. Los meses no contiguos no se enlazan como si no hubiera huecos. Las posiciones siguen siendo observaciones por fecha; no se reconstruye un calendario o vencimiento contractual supuesto.

## Controles de confirmación

- Resumen, efectivo, cartera, columnas, signos, fechas y componentes deben conciliar. Revisar una apertura no elimina otras alertas.
- Un período sin movimientos requiere tabla y declaración explícita de ausencia, flujos publicados cero y apertura acreditada; no se inventan operaciones para llenar el mes. Una tabla ausente no equivale a vacía.
- Moneda MXN acreditada o revisada por documento. Moneda extranjera/contradictoria no puede sobrescribirse. No se desplazan fechas al lunes o al corte.
- Revisiones de otro archivo, filas ajenas, valores negativos/no finitos, préstamos incompatibles o desgloses que no suman quedan rechazados. No se eliminan pagos iguales legítimos por coincidencia de importe o referencia.
- Solapamientos y saldos contiguos incompatibles bloquean. La transacción abarca aprobación, movimientos, eventos, enlaces de cancelación y cobertura; un fallo revierte todo. Reabrir o reintentar no duplica.

El libro muestra efectivo y componentes confirmados, no un patrimonio total inventado. Este flujo no calcula declaración anual, no asigna titularidad externa ni aprueba reinversión por coincidencia. Las imágenes siguen aportando evidencia OCR revisable; la confirmación financiera descrita corresponde al PDF textual reconocido. Un documento incompleto o un formato desconocido permanece bloqueado.

Procesamiento local/offline con dependencias existentes, sin APIs, servicios o pagos nuevos. Pruebas ficticias y sin confirmar contabilidad personal en el chat. Fintual conserva su identidad MXN/USD.
