# Fintual: efectivo y valuación separados

La aplicación prepara el plan del PDF textual MXN del formato admitido. La confirmación registra **el efectivo del portafolio**, con depósitos, retiros, compras, ventas y gastos publicados. Posiciones, costo promedio, variación, rendimiento porcentual, pendientes de liquidación e ISR informativo quedan como observaciones en el plan aceptado.

## Flujo

1. Subir o abrir el PDF. Si está protegido, introducir su contraseña para procesarlo y en **Desbloquear plan** para releer el original financiero. Solo permanece en memoria durante la revisión; no se guarda en el plan/base y se elimina al abandonar/confirmar.
2. Revisar movimientos y posiciones anterior/actual observadas. La moneda debe estar acreditada en el documento como pesos mexicanos; una moneda ausente o contradictoria bloquea este formato.
3. Confirmar cuando todas las comprobaciones pasen. El original, revisión y estado del libro se verifican de nuevo antes de guardar todo en una transacción.

## Separación de conceptos

| Evidencia | Tratamiento |
| --- | --- |
| Depósito / retiro | Aportación / reducción de efectivo con origen o contrapartida pendientes |
| Compra / venta | Reducción / aportación de efectivo con base pendiente; no calcula ganancia realizada |
| Comisión e IVA de sus columnas | Dos componentes de gasto con evidencia propia; se cobran una vez |
| Posiciones y precios | Observaciones de valuación, sin interés cobrado ni nuevas cuentas contables |
| Variación y rendimiento porcentual | Información reportada, sin ingreso en efectivo o tasa de interés contractual inferidos |
| ISR informativo | Cifra conservada como observación, sin cargo adicional de efectivo |
| Saldo inicial/final de efectivo | Anclas del período; no nuevas aportaciones al cambiar de mes |
| Pendiente por liquidar | Observación del resumen, sin movimiento o cuenta ficticios |

La vista de inversión identifica el portafolio; las dos pestañas no generan dos cuentas. El libro usa la etiqueta **Efectivo del portafolio** y su cierre por fecha. Ese importe no es el valor de los fondos ni el total patrimonial actual. Las posiciones repetidas entre meses no se suman como nuevas inversiones.

## ISR y rendimiento

La cifra de ISR publicada no queda acreditada por este formato como cargo independiente de efectivo: la conciliación ya utiliza los flujos del detalle. Se conserva íntegra en el resumen observado y no se descuenta otra vez.

La retención de efectivo y el interés neto permanecen desconocidos hasta acreditar su asignación. Esto también aplica si el ISR informativo publicado es cero: se mantiene el cero observado, sin crear una retención de efectivo ficticia. No determina exención, costo fiscal, ganancia realizada o impuesto anual.

## Controles y límites

- Se requiere lectura específica de inversiones y conciliación completa de posiciones, resumen y efectivo; una diferencia del saldo inicial de cartera bloquea el lote aunque el efectivo cuadre.
- Se contrastan cierre de efectivo, depósitos/retiros y comisiones después de normalizar. Importes de operaciones no positivos, gastos negativos, conceptos desconocidos o posiciones negativas fuera de este perfil bloquean.
- Las fechas de operación se conservan; una fecha suelta de liquidación del detalle no genera otra operación. Operaciones iguales legítimas mantienen evidencia distinta por documento/página/línea/componente.
- Una tabla vacía requiere la declaración explícita admitida por el lector. Un rendimiento NaN permanece desconocido y bloquea; no se transforma en cero.
- Solapamientos y diferencias de continuidad de efectivo bloquean. Se admiten meses fuera de orden y los huecos permanecen visibles. Reintentos no duplican; fallos revierten documento, aprobación, movimientos y cobertura.

Quedan pendientes contabilidad de unidades y costo por lote, conciliación histórica de posiciones/pendientes, ganancia realizada, atribución de ISR, reinversiones, contrapartidas, correcciones y confirmación financiera desde imágenes. El OCR local sigue disponible como evidencia revisable.

Funciona localmente y sin conexión después de instalar las dependencias existentes. No añade servicios, APIs ni pagos obligatorios. Pruebas ficticias; la muestra real se utiliza solo para comprobar el bloqueo de discrepancias documentales, sin confirmar movimientos personales.
