# YoTePresto: apertura de efectivo y cobro documentado

La aplicación prepara un plan para el PDF textual reconocido. La confirmación registra una cuenta de efectivo de la plataforma, no una cuenta bancaria adicional. Cartera, tasas, acumulados y atrasos quedan como observaciones; no se suman como otro saldo o ingreso mensual.

## Acreditar la apertura

El estado distingue saldo global y disponible, pero este formato no publica la apertura de efectivo. La resta entre primer saldo operativo e importe de la primera fila genera únicamente un **candidato aritmético**. El saldo global inicial no lo reemplaza.

1. Subir o abrir el PDF. Si está protegido, proporcionar la contraseña para procesarlo y en **Desbloquear plan**; solo permanece en memoria y no se guarda en el plan/base.
2. Comprobar la apertura candidata con otras fuentes propias. Si se acredita, marcar **Verifiqué con mis fuentes la apertura de efectivo** y pulsar **Acreditar apertura de efectivo**. La app registra la declaración del usuario, no una cifra publicada por el estado ni una verificación automática de esas fuentes. Si no se puede acreditar, dejar el documento pendiente.
3. Revisar el plan y confirmar únicamente si todos los controles pasan.

Si ya existe el cierre del mes inmediatamente anterior confirmado, y coincide con el candidato, el plan puede usarlo como apertura enlazada. Un hueco temporal no habilita ese enlace. La revisión explícita queda vinculada a importe, documento, versión y huella del plan; no se convierte en preferencia global ni aportación. No elimina diferencias de continuidad o de otros controles.

## Desglose dentro del alcance

Esta primera integración admite un pago único enlazado por referencia a un préstamo abierto antes del período. El principal debe coincidir con saldo inicial menos saldo final de ese préstamo. Principal más interés/IVA mensuales deben coincidir con el pago completo, en su fecha publicada. No se reparte un agregado entre varias fechas o préstamos por proporción.

| Evidencia | Registro |
| --- | --- |
| Principal recuperado | Aportación a efectivo, con origen pendiente; no interés ni capital externo acreditado |
| Interés ordinario / moratorio | Interés cobrado en dos componentes con evidencia |
| IVA ordinario / moratorio | IVA recibido separado del interés |
| Fila única de retención | Desglose mensual en ISR retenido e IVA pagado, en la fecha de esa fila |
| Comisión con IVA | Un cargo, sin duplicar el desglose del resumen |
| Fondeo / retiro / préstamo | Aportación o reducción operativa con origen/contrapartida pendientes |
| Cartera, atrasos y acumulados | Observaciones, sin cobros o pérdidas adicionales |
| Ganancia del resumen | Control informativo de su base antes/después de retención, sin otro ingreso |

El ISR no publicado permanece desconocido y bloquea este alcance porque falta su desglose. Un cero publicado puede registrarse como evidencia de retención cero. Retención no determina el impuesto anual. Interés neto de ISR no equivale a ganancia después de IVA y comisiones.

## Controles y límites

- Se exigen ambas lecturas específicas y conciliación de resumen global, efectivo y cartera. Solo la incidencia concreta de apertura no publicada se resuelve mediante revisión/enlace; no se borran las demás alertas.
- Pagos múltiples, retenciones múltiples sin fecha única, referencias de préstamo ambiguas, principal incompatible, cancelaciones y conceptos no mapeados bloquean; no se genera un reparto supuesto.
- Moneda MXN publicada o revisada por documento. Una moneda extranjera/contradictoria no puede sobrescribirse. Fechas y signos publicados se conservan, sin ajustar fines de semana, importes o redondeos para cuadrar.
- La normalización vuelve a comprobar cierre de efectivo, interés, IVA recibido, ISR, IVA retenido y comisión. Aperturas/cierres son anclas documentales y no movimientos de capital nuevo.
- Solapamientos y saldos contiguos incompatibles bloquean. Se admiten meses fuera de orden; huecos visibles y reintentos idempotentes. Fallos revierten documento, aprobación, movimientos y cobertura en una transacción.

Quedan pendientes pagos múltiples con desglose por operación, cancelaciones, cartera contable por préstamo, reinversión, conciliación con otras cuentas, correcciones, fiscalidad anual e importación financiera desde imágenes. El OCR local conserva evidencia revisable. El libro muestra cierre de efectivo, no valor total del patrimonio.

Procesamiento local/offline con las dependencias existentes, sin APIs, servicios o pagos nuevos. Pruebas ficticias; no se confirma contabilidad personal en el chat. La institución Fintual conserva sus portafolios MXN/USD y no se crea una institución independiente con el nombre de su custodio.
