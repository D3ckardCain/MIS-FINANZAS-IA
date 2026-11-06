# Mifel: de la lectura al libro financiero

La cuenta a la vista remunerada tiene dos vistas de consulta y una sola identidad financiera. La aplicación no suma el saldo dos veces ni crea una transferencia entre sus pestañas.

## Uso

1. Subir o abrir un PDF Mifel del formato admitido. El plan financiero se prepara automáticamente.
2. Revisar el período, la apertura/cierre, los movimientos, los pares de interés/ISR y las advertencias.
3. Pulsar **Confirmar importación** si el plan está listo. **Libro financiero** mostrará una sola fila de cuenta remunerada Mifel, con su fecha de cierre, interés, ISR y diferencia entre ambos.

La revisión documental de las pestañas y la confirmación financiera siguen siendo acciones distintas. Una foto puede extraerse con OCR, pero todavía no autoriza esta confirmación financiera.

## Qué se registra

| Dato del estado | Tratamiento |
| --- | --- |
| Cuenta remunerada en ambas vistas | Una cuenta, un período y un solo lote de movimientos |
| Pago de intereses | Interés bruto en la fecha de cobro publicada |
| ISR retenido | Cargo separado, una sola vez por fila; no se repite por el resumen o grupo de rendimiento |
| Interés menos retención | Dato calculado para consulta; no crea un tercer movimiento |
| Transferencia SPEI recibida/enviada | Aportación/reducción con origen pendiente, sin atribuir capital externo o traspaso propio sin evidencia |
| Saldo inicial y final | Anclas documentales, sin convertir apertura en aportación |
| Rango remunerado | Se conserva aparte de la fecha del cobro, aunque alcance el mes siguiente o un fin de semana |
| Tasa, GAT y saldo promedio | Metadatos históricos publicados, sin reconstruir condiciones ausentes |

Los grupos de cobro conservan referencias del interés/retención, importe bruto, ISR, neto y días remunerados en el plan aceptado. El ledger conserva cada movimiento y su evidencia. Los folios se acotan a cuenta/período: no se presupone que sean únicos para todos los años.

El ISR explícito cero se conserva como cero documentado. Un pago de interés explícito de importe cero se conserva como observación, sin crear un movimiento de efectivo inválido. Un campo ausente no se transforma en cero.

## Controles

- El original se vuelve a leer al confirmar. Ambas vistas deben tener extracción específica y el lector debe conciliar resumen, columnas, saldos y referencias.
- La normalización vuelve a comprobar cierre, interés bruto y retenciones.
- Períodos superpuestos se bloquean. Meses fuera de orden están admitidos, pero las aperturas y cierres de meses consecutivos deben coincidir.
- Comisiones/IVA no nulos, otros productos con saldo, conceptos desconocidos o diferencias documentales requieren mapeo adicional; no se ajustan importes para cuadrarlos.
- El mismo mecanismo de Openbank garantiza versión del plan, reintentos idempotentes y transacción completa: un fallo no deja aprobación o movimientos parciales.

El libro distingue instituciones y cuentas por su identidad. Mifel puede coexistir con Openbank en la misma base sin fusionar cuentas, ingresos o retenciones. Las cantidades consultadas corresponden a los períodos importados, no a toda la historia ni al saldo de mercado actual.

## Pendiente

Relacionar SPEI con otras instituciones, acreditar origen de capital, resolver correcciones/solapamientos y extender confirmación a otros productos/imágenes. No se infiere reinversión por mantener el interés en la cuenta, ni se calcula el ISR definitivo del SAT.

No hay nuevas dependencias ni llamadas externas: se conserva operación local/offline y sin pagos obligatorios. Pruebas con documentos ficticios; el PDF compartido sirve para validar la generación del plan, sin confirmar movimientos personales.
