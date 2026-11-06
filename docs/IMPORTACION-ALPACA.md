# Alpaca: efectivo USD, dividendos y retención extranjera

La aplicación prepara el plan del estado mensual textual del formato admitido. Confirmar registra **una cuenta de efectivo USD del portafolio**. Acciones/ETF, cantidades, precios, costo, plusvalías y resultados reportados quedan como observaciones; todavía no se crea una cartera contable por lotes.

## Uso

1. Subir o abrir el PDF. Si está protegido, introducir su contraseña al procesarlo y en **Desbloquear plan** para releer el original financiero. Solo permanece en memoria durante la revisión; no se guarda en el plan/base y se elimina al abandonar/confirmar.
2. Revisar efectivo, ingresos, cargos y observaciones de posiciones/operaciones. El perfil requiere moneda USD acreditada por la posición de efectivo. No convierte importes a MXN ni suma monedas distintas.
3. Confirmar cuando no haya bloqueos. La app verifica otra vez original, revisión y estado del libro, y guarda el lote completo en una transacción.

## Tratamiento

| Evidencia | Registro |
| --- | --- |
| Compra / venta | Reducción / aportación de efectivo, con origen/base pendientes |
| Dividendos | Ingreso por dividendo, separado de interés y capital |
| Intereses | Ingreso por interés desde su fila |
| NRA withholding | Retención extranjera, separada del ISR mexicano |
| Comisión de compraventa | Gasto contrastado con Cost and Fees, sin incluirlo dos veces en el importe de operación |
| Cargo de Fees | Gasto desde su fila y controlado con Subtraction, distinto de la comisión de operación |
| Memopost con importe y comisión cero | Observación sin movimiento de efectivo |
| Posiciones/costo/plusvalías/resultados | Observaciones, sin ingreso adicional ni ganancia realizada calculada |
| Acumulados del año | Información separada; no vuelve a registrarse como ingreso mensual |
| Apertura/cierre de efectivo | Anclas del período, sin aportación mensual ficticia |

El libro muestra **Efectivo del portafolio**, unidad USD y cierre por fecha. No es el valor de mercado de acciones más efectivo ni un total patrimonial actual. Las dos vistas comparten evidencia y no crean dos cuentas. Una venta aporta efectivo sin convertir todo su importe en ganancia o capital externo acreditado.

## Impuestos e ingresos

Dividendos e intereses se conservan separados. La retención extranjera afecta al efectivo USD y tiene su propia categoría; no se transforma en ISR mexicano, acreditamiento o impuesto anual calculado. Un cero explícito extranjero conserva evidencia sin generar un cero de ISR mexicano.

La consulta muestra dividendos, retención extranjera e ingresos menos esa retención. Este último importe no descuenta todas las comisiones ni determina el resultado fiscal. La retención mexicana y su neto permanecen desconocidos; no se asignan tipos de cambio supuestos.

## Controles y límites

- Se requieren las dos lecturas específicas, las secciones reconocidas y conciliación completa. Guiones monetarios permanecen desconocidos; no se convierten en cero para cerrar ecuaciones.
- Efectivo de Holdings debe coincidir con Ending Value. Se comprueban cierre normalizado, Addition, Subtraction, Trade Transaction y Cost and Fees; discrepancias o comisiones de operación desconocidas bloquean.
- Memopost con efecto monetario desconocido/no nulo, ingreso negativo, devolución de impuesto extranjero, conceptos nuevos, posiciones cortas, opciones o renta fija fuera del alcance bloquean el lote.
- Se conservan fechas, símbolos, descripciones y evidencia por página/línea/componente. Operaciones iguales legítimas no se deduplican por importe o símbolo. No se calculan costo fiscal, lotes ni ganancia realizada desde el resumen.
- Solapamientos y diferencias de continuidad de efectivo bloquean. Se admiten meses fuera de orden, con huecos visibles. Reintentos no duplican; fallos revierten documento, aprobación, movimientos y cobertura.

Quedan pendientes contabilidad de cantidades/costo por lote, continuidad histórica de posiciones, atribución fiscal mexicana, conversión documentada a MXN, transferencias externas/contrapartidas, reinversión, correcciones y confirmación financiera desde imágenes. El OCR local continúa disponible como evidencia revisable.

Procesamiento local/offline después de instalar las dependencias existentes. Sin servicios, APIs o pagos nuevos. Pruebas exclusivamente ficticias, sin confirmar movimientos personales ni publicar documentos del titular.
