# Plata: confirmación de débito y ahorro

La aplicación prepara automáticamente el plan de ambos productos al abrir un PDF textual del formato admitido. Tras revisar el plan, **Confirmar** guarda el lote completo en el libro local. Si un control falla, no se confirma ninguna de las dos cuentas.

| Evidencia | Tratamiento financiero |
| --- | --- |
| Cuenta y ahorro con CLABE diferentes | Dos cuentas y dos períodos; el agregado sirve únicamente de control |
| Cashback abonado | Aportación con origen cashback, una sola vez |
| Transferencia explícita entre cuentas propias con pareja única | Reducción en débito y aportación en ahorro, enlazadas y neutrales en el total |
| SPEI sin contrapartida acreditada | Aportación/reducción con origen pendiente, sin presumir capital externo |
| Rendimiento del detalle | Interés bruto, separado del capital aunque el resumen combine depósitos e intereses |
| ISR del detalle | Retención registrada una vez; el ISR global informativo no genera otro cargo |
| ISR cero publicado sin fila | Evidencia de retención cero por producto |
| Apertura y cierre | Anclas documentales; no aportaciones mensuales adicionales |
| Tasa, saldo promedio y GAT | Condiciones históricas publicadas, sin sustituir por tasas actuales |
| Comprobante fiscal anexo | Evidencia identificada por página, sin generar comisiones ni duplicar impuestos |

## Fechas y control

La fecha efectiva del movimiento es la fecha de cargo publicada; operación y cargo se conservan por separado. Si cualquiera queda fuera del período, el documento completo permanece bloqueado, aunque sus sumas cuadren. No se cambia la fecha al lunes o al día del corte, ni se importa solo el producto que sí pasa los controles.

Se exige conciliación de ambos productos y agregado, moneda MXN/tipo de cambio uno, identidad consistente, secuencia cronológica y coincidencia de cierre, depósitos/rendimientos, interés e ISR después de normalizar. Una base agregada de ISR inexplicable, una transferencia propia sin pareja única o conceptos desconocidos bloquean la confirmación. Comisiones/IVA no nulos requieren todavía mapeo específico.

Las referencias con guion siguen desconocidas. Cada fila conserva evidencia por documento/página/línea; dos operaciones iguales legítimas permanecen distintas. Entre PDFs se bloquean períodos superpuestos y diferencias de continuidad, sin asumir identidad económica por importe. Se admiten meses fuera de orden; los huecos permanecen visibles.

El original, revisión y estado del libro se comprueban otra vez al confirmar. Documento, aprobación, movimientos y cobertura se guardan en una única transacción; los fallos revierten todo y los reintentos no duplican. El libro muestra cierres documentales por cuenta y fecha, sin convertirlos en un saldo patrimonial actual.

## Límites

La retención no determina el ISR anual definitivo. No se infiere reinversión por dejar intereses en ahorro. Quedan pendientes otros productos/plazos, conciliación entre instituciones, correcciones y confirmación financiera desde imágenes. El OCR local continúa disponible como evidencia documental revisable.

Sin servicios ni dependencias nuevas: este procesamiento funciona localmente y sin conexión después de instalar la aplicación y sus dependencias. Las pruebas usan documentos ficticios; la muestra real se utiliza solo para comprobar el bloqueo temporal, sin confirmar movimientos personales.
