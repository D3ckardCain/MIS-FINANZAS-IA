# Importación financiera — primera integración: Openbank

La aplicación conecta el lector Openbank PDF con el ledger. Mifel cuenta con su propia integración documentada en [Importación Mifel](IMPORTACION-MIFEL.md). BanCoppel tiene [integración de cuenta de paso](IMPORTACION-BANCOPPEL.md). DiDi tiene [confirmación de cuenta remunerada](IMPORTACION-DIDI.md). Cada institución conserva sus reglas; imágenes y constancias fiscales todavía no se confirman financieramente.

## Flujo de uso

1. Subir o abrir un documento Openbank. La aplicación prepara automáticamente el plan financiero.
2. Revisar sus períodos, movimientos propuestos y advertencias. **Preparar importación financiera** permite actualizar el plan si cambió la revisión documental u otro período del libro.
3. Pulsar **Confirmar importación** cuando el plan esté listo. Un plan bloqueado no ofrece confirmación.
4. Abrir **Libro financiero** para consultar los cierres por cuenta/producto y fecha, interés cobrado, retenciones documentadas, períodos importados y orígenes pendientes.

Marcar un documento como revisado sigue siendo una acción distinta: no confirma movimientos financieros.

## Reglas de conversión

| Evidencia del estado | Registro financiero |
| --- | --- |
| Abono de intereses | Interés cobrado, separado de capital |
| Traspaso explícito entre débito y Apartado con pareja única | Reducción en origen y aportación en destino, mismo vínculo propio |
| Otro abono/cargo de débito | Aportación/retiro con origen pendiente; no se inventa capital externo |
| Retención explícita cero en el resumen | Registro de retención cero con evidencia de resumen; no cambia efectivo |
| Saldo inicial/final | Ancla documental del período; no se transforma en aportación o nueva apertura mensual |

Los traspasos se proponen por conceptos complementarios explícitos, fecha, importe y ambas vistas del mismo PDF. La confirmación acepta esos vínculos junto con el lote. Dos pares indistinguibles se bloquean; no se decide por orden de filas ni por coincidencia casual de importes.

La identidad económica entre PDFs no se deduce de fecha e importe. Dentro del archivo se identifica evidencia por documento/cuenta/página/línea; entre archivos, los períodos superpuestos de la misma cuenta se bloquean antes de duplicar registros. No hay todavía un flujo para sustituir estados corregidos o resolver importaciones superpuestas.

## Saldos e historia

Cada período debe reconstruir exactamente su cierre desde su apertura y movimientos normalizados. Entre períodos consecutivos, el cierre anterior debe coincidir con la apertura siguiente. Una diferencia bloquea el lote, sin ajustes ficticios.

Se permite cargar meses fuera de orden. Los saldos iniciales permanecen como anclas de períodos y no como aportaciones ni movimientos adicionales del ledger. Por ese motivo, `Ledger.balances()` sin apertura representa únicamente el neto de movimientos importados; la aplicación muestra el **saldo de cierre documental** de `FinancialBook.summary()` con su fecha, sin presentarlo como saldo actual.

Los huecos entre períodos importados se muestran y no se rellenan con supuestos. El primer período importado no acredita la apertura real de la cuenta. Intereses y retenciones son acumulados de los períodos efectivamente confirmados, no necesariamente de toda la historia.

## Confirmación y persistencia

El plan se vuelve a calcular desde el original al confirmar; incluye la revisión documental y una huella del estado del libro. Si cambió alguno, se exige preparar otro plan. La bandeja se bloquea durante esa comprobación, sin modificar su original o extracción.

Una sola transacción financiera incluye registro documental, aprobación, movimientos, evidencias, cobertura y plan confirmado. Las operaciones anidadas del Store usan savepoints. Un fallo revierte todo el lote. Reintentar la misma confirmación devuelve la importación existente sin volver a sumar nada.

La base financiera se guarda junto a la bandeja, con sufijo `.ledger.sqlite3`. Ambas son archivos locales privados, fuera de Git. La base financiera conserva una copia inmutable del plan aceptado, su revisión y huella. Reprocesar un documento ya importado no modifica sus movimientos confirmados; corregirlos requiere un flujo específico posterior. Para trasladar el conjunto de datos se necesitan las dos bases con el servicio detenido.

## Límites explícitos

- Solo Openbank textual con formatos conciliados e identidad de cuenta publicada. Vistas no disponibles o meramente documentales se excluyen con advertencia; una transferencia propia sin contrapartida única bloquea el lote.
- Una discrepancia del lector, retención/comisión no nula sin formato de detalle admitido, concepto desconocido o inconsistencia de normalización bloquea la vista/lote según su alcance.
- Los orígenes desconocidos permanecen pendientes. No hay aún interfaz para acreditar origen externo/cashback o parear transferencias entre instituciones.
- Sin reinversión inferida, cálculo anual SAT, equivalencias de monedas ni valoración de posiciones. El cierre de débito y el de inversión se consultan separados.
- Los lectores originales continúan devolviendo `ready_to_import=False`: leer no aprueba. La capa financiera revisa y confirma un plan distinto.

Pruebas con PDF ficticios: normalización, retención cero, reducción/aportación propia, origen desconocido, reintento/reapertura, solapamientos, meses fuera de orden, límites de continuidad, huecos, versiones/planes obsoletos, fallo intermedio con rollback total, identidad ausente, conceptos/retenciones no admitidos y confirmación HTTP real. La inspección visual usa datos ficticios; no se confirmó contabilidad personal del titular.
