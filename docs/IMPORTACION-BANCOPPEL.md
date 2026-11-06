# BanCoppel: cuenta de paso al libro financiero

La integración confirma el débito del formato conocido. BanCoppel se muestra como **Cuenta de paso**: sus depósitos y transferencias no se convierten en inversiones o rendimientos.

## Uso

1. Subir o abrir un PDF BanCoppel. La aplicación prepara el plan financiero automáticamente.
2. Revisar movimientos, período, apertura/cierre y advertencias. El detalle impreso en orden inverso se interpreta con sus saldos, conservando página/línea y fechas del período interior.
3. Confirmar el plan si está listo. El libro muestra una cuenta operativa con su cierre y fecha, cargos, interés/retención documentados y orígenes pendientes.

La pestaña de inversiones no genera saldo, producto ni transferencia adicional a partir de la cuenta de paso. Imágenes y productos adicionales todavía no tienen confirmación financiera en esta integración.

## Tratamiento

| Evidencia | Movimiento |
| --- | --- |
| Depósito en efectivo o corresponsal | Aportación a la cuenta con origen pendiente |
| SPEI/traspaso recibido o enviado | Aportación/reducción con contrapartida pendiente |
| Devolución SPEI | Entrada/salida según el detalle; no es rendimiento ni capital externo acreditado |
| Comisión | Cargo operativo separado |
| IVA de comisión | Cargo operativo separado del ISR; no se repite por el resumen |
| Pago de interés explícito | Interés cobrado; si no existe, no se inventa rendimiento |
| Retención cero publicada | Evidencia de ISR cero, sin cargo monetario adicional |
| Saldo inicial/final | Ancla del período, no nueva aportación |

El uso habitual como banco de paso no autoriza a ignorar un interés que sí aparezca en otro estado histórico. Las tasas publicadas se conservan como metadatos, sin estimar intereses. La consulta **Comisiones e IVA** suma esos cargos operativos, mientras que **Interés menos ISR retenido** conserva su alcance específico; no representa una rentabilidad completa después de gastos.

## Controles

- Lectura específica y conciliada de débito, identidad de cuenta única y moneda nacional explícita. El símbolo dólar no identifica por sí solo la moneda; moneda ausente/contradictoria bloquea la confirmación.
- Cada movimiento debe tener sentido de entrada/salida determinado por el saldo y coincidir con el resumen. Se vuelven a cotejar apertura/cierre, aportaciones, retiros, interés, comisiones, IVA e ISR después de normalizar.
- Las fechas MM/DD se resuelven por el período interior, incluso cuando cambia el año. No se usa el nombre del archivo.
- Operaciones iguales en fecha/importe se conservan como evidencias distintas. Identificación por cuenta/documento/página/línea no prueba duplicidad económica entre archivos; períodos superpuestos se bloquean.
- Meses fuera de orden están admitidos. Meses consecutivos deben enlazar apertura/cierre sin ajustes; huecos permanecen visibles.
- Identidad ambigua, diferencias, dirección no reconocida o retención no nula sin detalle admitido bloquean la importación.
- La transacción y versión del plan son las mismas del libro existente: un fallo revierte documento, aprobación, movimientos y cobertura; repetir la confirmación no duplica cantidades.

## Alcance pendiente

Las aportaciones/reducciones quedan registradas, pero su origen no se supone externo ni propio. Falta enlazar transferencias con otras instituciones y acreditar el origen de efectivo/devoluciones. No se deduplican operaciones por coincidencia casual ni se infiere reinversión.

Se conserva ejecución local/offline sin nuevas dependencias, APIs o servicios obligatorios. Las pruebas usan documentos ficticios; el estado compartido se utiliza para validar generación del plan, sin confirmar contabilidad personal.
