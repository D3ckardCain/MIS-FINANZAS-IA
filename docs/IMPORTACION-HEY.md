# Hey: pagos efectivos y pagarés observados

La aplicación prepara el plan de un PDF textual del formato mensual admitido. La confirmación incorpora **una cuenta operativa de efectivo** con sus pagos, y conserva pagarés, resumen de inversiones y propuestas de renovación como evidencia fechada dentro del plan aceptado. Todavía no crea una cartera contable de contratos ni un total patrimonial confirmado.

## Flujo

1. Subir o abrir el documento. Si está protegido, introducir la contraseña para procesar su lectura documental y volver a indicarla en **Desbloquear plan** para releer el original financiero.
2. Revisar el plan, los pagos y las observaciones de pagarés. Si falta la moneda publicada, acreditar expresamente MXN; la revisión no puede sustituir una moneda extranjera o contradictoria.
3. Confirmar únicamente cuando no existan bloqueos. El original, su revisión y el estado del libro se verifican de nuevo antes de guardar.

La contraseña solo permanece en memoria durante la revisión; no se guarda en el plan, base de datos o historial. Se elimina al abandonar la vista, abrir otro documento o confirmar; recargar requiere volver a indicarla. El original cifrado permanece intacto. La moneda revisada sí se conserva en el plan confirmado para ese documento.

## Separación de importes

| Evidencia | Tratamiento |
| --- | --- |
| Devolución de principal | Aportación a efectivo; no es ganancia ni capital externo acreditado |
| Apertura de pagaré | Reducción de efectivo; origen/destino contable pendientes |
| Interés pagado | Ingreso bruto desde su fila, una sola vez |
| ISR pagado | Retención desde su fila, incluida una fila con cero explícito |
| Interés neto del resumen | Control de bruto menos retención; no genera otro cobro |
| Devengo incluido en saldo de inversiones | Observación, sin sumarlo de nuevo como interés cobrado |
| Condiciones y neto al vencimiento | Observación contractual fechada; proyecciones distintas de pagos efectivos |
| Total Portafolio / Total Vigentes | Controles documentales distintos, sin crear cuentas o movimientos adicionales |
| Apertura/cierre operativo | Anclas del período, sin aportaciones mensuales ficticias |

Las dos pestañas no duplican el efectivo. La identidad por documento, página y línea conserva tres categorías distintas aunque compartan folio de contrato. Tasas, GAT, plazo y fechas se guardan como condiciones históricas, sin aplicar ofertas actuales o calcular tasas fiscales desde un cargo aislado.

## Reinversión pendiente

El lector propone renovación cuando existen cuatro filas compatibles de la misma fecha: devolución de principal, interés, ISR y apertura de otro contrato por el neto. La propuesta conserva sus cuatro localizadores y `needs_review=True`.

Confirmar el efectivo **no aprueba la reinversión**: no genera otra ganancia, capital externo, transferencia propia o vínculo contractual contable. La consulta muestra la propuesta por separado. Quedan pendientes su revisión y la cartera histórica de contratos; las observaciones mensuales repetidas no se suman como nuevas inversiones.

## Controles y límites

- Se exigen ambas lecturas específicas y conciliación completa de efectivo y pagarés. Una diferencia de proyección bloquea el lote aunque el efectivo cuadre; no se descarta la diferencia ni se confirma solo la vista operativa.
- Se contrastan saldo por movimiento, abonos/cargos, cierre, ISR y neto normalizados, además de contratos, vencimientos, aperturas y totales documentales del lector.
- Fechas, sentido de columnas, referencias por categoría y conceptos deben ser compatibles. No se reordenan filas ni se inventan ajustes. Comisiones operativas no nulas, pagos parciales, conceptos adicionales y referencias ambiguas requieren adaptación.
- Períodos superpuestos o saldos contiguos incompatibles bloquean. Se admiten meses fuera de orden; los huecos permanecen visibles. Reintentos no duplican y los fallos revierten documento, aprobación, movimientos y cobertura en una transacción.
- El libro muestra el cierre operativo por fecha y los intereses/retenciones de períodos confirmados. No representa un saldo actual de mercado ni incorpora el valor de los pagarés como otro saldo confirmado.

Faltan cartera contable de pagarés, reinversión confirmada, enlaces entre instituciones, correcciones y confirmación financiera desde imágenes. El OCR local conserva evidencia revisable. Una retención no determina el impuesto anual.

Procesamiento local y sin conexión después de instalar las dependencias existentes, sin APIs o pagos obligatorios nuevos. Pruebas ficticias; la muestra real solo se usa para verificar el bloqueo de diferencias documentales, sin confirmar movimientos personales.
