# Kapital: pagos, timbrado y pagarés observados

La aplicación prepara el plan de los dos formatos textuales admitidos: resumen anterior con contratos LD y cuenta de cheques con folios y pagarés del formato nuevo. Confirmar guarda una cuenta operativa y sus movimientos; pagarés y saldos de inversión se conservan como observaciones fechadas del plan. No crea todavía una cartera contable de contratos ni un patrimonio total confirmado.

## Flujo

1. Subir o abrir el PDF. Si está protegido, introducir su contraseña para procesarlo y después en **Desbloquear plan** para releer el original financiero.
2. Revisar movimientos y posiciones a plazo. La moneda debe estar publicada como nacional/MN/MXN, o acreditarse mediante revisión expresa para ese documento. Una moneda extranjera o contradictoria no puede sobrescribirse.
3. Confirmar cuando todos los controles pasen. La app verifica de nuevo original, revisión y estado del libro, y guarda el lote en una transacción.

La contraseña solo se mantiene en memoria durante la revisión: no se guarda en el plan o base de datos. Se elimina al abandonar/confirmar y se vuelve a solicitar al recargar. El PDF cifrado original permanece intacto.

## Tratamiento

| Evidencia | Registro |
| --- | --- |
| Transferencia o movimiento operativo admitido | Aportación/reducción con origen pendiente, sin capital externo presumido |
| Apertura de pagaré | Reducción de efectivo; conserva el retiro con signo negativo del formato anterior como evidencia |
| Devolución de principal | Aportación al efectivo; no es interés |
| Interés de inversión cobrado | Ingreso bruto desde su fila, una vez |
| ISR pagado | Retención desde su fila; no se duplica por aparecer en el resumen |
| Cargo de timbrado | Comisión, con evidencia propia |
| Descuento de timbrado | Devolución de comisión, con evidencia propia; no aportación, cashback o ganancia |
| Pagaré vigente | Observación de capital, fechas, tasa, GAT y proyecciones, sin cobro futuro registrado |
| Apertura/cierre operativo | Anclas documentales, sin capital nuevo por cambiar de mes |

Los depósitos y retiros del resumen ya incluyen sus componentes: no se añade otra vez principal, interés, ISR o timbrado. El libro conserva cargo y descuento aunque compartan folio y se compensen. **Cargos de comisiones e IVA** muestra el neto de comisiones menos devoluciones; la lista de movimientos conserva ambos importes brutos y su saldo intermedio validado por el lector.

El interés/ISR futuro de pagarés se mantiene separado del pagado. Los campos no publicados por el formato anterior siguen desconocidos, incluidos retención y neto al vencimiento. No se aplican tasas actuales a contratos históricos, ni se fusionan automáticamente identificadores LD con números del formato nuevo.

## Controles

- Se requieren ambas lecturas específicas y conciliación completa de efectivo y pagarés. Una diferencia contractual bloquea todo el lote, aunque el efectivo cuadre.
- Se contrastan saldos por fila, depósitos/retiros y cierre, además del interés/ISR pagado y las comisiones netas después de normalizar. No se fabrican ajustes ni se borran filas compensadas.
- Un folio con categorías diferentes puede ser válido; una categoría repetida para el mismo folio queda bloqueada, conservando evidencia. Fechas, columnas e importes deben ser compatibles.
- Interés/ISR no nulos de cheques, comisiones del formato anterior, conceptos nuevos o pagos parciales requieren mapeo específico. El formato nuevo admite el timbrado y su descuento reconocidos.
- Solapamientos y saldos contiguos incompatibles bloquean. Se admiten meses fuera de orden; los huecos permanecen visibles. Reintentos no duplican; errores revierten documento, aprobación, movimientos y cobertura.

## Alcance pendiente

El libro muestra el cierre **operativo** por fecha, interés/ISR pagados y cargos netos. Los pagarés se consultan como observaciones en el documento, sin sumarlos como otro saldo confirmado ni acumular sus apariciones mensuales. No se confirma reinversión, vínculo entre instituciones o equivalencia entre contratos por coincidencia de importes.

Quedan pendientes cartera histórica de pagarés, revisión de equivalencias/vencimientos entre documentos, contrapartidas, reinversión, correcciones y confirmación financiera desde imágenes. El OCR local sigue disponible como evidencia revisable. Retención pagada y proyección no determinan el impuesto anual.

Procesamiento local/offline después de instalar las dependencias existentes. Sin servicios, APIs o pagos nuevos. Pruebas ficticias; la muestra real solo se utiliza para generar un plan sin confirmar movimientos personales.
