# Alpaca: acciones/ETF y efectivo USD

Se incorpora un perfil documental con dos vistas y OCR local, más lector PDF optativo de revisión detallada. Ambas vistas corresponden a una única cuenta de corretaje; su efectivo no es otra posición ni una cuenta bancaria inventada.

```bash
python -m finanzas.readers estado.pdf --institution alpaca --lane investments --reconcile
python -m finanzas.readers estado.pdf --institution alpaca --lane debit --reconcile
```

## Magnitudes independientes

- Cash Summary: período actual y acumulado anual, sin sumar ambas columnas.
- Account Summary y Holdings: participaciones, precios, valor de mercado, costo publicado y plusvalía no realizada.
- Income: dividendos, intereses y retenciones extranjeras como filas independientes.
- Transaction: compras/ventas con cantidad de participaciones y signo de efectivo, distintos de cantidades informativas de Memopost.
- Realized Gain/Loss: resultado publicado separado de la venta bruta y de plusvalías no realizadas.
- Fees: cargos publicados, sin asumir comisión cero cuando aparece un guion.

La moneda permanece USD y las fechas de operación se interpretan MM/DD/AAAA. El encabezado Period: MONTH - YEAR determina el mes completo. No se convierten importes a MXN sin tipo de cambio, fecha y regla definidos.

## Incertidumbre y conciliación

El símbolo «--» se guarda como `None`. No se convierte en cero ni se crean movimientos para cerrar una ecuación. Los campos numéricos existentes pueden comprobarse sin afirmar que todo el documento concilia.

El lector verifica las secciones obligatorias, fechas, tipos de operación, signo/cantidad de compraventas, moneda de efectivo, ingresos y operaciones frente al resumen. Comprueba ecuaciones solo cuando todos sus términos son numéricos publicados. Se mantiene `ready_to_import=False` incluso si una fuente sintética concilia.

Una entrada/salida agregada sin detalle suficiente requiere referencias y contrapartida. Los Memopost conservan evidencia y referencias partidas, pero su cantidad no es efectivo abonado ni cantidad de acciones. No se compensan importes faltantes mediante estas filas.

## Pendientes

No hay identidad económica única por ejecución, reconstrucción general de lotes, acciones corporativas ni motor fiscal. Símbolo, fecha e importe pueden repetirse legítimamente. No se deduplican operaciones por esa coincidencia.

La retención extranjera se registra en USD y separada del ISR bancario mexicano; no se determina su acreditamiento ni impuesto anual. Las notas legales generales no se convierten en tasas/cargos aplicados al titular.

La ausencia de acciones en Holdings no acredita cierre de cuenta ni ausencia histórica de movimientos. Los campos vacíos o guiones requieren revisión; las imágenes pasan por OCR sin heredar conciliación PDF. No se han importado estados reales ni datos de Excel.
