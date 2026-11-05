# Catálogo de lectores por institución

## Alcance implementado

Hay 26 entradas documentales con soporte PDF e imagen, más dos lectores de capturas BingX/Pionex (28 entradas totales). Las 26 documentales son: dos vistas para cada una de las 13 instituciones con formatos disponibles. Comparten utilidades de PDF/fechas/evidencia; cada perfil define identidad y selección de secciones.

**No son 26 importadores contables terminados.** Openbank conserva sus dos lectores con conciliación detallada. Los otros perfiles realizan extracción documental por secciones, valores observados y localizadores; requieren mapeo económico y conciliación antes de convertirlos en movimientos. No escriben en la base de datos.

| Institución | Lector de débito | Lector de inversiones | Particularidad |
| --- | --- | --- | --- |
| BanCoppel | Documental y conciliación PDF optativa | Detecta sección si consta | Cuenta de paso; no asumir aportación externa |
| DiDi Cuenta | Documental | Documental, cuenta compartida | Depósitos puede incluir rendimiento; escalones |
| CETESdirecto | Detecta ausencia de sección | Documental y conciliación PDF optativa | Efectivo, títulos, mercado, fechas de liquidación |
| Doopla | Detecta ausencia de sección | Documental | Capital, interés, IVA, ISR y cartera de préstamos |
| Fintual | Detecta ausencia de sección | Documental | Títulos, precios, valuación, venta y retiro |
| Fondeadora | Documental | Detecta Bóveda si consta | Reporte operativo no prueba ausencia histórica de inversión |
| Hey | Documental | Documental | Vencimiento, renovación, neto y devengado |
| Kapital | Documental | Documental | Proyecciones a vencimiento distintas de cobros |
| Nu | Documental | Documental de cajitas | Congelar/descongelar no es capital externo |
| Openbank | Conciliación implementada | Conciliación implementada | Continúa el lector específico ya verificado |
| SuperTasas | Documental | Documental, vista/plazo | Cuenta compartida, capital e interés por separado |
| Plata | Documental | Documental | Cashback, agregado depósitos/rendimientos y registro posterior al corte |
| Mifel | Documental | Documental, cuenta compartida | Cuenta remunerada, retenciones y períodos agrupados |

«Detecta ausencia» significa que devuelve section_missing cuando la sección no figura en el archivo. No declara que la institución no ofrezca ese producto ni que el titular nunca lo haya tenido.

## API y uso

```python
from pathlib import Path
from finanzas.readers import reader_for, available_readers

print(available_readers())
content = Path("documento_privado.pdf").read_bytes()
debit = reader_for("nu", "debit").read_pdf(content)
investments = reader_for("nu", "investments").read_pdf(content)
```

El extra local se instala con requirements-pdf.txt. No hay API de pago ni conexión externa durante la lectura.

Consola local:

```sh
python -m finanzas.readers --list
python -m finanzas.readers documento_privado.pdf --institution nu --lane investments
```

Por defecto imprime un resumen de estado. --details incluye valores y evidencia privados en la salida local: no publicarla en GitHub.

## Resultado documental

DocumentPreview conserva institución, vista, huella documental, períodos y observaciones. Cada observación conserva:

- Página, línea y sección.
- Celdas de texto separadas según espacios de la extracción PDF.
- Decimales y porcentajes observados, sin transformarlos automáticamente en cargos, abonos o rendimientos.
- Tipo orientativo: saldo, capital, interés, ISR, ISR acumulado, comisión, IVA, cashback, congelamiento, transferencia, proyección u otro.
- Identificador documental estable por huella/página/línea, compartido entre vistas.

Los tipos son etiquetas orientativas, no una clasificación económica confirmada. Una línea puede contener varias columnas y conceptos; no se suman automáticamente sus números. No se deduce el signo contable por la presencia o ausencia de un signo impreso.

Los números de una fila pueden ser precios, títulos, tasas o valores, no necesariamente importes de efectivo. Las celdas no constituyen todavía un esquema de columnas bancarias validado. Se conserva la evidencia para el mapeo posterior.

## Estados

- **review_required:** se detectó la sección y se extrajo evidencia; falta el mapeo económico/conciliación propios del formato.
- **section_missing:** no se detectó la sección en este documento; no equivale a cero ni a inexistencia del producto.
- **ReaderError:** identidad institucional incompatible, fechas inválidas, PDF ilegible/cifrado o parámetros incorrectos.

ready_to_import es siempre False en DocumentPreview. No se aprueban documentos, no se confirma la identidad global de una operación y no se generan movimientos.

Openbank devuelve su Preview específico con reconciled e issues. Que el lector concilie tampoco equivale a autorizar su importación.

## Fechas y duplicados

Los períodos salen del contenido. Se admiten rangos numéricos, ISO, meses en español y abreviaturas, y formatos de día inicial sin mes propio. No se utiliza el nombre del archivo ni la fecha del correo.

Si faltan períodos o se detectan varios, el resultado lo señala. No trasladar el período del resumen a todos los contratos ni convertir una fecha de vencimiento en fecha de cobro.

La identidad documental de una observación sirve para enlazar evidencia. No sustituye la referencia institucional del movimiento entre documentos solapados.

En DiDi, Mifel y SuperTasas las dos vistas pueden observar la misma cuenta remunerada. La misma evidencia conserva el mismo ID, sin añadir una segunda posición ni duplicar ISR. Ninguna vista constituye por sí sola un nuevo libro contable.

## Límites y próximos controles

- Estos perfiles reconocen los formatos conocidos; un cambio de diseño puede requerir adaptación. La lectura de imágenes usa OCR local; la de PDF cifrado sigue pendiente.
- No hay importación económica automática para los 12 perfiles documentales ni una conciliación financiera universal.
- Falta mapear tablas/contratos, resolver referencias, conservar todas las relaciones entre columnas, conciliar y preparar confirmación transaccional por institución.
- Los documentos de ISR anual requieren un lector distinto; no se confunden con extractos mensuales.
- No se ha inferido el tratamiento fiscal definitivo a partir de una etiqueta ISR.
- BingX y Pionex tienen lectores iniciales de capturas por etiquetas: ver CRIPTO-IMAGENES.md. Su validación con capturas reales queda pendiente. Wallets, brokers adicionales y FIBRAs requieren fuentes identificadas.
- El Excel no se lee ni se importa con estos lectores.

## Pruebas

La suite sintética cubre las 26 entradas, extracción PDF para los perfiles documentales, ambos lectores específicos de Openbank, separación de vistas, evidencia compartida, formatos de fechas, ausencia de sección, referencia a otra institución, proyecciones, congelamientos, ISR acumulado y PDF corrupto.

Los datos de prueba son ficticios. La comprobación local adicional con fuentes privadas no incorpora archivos, texto, importes ni identificadores del titular al repositorio.

La entrada de imagen devuelve evidencia y revisión pendiente: ver [manual OCR](IMAGENES.md). La consola detecta PDF o imagen por contenido; --ocr-language configura los idiomas locales.

Para BanCoppel existe read_reconciled_pdf o --reconcile: compara el detalle, el resumen y su interés/retención, manteniendo discrepancias sin ajustes ficticios. Ver [manual de BanCoppel](BANCOPPEL.md).

CETESdirecto admite read_reconciled_pdf/--reconcile en Inversiones, preservando por separado efectivo, posiciones, registro/liquidación e ISR del mes/acumulado. Ver [manual específico](CETESDIRECTO.md).

DiDi Cuenta admite conciliación optativa en ambas vistas de una misma cuenta. Separa rendimientos de transferencias, evita duplicar depósitos/rendimientos y conserva condiciones históricas del documento. Ver [manual de DiDi](DIDI.md).
