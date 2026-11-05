# CETESdirecto: conciliación de efectivo y posiciones

## Estado y uso

CetesDirectoInvestmentReader procesa el formato textual conocido de estados de CETESdirecto. Es una conciliación documental, no contabilidad fiscal ni importación automática.

```python
from pathlib import Path
from finanzas.readers import reader_for

preview = reader_for("cetesdirecto", "investments").read_reconciled_pdf(
    Path("estado_privado.pdf").read_bytes()
)
print(preview.detail_reconciled, preview.reconciled, preview.issues)
```

```sh
python -m finanzas.readers estado_privado.pdf --institution cetesdirecto --lane investments --reconcile
```

Las imágenes siguen el flujo OCR y revisión descrito en IMAGENES.md. No heredan los controles del PDF.

## Información conservada

- Documento y cuenta por huellas; fechas internas del período.
- Posiciones iniciales/finales: emisora, serie, títulos, precio de mercado Decimal, valuación y campos adicionales impresos.
- Efectivo inicial/final del resumen y del detalle, sin sobrescribir uno con otro.
- Entradas/salidas, interés e ISR del período, e interés/ISR acumulados del ejercicio como campos distintos.
- Resultados adicionales con su etiqueta original: ganancia de capital BONDDIA, rendimiento BONDDIA/ENERFIN o venta anticipada GUBER. No se homogeneizan como interés cobrado.
- Por movimiento: registro, liquidación, folio, código, emisora/serie, campos instrumentales impresos, cargo, abono, saldo, página y línea.

Los campos instrumentales de movimientos pueden tener columnas vacías al extraer texto. Se conserva su secuencia sin inventar una asignación de títulos/precio/plazo/tasa cuando no está demostrada. En posiciones se conservan tipados títulos, precio y valuación; los adicionales requieren su interpretación contractual posterior.

## Controles y límites contables

Se comprueba la suma de valores de las posiciones contra sus totales y contra el resumen; posiciones más efectivo contra total inicial/final; cargos/abonos y saldos de cada movimiento; entradas/salidas de efectivo e ISR del detalle contra sus resúmenes.

Una compra puede registrarse antes del comienzo del mes y liquidarse dentro del período. Se conservan ambas fechas. Un saldo de efectivo de registro temporalmente negativo no se convierte por ello en pérdida o deuda.

No se exige que inicial más interés menos ISR sea igual al total final: el valor de mercado, las operaciones con títulos y los resultados informados tienen naturaleza distinta del efectivo cobrado.

Una amortización y su retención pueden compartir folio. El folio solo no es una identidad global adecuada; no se eliminan componentes por coincidencia.

Los códigos reconocidos son INGEFVO, EGREFVO, COMPRA, COMPSI, VTASI, AMORTIZACION e ISR. Un código nuevo o contradicción queda pendiente. El perfil valida moneda de resumen en pesos/MXN; otras monedas requieren otro mapeo.

## Estados vacíos y diferencias

Un estado sin títulos o movimientos es válido si contiene totales explícitos y compatibles. No equivale a un archivo ausente ni a una ausencia histórica de inversión.

detail_reconciled expresa coherencia del detalle de efectivo. reconciled exige además posiciones y resumen compatibles. Si resumen y detalle difieren, se conservan ambos valores, se señala la discrepancia y no se genera un ajuste ficticio.

ready_to_import permanece False. No se calculan aquí interés real, costo de adquisición, resultado fiscal, declaración anual ni composición capital/interés de cada amortización.

## Identidad y cobertura

document_id es SHA-256 del PDF original. logical_text_id identifica el texto con espacios y Unicode normalizados, conservando mayúsculas. Son huellas con propósitos distintos.

PDF con bytes distintos pueden contener datos textuales equivalentes. Esa comparación ayuda a revisar copias y períodos, pero no certifica por sí sola toda la semántica del documento ni fusiona movimientos. Las evidencias originales se conservan.

La fecha contable sale del documento. El nombre de un archivo no acredita el mes, y una copia del mismo contenido no completa un período faltante.

review_coverage puede comparar posición total de resúmenes consecutivos de una misma cuenta. Ese control no sustituye el del efectivo del detalle, ni resuelve una discrepancia entre resumen y detalle.

## Validación

Pruebas públicas con datos ficticios y PDF generado en memoria; verificación adicional de formatos privados fuera del repositorio. El parser requiere un bloque único de detalle de efectivo y posiciones inicial/final únicas; diseños o tablas multipágina diferentes requieren adaptación.

Los documentos reales, sus importes y el inventario del titular permanecen privados.
