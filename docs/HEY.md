# Hey: cuenta operativa, pagarés y reinversión

El lector optativo reconoce el formato mensual de estado único validado: cuenta operativa, resumen de pagarés, condiciones por contrato y tabla de capital/interés/ISR/neto al vencimiento. PDF y OCR local siguen disponibles en ambas vistas.

```bash
python -m finanzas.readers estado.pdf --institution hey --lane debit --reconcile
python -m finanzas.readers estado.pdf --institution hey --lane investments --reconcile
```

## Cobro y proyección

- La devolución de capital no es interés. La apertura es cargo en cuenta operativa y aportación local al contrato nuevo.
- Principal, interés pagado y retención se conservan como filas independientes, aunque compartan referencia de contrato.
- El interés del resumen se contrasta con interés pagado menos retención. No se presupone que la columna sea bruta ni se vuelve a descontar el ISR de un neto.
- El interés devengado indicado como incluido en el saldo actual no se suma otra vez como cobro.
- Los importes al vencimiento de contratos vigentes se conservan como futuros. Sus intereses y retenciones no se mezclan con los efectivamente cobrados en el período.

El capital vigente más devengado se contrasta con el saldo actual; cuenta operativa más inversiones actuales se contrasta con Total Portafolio. Total Vigentes se conserva y se compara por separado con los netos al vencimiento. Una diferencia permanece abierta y no reemplaza el saldo actual por una proyección.

## Contratos y condiciones

Cada contrato conserva identificador, apertura, vencimiento, días, tasa anual, capital, interés, ISR, neto, comisión y GAT nominal/real publicados. Las fechas y días deben coincidir; también la tasa de la tabla contractual y sus condiciones. No se recalcula interés mediante una base anual supuesta ni se asigna una tasa fiscal anual a partir de un cargo aislado.

Los contratos vencidos en el período se cotejan con principal, interés y retención de su fecha de pago; las aperturas del período con el cargo y su fecha. Un contrato vigente con pagos no explicados queda pendiente. No se aplican tasas actuales a contratos históricos.

## Reinversión propuesta, sin confirmación automática

Se proponen vínculos entre cuatro filas contiguas de una misma fecha: principal, interés y retención del contrato origen, seguidos por apertura de otro contrato por el importe neto. Deben existir referencias vinculables a contratos únicos. Si el detalle operativo no concilia, no se generan propuestas.

Cada propuesta conserva los cuatro localizadores y `needs_review=True`. No se confirma ni se escribe en el libro. El nuevo contrato puede recibir capital retornado e interés neto; la apertura no es otro ingreso ni capital externo nuevo del consolidado. Los contratos vencidos no se suman a los vigentes para valorar el patrimonio al corte.

## Evidencia, estados y límites

Los cargos/abonos se reconocen por sus columnas de disposición visual y se contrastan contra cada saldo, los totales y el resumen. Los contratos se extraen en modo estándar para conservar fechas que ciertos PDF reordenan visualmente. Cada fila indica `source_extraction`, página y línea.

La vista débito puede conciliar mientras inversiones mantiene diferencias. Los estados corresponden únicamente a las comprobaciones implementadas; `ready_to_import=False` siempre. Las imágenes no heredan conciliación del PDF.

El formato reconocido cubre estos movimientos de pagarés. Conceptos operativos adicionales, pagos parciales, cambios de estructura o referencias ambiguas quedan pendientes; el lector documental general sigue disponible. No se reconstruye la composición del saldo anterior sin sus estados, no se calcula costo fiscal ni declaración anual y no se importan datos reales o Excel.

Sin dependencias nuevas, servicios de pago ni acceso a APIs financieras. Documentos e informes del titular permanecen privados.
