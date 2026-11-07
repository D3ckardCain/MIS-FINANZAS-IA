# Fintual: fondos en MXN

El lector PDF optativo compara cartera anterior/actual, valores, efectivo, pendientes, resumen de depósitos/retiros, operaciones y anexo de ISR/comisiones. No importa movimientos.

```bash
python -m finanzas.readers estado.pdf --institution fintual --lane investments --reconcile
```

La vista débito conserva el lector documental de ausencia de cuenta bancaria; no se inventa una cuenta adicional. Este lector específico corresponde a los estados de fondos en pesos mexicanos, no a estados de acciones USD de otro custodio.

## Qué separa

- Cantidad de participaciones, precio, costo promedio, valuación y variación publicada.
- Cartera anterior y actual, incluidos los casos con «No hay activos» y cero explícito.
- Depósitos/retiros externos de compras/ventas internas de participaciones.
- Comisión e IVA del movimiento frente al total de comisión del documento.
- ISR informativo, sin volver a descontarlo del efectivo por su sola presencia en un anexo.
- Rendimiento porcentual del período actual frente a la serie histórica, que puede contener NaN. NaN no significa cero.

«Variación» puede incluir movimientos de capital; no equivale automáticamente a interés cobrado. Una venta y el retiro posterior son pasos distintos, no dos rendimientos. Una valuación mayor no crea un cobro.

## Controles y límites

Las fechas internas determinan el período. Se contrastan valuaciones de filas, totales de valores/efectivo/pendientes, depósitos/retiros, comisión y la ecuación del efectivo. Se aceptan formatos monetarios reconocidos como $0,00 sin confundirlos con miles. Se conservan diferencias exactas, incluso de un centavo.

`detail_reconciled` corresponde al efectivo/movimientos; `reconciled` también exige coherencia de posiciones y totales. Ambos pueden diferir. `ready_to_import` permanece falso.

Se conserva el nombre impreso en la fila, sin homologar automáticamente nombres comerciales o series. La reconstrucción de lotes, títulos/precios por ejecución, liquidación, costo fiscal, cuentas/objetivos y transferencia a otras cuentas queda pendiente. La fecha de liquidación impresa dentro de un detalle no se convierte en otra operación.

Los meses sin movimientos deben declararlo explícitamente. Un corte anterior reproducido dentro del PDF no sustituye un estado completo faltante. La cobertura usa la misma cuenta identificada y deduplicación por archivo SHA-256.

PDF y OCR funcionan localmente. Las imágenes generan evidencia para revisión, sin heredar conciliación PDF. Los originales e informes del titular se mantienen privados. No se importan datos de Excel ni se calcula declaración anual.


## Confirmación desde la aplicación

La aplicación incorpora un [plan de efectivo revisable](IMPORTACION-FINTUAL.md), con posiciones y resumen como observaciones separadas. La confirmación no convierte valuación o rendimiento porcentual en interés cobrado ni descuenta de nuevo el ISR informativo. El libro distingue «Efectivo del portafolio» y mantiene retención/neto de efectivo desconocidos hasta acreditar su atribución. PDF protegido con contraseña transitoria admitido, sin guardarla.


## Institución y portafolios

Fintual incluye fondos MXN y acciones USD como portafolios separados. Los estados con formato Alpaca se registran bajo Fintual; Alpaca solo figura como custodio/perfil técnico. Ver [Fintual USD](IMPORTACION-ALPACA.md). No se fusionan saldos o movimientos de monedas distintas.
