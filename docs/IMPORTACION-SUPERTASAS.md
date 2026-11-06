# SuperTasas: efectivo y observaciones de plazo

La aplicación prepara el plan al abrir un PDF textual del formato admitido. La confirmación guarda **una cuenta de efectivo a la vista**, sus movimientos y las observaciones de posiciones a plazo dentro del plan aceptado. No confirma todavía una cartera contable de contratos ni calcula el patrimonio total.

## Uso

1. Subir el PDF. Si está protegido, introducir la contraseña para procesar su lectura documental.
2. Preparar el plan. En un PDF protegido, pulsar **Desbloquear plan** con la contraseña para releer el original. Si la moneda no está publicada, revisar expresamente si corresponde a MXN; no deducirla del símbolo dólar o de la etiqueta del rendimiento.
3. Revisar efectivo, advertencias y **Posiciones a plazo · observaciones documentales**. Solo puede confirmarse cuando todos los controles pasan.

La contraseña permanece únicamente en memoria durante la revisión; no forma parte del plan, la base de datos ni el historial. Se solicita de nuevo después de abrir otro documento, abandonar la vista o recargar la aplicación. El original cifrado permanece intacto. La confirmación vuelve a releerlo y exige la misma revisión y huella del plan. Las decisiones de moneda sí se conservan en el plan aceptado, vinculadas a ese documento; nunca sobrescriben una moneda contradictoria publicada.

## Tratamiento

| Evidencia | Registro |
| --- | --- |
| Abono o retiro de efectivo | Aportación o reducción, con origen/contrapartida pendientes |
| Apertura de inversión a plazo | Reducción de efectivo; no se presume dinero externo, reinversión ni un contrato contable confirmado |
| Devolución de principal | Aportación de principal al efectivo, sin clasificarlo como ganancia |
| Rendimiento de cuenta a la vista | Interés cobrado de su fila, una sola vez |
| Retención cero publicada a la vista | Evidencia de cero para ese producto; no declara ISR cero de todas las inversiones |
| Posición a plazo vigente | Observación fechada: principal, apertura, vencimiento, plazo, tasa, GAT y proyecciones |
| Interés y retención proyectados | No generan cobros ni impuestos efectivamente retenidos |
| Apertura/cierre de efectivo | Anclas documentales; no aportaciones mensuales ficticias |

Los abonos ya incluyen los intereses pagados: el resumen no genera un segundo ingreso. Las dos vistas comparten evidencia de efectivo y no se suman como cuentas distintas. Una posición repetida en el siguiente mes es otra observación de condiciones, no una nueva compra o ganancia. Su huella calculada no equivale a un identificador contractual emitido por la institución.

## Controles

- Se requieren ambas lecturas específicas, apertura/cierre y conciliación de efectivo y posiciones. Un saldo inicial vacío queda desconocido y bloquea; no se deriva de las demás cifras.
- Cada saldo corriente, abono/cargo y cierre debe coincidir, antes y después de normalizar. Fechas fuera del período, invertidas, columnas incorrectas, conceptos no mapeados y posiciones contradictorias bloquean el lote completo.
- Por ahora la retención, comisiones e IVA de los resúmenes deben ser cero. Importes no nulos requieren mapeo documental específico.
- Un cobro a plazo sin desglose acreditado de bruto/retención bloquea la confirmación. La palabra «exento» se conserva como descripción y no se usa para declarar un impuesto cero o definitivo.
- Solapamientos y diferencias entre saldos de meses contiguos bloquean. Se admiten meses fuera de orden; los huecos permanecen visibles. Reintentos no duplican; un fallo revierte documento, aprobación, movimientos y cobertura en una transacción.

## Alcance pendiente

El libro muestra el cierre de **efectivo** por fecha, no efectivo más capital a plazo ni valor actual de mercado. Las observaciones de contratos se consultan desde el documento confirmado; todavía no se consolidan como cartera histórica de contratos. Sus cambios no se resuelven ni fusionan automáticamente.

Faltan pagos de interés a plazo con clasificación fiscal acreditada, retenciones/comisiones no nulas, vínculos entre cuentas, reinversiones confirmadas, correcciones e importación financiera desde imágenes. El OCR local sigue disponible como evidencia revisable. Retención y proyección no determinan el impuesto anual.

El procesamiento es local y funciona sin conexión después de instalar las dependencias existentes. No añade servicios, APIs, tarjeta o pagos obligatorios. Las pruebas son ficticias; la muestra real solo se usa para comprobar que sus cobros sin desglose suficiente quedan bloqueados, sin confirmar contabilidad personal.
