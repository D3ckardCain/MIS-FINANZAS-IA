# DiDi Cuenta: confirmación financiera

Las pestañas operativa e inversión representan una misma cuenta remunerada. La aplicación confirma un solo período y un lote único; no suma dos saldos ni crea un traspaso entre pestañas.

## Uso

1. Subir o abrir un PDF DiDi del formato admitido. El plan financiero aparece automáticamente.
2. Revisar aportaciones, retiros, interés, retención publicada y advertencias.
3. Confirmar el plan cuando esté listo. El libro mostrará una sola cuenta DiDi con cierre/fecha, interés y retención de los períodos importados.

Se admiten los dos formatos de resumen ya reconocidos por el lector. Las imágenes continúan como evidencia OCR; su confirmación financiera no está implementada.

## Interpretación

| Dato | Tratamiento |
| --- | --- |
| Depósitos del resumen | Incluyen rendimientos; no se convierten íntegramente en capital aportado |
| Transferencia entrante | Aportación a la cuenta con origen pendiente |
| Transferencia saliente | Reducción con contrapartida pendiente |
| Fila de rendimientos | Interés cobrado una sola vez, con su fecha y referencia |
| Retención cero publicada | Registro de ISR cero con evidencia de resumen |
| Interés explícito de importe cero | Observación conservada, sin nuevo movimiento de efectivo |
| Saldo inicial y final | Anclas del período, no nuevas aportaciones |
| Tasas, topes y escalones | Metadatos y texto publicados conservados en el plan aceptado |

Por ejemplo, si un estado ficticio publica depósitos de 51 e interés de 1, y sus filas muestran transferencia de 50 e interés de 1, se registra aportación de 50 e interés de 1. No se registra aportación de 51 más otro ingreso de 1.

El origen de las transferencias no se presume externo ni propio. Se registra el movimiento de la cuenta sin enlazarlo por coincidencia de fecha/importe; la conciliación entre instituciones queda pendiente.

## Controles y límites

- Ambas vistas deben disponer de lectura específica; el original se vuelve a analizar al confirmar.
- Identidad de cuenta, período, columnas MXN, fechas, referencias y saldos deben conciliar. Una referencia continuada entre páginas conserva su valor reconstruido y el localizador de la fila.
- La normalización comprueba cierre, depósitos incluyendo interés, retiros, rendimientos e ISR.
- Folios repetidos o ausentes, conceptos desconocidos, moneda no reconocida, diferencias o retención no nula sin desglose admitido bloquean la confirmación. No se estima ni descuenta un impuesto para hacer cuadrar el estado.
- Los folios se acotan a cuenta y período. Operaciones de igual fecha/importe y distinto folio se conservan; estados distintos superpuestos se bloquean.
- Se admiten meses fuera de orden con continuidad comprobada entre períodos consecutivos. Aperturas no se acumulan y huecos no se rellenan.
- No se aplica una tasa única a todos los escalones ni se inventa vigencia a partir de una fecha de cálculo. Tampoco se presume reinversión o ISR anual definitivo.
- La confirmación usa la transacción, revisión y huella del libro existentes; fallos revierten todo el lote y reintentos no duplican.

DiDi coexiste con Openbank, Mifel y BanCoppel sin fusionar cuentas. No hay nuevas dependencias ni servicios externos obligatorios: funciona local/offline después de instalar los requisitos. Pruebas con documentos ficticios y generación de plan sobre la muestra real, sin confirmar movimientos personales del titular.
