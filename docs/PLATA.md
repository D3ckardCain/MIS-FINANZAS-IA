# Plata: cuenta y ahorro flexible

El adaptador local conserva dos productos separados bajo una relación compartida. Las CLABE de cada producto se comparan con su sección de movimientos y se representan mediante huellas; no se publican identificadores reales.

## Uso

```python
from finanzas.readers import reader_for
preview = reader_for('plata', 'investments').read_reconciled_pdf(pdf_bytes)
# Vista alternativa: 'debit'
```

El catálogo mantiene entrada PDF/imagen. La imagen usa OCR local y revisión de evidencia; no garantiza por sí sola la conciliación económica del adaptador PDF.

## Interpretación

- Conserva período interior, fecha de operación y fecha de cargo por separado. Una fila fuera del período permanece en la vista documental y bloquea la conciliación temporal, sin cambiar su fecha.
- Separa resumen global, cuenta y ahorro. Depósitos y rendimientos pueden estar combinados en el resumen: el interés del detalle no se suma por segunda vez.
- Distingue cargos de cuenta, retención ISR e interés bruto. Comprueba si el ISR informativo global ya está incluido en otros cargos; una base inexplicable queda pendiente. Retención no equivale a impuesto anual definitivo.
- Conserva tasa anual, saldo promedio y GAT nominal/real publicados. No calcula condiciones históricas ausentes ni sustituye valores por ofertas actuales.
- Cashback es aportación con categoría propia. El traspaso propio reduce la cuenta de origen y aporta a destino; el vínculo y su posible procedencia de cashback son candidatos pendientes de revisión, sin crear capital externo adicional.
- Guiones en referencia significan referencia desconocida. Operaciones del mismo importe y fecha se conservan como evidencias distintas; la identidad por documento/página/línea no prueba identidad económica entre documentos.
- El signo negativo puede estar separado del importe en una descripción continuada. Filas malformadas, identidad ambigua o producto discordante se rechazan.
- El anexo «Comprobante fiscal» se identifica por página y se excluye de movimientos financieros. No se interpreta como constancia anual ni como nuevas comisiones.

## Controles y límites

`summary_reconciled` comprueba aritmética del producto y agregado. `detail_reconciled` exige además coherencia temporal. Una suma correcta puede coexistir con cargos posteriores al corte.

`ready_to_import` del lector permanece falso: la extracción sola no confirma movimientos. La aplicación dispone de un [plan financiero separado](IMPORTACION-PLATA.md), con revisión y confirmación atómica de ambos productos cuando todos los controles pasan. Enlaces entre instituciones y cobertura histórica siguen pendientes. No se infiere reinversión solo por permanecer el interés en el producto.

Pruebas sintéticas: dos identidades, descripción continuada, cashback, cargos/ISR agregados, interés incluido, fechas posteriores al corte, anexo fiscal, operaciones iguales legítimas, pares ambiguos, moneda/concepto desconocidos, identidad discordante, ISR cero y recorrido PDF del catálogo.
