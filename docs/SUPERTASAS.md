# SuperTasas: efectivo remunerado e inversiones a plazo

El lector específico separa movimientos pagados y posiciones a plazo proyectadas en dos vistas de la misma cuenta. Ambas comparten documento/identidad; sus totales no se suman como cuentas independientes.

```bash
python -m finanzas.readers estado.pdf --institution supertasas --lane debit --reconcile
python -m finanzas.readers estado.pdf --institution supertasas --lane investments --reconcile
```

Para PDF protegido, la API admite `SuperTasasReader(lane).read_pdf(content, password=...)`. La contraseña debe suministrarse explícitamente y en memoria; no se adivina, registra o añade a la vista previa. La consola general no recibe contraseñas como argumentos. Puede usarse una copia legible o la API con entrada privada. Los originales permanecen intactos. Las pruebas emplean una contraseña ficticia.

## Qué separa

- `summary`: efectivo inicial/final, abonos, cargos, interés bruto/neto y retención de la cuenta a la vista, tasa publicada, saldo medio y comisiones de ambas secciones.
- `rows`: movimientos con signo, concepto original, referencia, fecha interna y página/línea. Depósito/retiro, apertura a plazo, devolución de principal, interés pagado a plazo y rendimiento de cuenta son categorías distintas.
- `contracts`: posiciones publicadas con capital, apertura, plazo, vencimiento, tasa, GAT y proyecciones de bruto/retención/neto. Son observaciones mensuales de condiciones, no nuevos cobros cada mes.

La vista débito muestra todas las filas de efectivo. La de inversiones muestra aperturas, devoluciones de principal e intereses, conservando `rows` completo como contexto. Se incluyen los intereses a la vista, pero no se vuelve a sumar el total común de cuenta.

Los abonos del resumen ya incluyen los intereses de la tabla: no se añade de nuevo el rendimiento. Un pago de capital no es una ganancia. Un concepto que diga exento se conserva literalmente, sin concluir que determina la declaración o todas las inversiones del titular. Retención pagada y retención proyectada permanecen separadas.

## Controles y casos documentales

`detail_reconciled` comprueba efectivo, saldos por movimiento, abonos/cargos, período y mapeo de conceptos. `reconciled` exige además ausencia de incidencias en las posiciones. `ready_to_import=False` siempre: no se guardan movimientos reales.

Un saldo inicial sin cifra queda `None`, distinto de cero, y bloquea la conciliación completa. La continuidad de cobertura omite esos enlaces como no verificables. Los saldos negativos entre paréntesis se conservan con signo; no se reordenan filas ni se fabrican ajustes para cuadrarlos.

Se reconocen importes impresos con cero, uno o dos decimales, incluido `.00`, manteniendo precisión Decimal. Las etiquetas de columna están centradas; el sentido de cada importe se obtiene de su posición, sin reconstruirlo a partir del saldo. Un campo o encabezado ambiguo se rechaza.

Las dos formas de «capital al vencimiento» observadas se conservan: principal solo o principal más neto proyectado. La primera no se fuerza a incluir nuevamente el rendimiento total: puede existir otra modalidad de pago, que requiere sus condiciones. Un importe que no coincida con esas formas se señala sin corregirlo.

Una posición publicada como vigente cuyo vencimiento ya llegó al corte se mantiene visible y señala la inconsistencia. No se borra automáticamente ni se cuenta como inversión vigente confirmada.

## Revisión entre documentos

`review_supertasas(previews)` deduplica huellas binarias, exige una cuenta y rechaza versiones solapadas. La `snapshot_key` deriva de cuenta, fechas y principal: identifica una observación comparable, no un número de contrato económico emitido por la institución. Cambios de condiciones se señalan; variaciones de GAT permanecen como datos publicados de cada mes.

Se proponen correspondencias de apertura o devolución de principal únicamente si hay una posición única con fecha y capital compatibles. El estado es `candidate_requires_review`. No demuestra reinversión, procedencia externa, pago de todo el rendimiento o exención. Los cupones periódicos permanecen como pagos observados; no se les asigna automáticamente un contrato o calendario por coincidencia de importe.

`review_coverage` verifica períodos y saldos reportados, sin completar historia con proyecciones ni Excel. Se conservan fechas de operación publicadas aunque el orden o los saldos sean problemáticos.

PDF y OCR operan localmente con las dependencias existentes. Las imágenes conservan evidencia OCR revisable, sin heredar automáticamente los controles estructurados del PDF. No hay APIs de pago, conexión bancaria, cálculo SAT ni importación automática. Documentos, contraseñas e informes financieros del titular no se publican en GitHub.
