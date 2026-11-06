# Mifel: cuenta a la vista remunerada

El lector optativo reconoce resumen, tabla de rendimientos por producto y detalle operativo de la cuenta remunerada. Ambas vistas representan la misma cuenta y conservan `shared_account=True`; no se duplica su saldo.

```bash
python -m finanzas.readers estado.pdf --institution mifel --lane investments --reconcile
python -m finanzas.readers estado.pdf --institution mifel --lane debit --reconcile
```

## Fechas y rendimiento

Cada interés conserva fecha de abono y rango remunerado explícito. Un abono puede incluir fines de semana, días inhábiles o días del mes siguiente. No se desplaza al lunes ni se cambia su mes de cobro. No se divide entre días mediante una tasa o base anual supuesta.

`review_mifel_documents` distingue cobertura mensual de estados y unión de rangos remunerados. Señala huecos/solapamientos y cuenta la unión de días, sin duplicar períodos que reaparecen en copias binarias del mismo documento.

Se agrupan interés y retención únicamente con misma fecha y raíz de referencia, exigiendo una fila de cada tipo. Se conservan referencias completas, rangos, importes y página/línea. El neto es calculado, no otro ingreso. No se confirma una importación.

## Controles

Se cotejan cada saldo corriente, totales de depósitos/retiros, ecuación del efectivo, interés/ISR frente al resumen y tabla de productos, y posición de cuenta/portafolio. Se preservan tasa, GAT y promedio publicados; las cifras redondeadas de gráficos no reemplazan importes exactos.

Una aportación modifica el saldo en su fecha original. Su origen sigue pendiente hasta contrastar otra cuenta. El interés que permanece en la cuenta no genera otra aportación externa ni otro ingreso por reinversión.

Inversiones a plazo/fondos en cero no significan que la cuenta remunerada tenga saldo cero. Otros productos con valores no nulos requieren un adaptador específico y dejan revisión pendiente; no se mezclan con esta cuenta. Los saldos de otras secciones no se infieren a partir de celdas vacías.

## Límites

Formatos, referencias, fechas o conceptos desconocidos, rangos ausentes/invertidos y diferencias de un centavo quedan pendientes. Las referencias repetidas se conservan y señalan; no se deduplican operaciones por fecha/importe. El detalle termina en sus totales para no tratar cargos objetados, notas o facturas como movimientos adicionales.

No calcula reglas de devengo diario ni ISR anual o su acreditamiento. El OCR local acepta imágenes sin heredar conciliación PDF. No se importan datos reales ni Excel y `ready_to_import=False` siempre. Los originales e informes financieros permanecen privados; no se añaden APIs de pago.

## Confirmación en la aplicación

El formato textual conciliado ya se conecta al ledger mediante un plan financiero revisable. Ambas pestañas conservan una cuenta única, sin duplicación de capital, interés o ISR. Ver [manual de importación Mifel](IMPORTACION-MIFEL.md). La entrada de imagen sigue siendo evidencia OCR pendiente de confirmación financiera.
