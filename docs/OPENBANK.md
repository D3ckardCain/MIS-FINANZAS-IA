# Openbank: lectores de débito e inversiones

## Entrega

Dos clases independientes en `finanzas.openbank`:

- `OpenbankDebitReader`: sección Cuenta Débito Open Light.
- `OpenbankInvestmentReader`: sección Apartado Open.

Ambos producen `Preview`; no escriben en SQLite ni aprueban documentos. El módulo lee PDF textual local mediante pypdf 6.10.0 (BSD-3-Clause), sin APIs ni conexión externa. Los PDF escaneados, cifrados, otros productos y otros formatos requieren adaptación.

## Uso local

Instalar el extra con `python -m pip install -r requirements-pdf.txt`, preferiblemente dentro de un entorno virtual. La biblioteca se descarga durante la instalación; la lectura posterior funciona offline.

```python
from pathlib import Path
from finanzas.openbank import OpenbankDebitReader, OpenbankInvestmentReader, transfer_candidates

content = Path("estado_privado.pdf").read_bytes()
debit = OpenbankDebitReader().read_pdf(content)
investments = OpenbankInvestmentReader().read_pdf(content)

print(debit.reconciled, debit.issues)
print(investments.reconciled, investments.issues)
print(transfer_candidates(debit, investments))
```

No publicar la salida detallada ni el PDF en el repositorio público.

## Qué conserva y comprueba

- Huella de los bytes del documento, producto, período interno, importes Decimal y tasa anual informativa del resumen.
- Cada fila conserva fecha efectiva, descripción completa, columna depósito/retiro, saldo, página y línea de extracción.
- Contrasta la extracción por columnas con la extracción lógica del PDF. Esto evita mezclar descripciones que se dibujan antes o después de la fecha.
- Separa páginas de continuación de la tabla y páginas informativas sin movimientos.
- Comprueba cada saldo intermedio, saldo final, total de entradas, total de salidas y cobros de intereses.
- En el formato soportado, los intereses se presentan aparte de Depósitos. La conciliación no cuenta ese interés dos veces.
- Reconoce aportación desde débito y retiro hacia Apartado. Los movimientos operativos restantes siguen como movimientos de débito; no se reclasifican automáticamente como capital externo.
- Conserva retención cero documentada. Si falta ese campo, rechaza el formato. Si ISR o comisiones son no nulos, conserva los importes y exige adaptar/revisar su detalle antes de considerar conciliado.
- Conceptos de inversión desconocidos o diferencias contables quedan en `issues`; estructura ilegible o extracciones contradictorias producen `FormatError`.
- `reconciled` significa que pasaron estos controles; no certifica totalidad histórica, fiscalidad ni identidad de contrapartes.

## Transferencias y reinversión

`transfer_candidates` propone únicamente pares únicos compatibles del mismo documento y fecha entre débito e inversión, y solo si ambas vistas concilian. Coincidencias ambiguas no se enlazan. La propuesta requiere revisión: no confirma por sí sola una transferencia ni genera aportaciones externas.

Los abonos de interés se conservan en su fecha de registro, sin repartir automáticamente fines de semana. La tasa del resumen se registra como informativa; no crea un historial contractual ni se aplica a otros meses.

## Límites

No hay pantalla de revisión ni confirmación del importador todavía. El PDF no siempre ofrece una referencia estable por abono; el lector no inventa IDs globales con fecha/importe ni incorpora sus filas automáticamente. La próxima integración deberá resolver identidad, saldos iniciales entre meses, selección de movimientos, aprobación y guardado transaccional.

`read_pages` acepta texto con columnas para pruebas o integración. Las descripciones multilineales necesitan también `raw_pages` con extracción lógica; en su ausencia se rechazan para evitar asignarlas al movimiento incorrecto.

Las páginas/filas son localizadores de extracción, no coordenadas visuales. La verificación del original se hace con la huella documental; no se guarda el archivo dentro del lector.

## Identidad y períodos sin movimientos

Las vistas ahora conservan `account_fingerprint`, `recipient_fingerprint` e `identity_source`. Débito usa el número explícito de cuenta. Apartado usa la cuenta débito padre del mismo PDF junto con el producto, porque su sección no siempre imprime número propio. Esta identidad permite revisar continuidad de cada vista sin mezclar ambas; no equivale a un número de Apartado confirmado por la constancia. Cuando no hay datos de identidad, quedan desconocidos y la cobertura no los acepta como cuenta identificada.

El RFC del cliente puede estar en la segunda columna; el RFC del emisor no lo sustituye. Dos cuentas o RFC contradictorios dentro del archivo se rechazan.

Una sección de resumen explícitamente íntegro en cero puede omitir por completo la tabla de transacciones. Se acepta solo si no hay importes monetarios no nulos, filas fechadas o una tabla declarada sin encabezado reconocible. Una sección ausente sigue siendo ausente, distinta de un período documentado en cero. Un resumen o tabla no nulos no se corrigen ni se omiten.

`ready_to_import=False`: la conciliación produce una vista previa y no guarda datos financieros.
