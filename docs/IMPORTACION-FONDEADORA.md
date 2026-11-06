# Fondeadora: cuenta operativa y moneda revisada

La confirmación financiera admite estados operativos completos, conciliados y del formato conocido. Los reportes de movimientos sin apertura/cierre se conservan como evidencia y permanecen bloqueados para esta importación. Un saldo operativo cero no acredita una Bóveda o cartera de inversión de valor cero.

## Flujo

1. Subir o abrir el PDF Fondeadora. La aplicación prepara el plan operativo.
2. Si el documento no publica moneda, seleccionar **Pesos mexicanos (MXN)** únicamente después de comprobarla, y pulsar **Aplicar revisión de moneda**. Si no se puede acreditar, elegir la opción pendiente y no confirmar.
3. Revisar los movimientos y advertencias. Confirmar el plan solo cuando esté listo; el libro mostrará una cuenta operativa, sin crear una cuenta adicional de inversión.

La revisión de moneda forma parte del plan aceptado, con su revisión documental y huella. No es una suposición derivada del símbolo `$`, no se aplica a otros archivos y no permite sobrescribir una moneda extranjera o contradictoria publicada. Se guarda al confirmar el lote; si se cierra el plan sin confirmar, no queda una decisión financiera registrada.

## Tratamiento

| Evidencia | Registro |
| --- | --- |
| Depósito/transferencia entrante | Aportación operativa con origen pendiente |
| Transferencia saliente | Reducción con contrapartida pendiente |
| Traspaso FONDEA/Apartado | Entrada/salida operativa y evidencia de destino pendiente; no crea saldo o contrato de Bóveda |
| Apertura/cierre | Anclas del período, sin nueva aportación |
| ISR cero publicado | Evidencia de retención cero, sin cargo adicional |
| Tasa/GAT vacío | Desconocido, distinto de cero publicado |
| Reporte sin saldos/interés/ISR | Evidencia parcial; campos ausentes permanecen desconocidos |

Un traspaso entre cuentas FONDEA no demuestra por sí solo que el destino pertenezca al titular. No se enlazan transferencias por coincidencia de importe ni se presupone capital externo, reinversión o beneficio por devolución de un Apartado. Las dos pestañas no generan una transferencia ficticia entre ellas.

## Controles y alcance

- Identidad/CLABE y período deben estar acreditados. El original se relee al confirmar; no se acepta la extracción genérica u OCR como aprobación financiera.
- El estado debe publicar apertura/cierre y una tabla de movimientos explícita. Una tabla vacía y conciliada es distinta de una tabla ausente.
- Se exige conciliación del lector y de la normalización: apertura más movimientos debe dar cierre, y depósitos/retiros coincidir con sus filas.
- Las fechas conservan su orden y período publicados. Una secuencia invertida se bloquea, sin reordenarla para cuadrar.
- Esta integración admite interés, ISR, comisiones y compras solo si el resumen publica cero; importes no nulos requieren mapeo específico de sus filas.
- Operaciones iguales legítimas conservan evidencia distinta. Solapamientos o diferencias de continuidad se bloquean; meses fuera de orden y huecos usan los controles del libro existente.
- Confirmar exige el mismo plan, moneda revisada y versión que se preparó. Fallos revierten documento/aprobación/movimientos/cobertura; reintentos no duplican.

Todavía faltan estados/contratos de inversión y su normalización de principal, rendimiento, retención y reinversión; el cierre operativo no los reemplaza. Imágenes, correcciones, formatos no conciliados y conciliación entre instituciones siguen pendientes de confirmación financiera.

Ejecución local/offline sin dependencias, APIs o pagos nuevos. Pruebas con documentos ficticios y revisión de comportamiento del reporte real, sin confirmar contabilidad personal. La interfaz de moneda se inspeccionó con una muestra ficticia; los envíos y la confirmación se probaron contra el servidor HTTP real.
