# CETESdirecto: efectivo liquidado y cobros pendientes de desglose

La aplicación prepara un plan para los formatos textuales admitidos. Confirmar incorpora **el efectivo del portafolio**, sus compras, cobros y cargos de ISR. Posiciones, precios, resultados y acumulados se conservan como observaciones; no se crea todavía una cartera contable de títulos o costo por lote.

## Flujo

1. Subir o abrir el PDF. Si está protegido, proporcionar contraseña para procesarlo y en **Desbloquear plan** para releer el original financiero. Solo permanece en memoria durante la revisión; no se guarda en plan/base.
2. Revisar efectivo, posiciones observadas y **Cobros pendientes de separar en capital/interés**. Este perfil requiere moneda MXN/PESOS publicada; ausencia o contradicción bloquea.
3. Confirmar cuando las comprobaciones del documento y el plan pasen. Original, revisión y estado del libro se verifican otra vez; la confirmación guarda el lote completo en una transacción.

## Tratamiento

| Evidencia | Registro |
| --- | --- |
| Entrada / salida de efectivo | Aportación / reducción con origen o contrapartida pendientes |
| Compra / COMPSI | Reducción de efectivo, sin inferir capital externo o reinversión |
| Venta / amortización | Cobro de valores sin asignación de principal/interés, conservando todo el efectivo recibido |
| ISR de operación | Retención desde su cargo, una vez |
| ISR cero publicado sin cargo | Evidencia de retención cero del período |
| Interés del período | Observación informativa, sin generar otro cobro |
| Intereses/ISR acumulados del ejercicio | Observaciones separadas; no vuelven a registrarse cada mes |
| BONDDIA/ENERFIN/GUBER y valuaciones | Resultados/precios observados, sin nuevo ingreso de efectivo |
| Apertura/cierre de efectivo | Anclas documentales, sin aportaciones mensuales ficticias |

No se calcula principal recuperado desde el precio o valor de mercado inicial: ese importe no acredita costo de adquisición o capital invertido. El cobro completo se registra como **cobro de valores sin desglose**, una categoría positiva de efectivo distinta de capital externo e interés. Por ahora queda pendiente separar sus componentes con evidencia suficiente.

## Consulta de intereses

El libro muestra separadamente **Interés informado · sin asignación a cobros** y **Cobros de valores sin desglose**. Si existen cobros sin asignación o interés informado pendiente de atribuir, el interés clasificado y su neto quedan **desconocidos**, no en cero. Tampoco se añade el interés informado a la amortización, lo que duplicaría efectivo.

Una cuenta sin operaciones, con interés del período cero y totales explícitos conciliados, puede acreditar ese cero. Si algún período de la cuenta tiene interés sin clasificar, el agregado sigue incompleto; la cifra informada conserva únicamente los períodos importados, sin sumar acumulados anuales.

El ISR registrado sigue siendo retención, no impuesto anual definitivo. No se infiere reinversión por venta y compra consecutivas ni por coincidencia de folios/importes.

## Fechas y controles

- Fecha efectiva de efectivo: **liquidación publicada**. También se conserva registro. Registro anterior al mes con liquidación dentro del mes es válido; una liquidación fuera del período bloquea el lote, sin moverla al día del registro o al corte.
- Se exige conciliación de posiciones, resumen y detalle. Una discrepancia entre efectivo del resumen y del diario bloquea; no se elige uno de los dos ni se ajusta el otro.
- Se comprueban sentido de columnas por código, orden de liquidación, saldo corriente, cierre normalizado, entradas/salidas e ISR. Saldo intermedio negativo publicado se conserva; no se reconstruyen filas para ocultarlo.
- Folio compartido entre amortización e ISR no significa duplicidad. Operaciones iguales legítimas conservan evidencia distinta por documento/página/línea; no se deduplican por importe o folio.
- Períodos superpuestos o saldos de efectivo contiguos incompatibles bloquean. Meses fuera de orden admitidos, huecos visibles y reintentos idempotentes. Fallos revierten documento, aprobación, movimientos y cobertura.

El cierre del libro está rotulado como **Efectivo del portafolio**, no como valor de cartera más efectivo ni patrimonio actual. Quedan pendientes costo/unidades por lote, desglose de amortizaciones/ventas, continuidad histórica de posiciones, contrapartidas, reinversión, fiscalidad anual, correcciones y confirmación financiera desde imágenes. El OCR local conserva evidencia revisable. Detalle multipágina no reconocido por el lector continúa bloqueado.

Funciona localmente y offline después de instalar las dependencias existentes, sin APIs, servicios o pagos nuevos. Pruebas ficticias; la muestra real se utiliza únicamente para comprobar el bloqueo de diferencias de efectivo, sin confirmar movimientos personales. Fintual conserva su identidad MXN/USD corregida.
