# YoTePresto: cuenta operativa y cartera de préstamos

Dos vistas de una cuenta de plataforma, con lector PDF específico y evidencia OCR local. La vista llamada `debit` es operativa: no afirma que exista una cuenta bancaria de débito. Ambas comparten documentos, movimientos e identidad, sin sumar dos veces su patrimonio.

```bash
python -m finanzas.readers estado.pdf --institution yotepresto --lane debit --reconcile
python -m finanzas.readers estado.pdf --institution yotepresto --lane investments --reconcile
```

La salida habitual muestra conteos, controles e incidencias. `--details` contiene información financiera privada. PDF/OCR usan las dependencias locales existentes; no se añade un servicio externo ni se importa información automáticamente.

## Separaciones necesarias

- `summary.initial/final`: saldos globales informativos publicados, distintos del efectivo disponible (`available`). La continuidad global se revisa con `review_coverage`.
- Interés ordinario, moratorio, IVA de ambos, comisión base/IVA y retenciones IVA/ISR: campos distintos. El recibido publicado puede incluir IVA y no equivale solo al interés ordinario ni a rendimiento neto final.
- `gain_reported` conserva «ganaste». `gain_basis_observed` distingue coincidencia antes de retenciones, después de retenciones o base no explicada; no impone una fórmula a todos los meses.
- `rows`: diario operativo con pagos compuestos, aportaciones, retiros, fondeo de préstamos, cancelaciones, comisiones y retenciones. Un pago no se convierte íntegramente en interés; puede contener capital recuperado.
- `loans`: observaciones de préstamos con ID, estado, plazo literal, tasa publicada y saldos. Interés, IVA y capital pagados **acumulados** no se suman como cobros del mes.
- `arrears`: ID, estado, días de atraso y contexto publicado. Motivo/cobranza se conserva como texto sin inventar la atribución cuando las columnas están incompletas.

Se admiten los formatos de cartera con usuario partido en otra línea y los que omiten esa columna. Un usuario omitido queda desconocido; no se toma la primera palabra del estado como usuario. El plazo `x/y` se guarda literalmente, sin asumir vencimiento, meses restantes o ganancias futuras.

## Controles independientes

`summary_reconciled` exige que coincidan los desgloses y la ecuación con los campos publicados. Cuando no figura una sección de retenciones, sus importes quedan `None`, no cero; el resumen fiscal completo no se da por acreditado.

`detail_reconciled` revisa los saldos operativos y totales observados. El primer saldo de efectivo se conserva como candidato aritmético (`cash_initial_implied`), no como apertura publicada; esa falta bloquea el detalle completo de un documento aislado. `review_yotepresto` coteja ese candidato con el disponible del mes anterior, cuando los meses son consecutivos.

Se cotejan también las comisiones y retenciones netas de sus cancelaciones. El fondeo de préstamos se compara tanto bruto como neto de cancelaciones; no se fuerza una equivalencia si ninguna base coincide.

Los importes y signos originales se preservan, incluso en cancelaciones. Los pagos, comisiones y retenciones de una misma fecha/referencia son filas distintas. El ID de evidencia usa archivo/página/línea; no es un ID económico de pago para eliminar registros repetidos. No se reordenan filas por saldo para forzar conciliación.

`portfolio_issues` coteja la suma de saldos finales de préstamos con los importes de categorías de portada y con el saldo global más disponible. Las diferencias señalan incompatibilidades entre cifras publicadas, sin afirmar su causa o introducir ajustes. Un conteo `--` queda desconocido. El acumulado «pagado» de portada no se añade otra vez al activo vigente.

`reconciled` requiere pasar resumen, detalle y cartera. `ready_to_import=False` siempre. La lectura íntegra de un archivo o continuidad global no acredita conciliación completa de sus movimientos.

## Historia y reinversión

`review_yotepresto(previews)` deduplica archivos binarios, exige el mismo usuario y rechaza solapamientos o metadatos incompatibles. Conserva observaciones mensuales separadas. Solo coteja acumulados entre meses consecutivos y préstamos con ID único por documento; disminuciones se registran para revisión, sin convertirlas automáticamente en pérdida o reverso.

El capital recuperado y el rendimiento que quedan disponibles pueden volver a financiar préstamos. Fondear un préstamo es reducción del efectivo y asignación a una inversión, no otra aportación externa ni una ganancia. El lector conserva los hechos necesarios, pero no confirma reinversión por igualdad de importe/fecha ni reparte un pago compuesto sin evidencia suficiente.

Los formatos admitidos separan períodos, moneda nacional y tasas por préstamo. No se aplican tasas actuales al pasado, se construye un calendario de pago supuesto, se reconstruye titularidad externa ni se calcula ISR anual. Las imágenes conservan evidencia OCR y requieren revisión; no heredan automáticamente verificaciones del PDF. Documentos, cartera, referencias e informes reales permanecen privados; las pruebas públicas son ficticias.
