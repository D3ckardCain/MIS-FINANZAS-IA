# Traspasos propios entre cuentas confirmadas

## Uso

1. Abre **Libro financiero → Traspasos entre tus cuentas**.
2. Selecciona la reducción de origen y una aportación compatible en destino. Se muestran institución, importe/unidad, fecha, descripción/referencia publicada y acceso a ambas evidencias.
3. Contrasta los documentos y marca que verificaste la propiedad de ambas cuentas y del dinero. Una coincidencia de importe no demuestra propiedad.
4. Pulsa **Preparar vínculo propio**, revisa el plan y confirma el traspaso. Cambiar la selección elimina el plan y desmarca la acreditación.

Los candidatos usan movimientos de capital pendientes con semántica de transferencia, depósito o retiro documentada. Compras/ventas de valores, principal de pagos de préstamos, interés, comisiones, cashback y movimientos ya vinculados quedan excluidos. Cuando una referencia no está publicada se indica; no se inventa.

## Efecto en el libro

La cuenta origen conserva su reducción y la cuenta destino su aportación. Ambas pasan de origen pendiente a **transferencia propia**, con un vínculo común. No se añaden movimientos, aportaciones externas ni ingreso; cantidades, unidades y las dos fechas originales se conservan. No se exige que ambas fechas sean iguales ni se desplazan fines de semana.

Este incremento admite una pareja completa de igual importe y moneda entre cuentas distintas. Varias entradas iguales se presentan como opciones separadas; ninguna se escoge automáticamente. Diferencias por comisiones, transferencias parciales, una salida contra varias entradas, conversiones de moneda y dinero en tránsito sin contraparte no se ajustan ni se concilian por aproximación.

## Revisión y auditoría

El plan queda ligado a las versiones de ambos movimientos y al estado del libro. Una nueva importación/corrección exige prepararlo de nuevo. El vínculo y ambas correcciones se guardan en una única transacción SQLite: cualquier fallo revierte todo. Reintentar o reabrir no duplica vínculos ni movimientos; una pata no puede usarse en dos traspasos.

Los lotes documentales originales permanecen congelados para auditoría. El libro vigente incorpora las revisiones de origen. La evolución reconoce el origen conciliado sin marcar una falsa diferencia de efectivo, siempre que exista el acta de vínculo y no hayan cambiado los datos financieros/evidencia. Una modificación posterior de fecha, cuenta, importe, moneda o evidencia señala el vínculo y el período para revisión, incluso si los dos lados todavía suman cero.

No es un mecanismo para reclasificar libremente capital, inventar reinversión o cambiar movimientos de compra/venta/préstamo. Tampoco se deshace automáticamente una conciliación ya confirmada; cualquier corrección posterior permanece trazada y señalada.

## Operación local y pruebas

Funciona sin Internet con el servicio local iniciado. No añade paquetes, servicios ni pagos. La consulta y los planes leen una instantánea consistente. Se reutilizan las restricciones HTTP locales y las revisiones del ledger; la tabla `book_transfer_links` conserva la acreditación del vínculo.

Once pruebas nuevas con documentos ficticios verifican candidatos sin asignación automática, propiedad explícita, dos fechas/importe conservados, exclusiones, moneda, varias entradas iguales, plan/versiones, rollback, reintento/reapertura, evolución y correcciones posteriores; flujo HTTP incluido. El navegador de CI prueba selección, acreditación, plan, confirmación, evolución y ancho móvil. Ningún dato personal se importa.


## Validación publicada

[688 pruebas y flujos Chrome aprobados](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42330762816). Capturas ficticias revisadas en escritorio y móvil. Los datos de prueba no corresponden a movimientos del titular.
