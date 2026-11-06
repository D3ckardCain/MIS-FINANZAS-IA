# Fondeadora: cuenta operativa y evidencia de inversión

El lector PDF optativo reconoce estados de cuenta y reportes de movimientos de los formatos observados. Conserva el emisor impreso Fondea Technologies o Apoyo Múltiple y la identidad de la cuenta, sin inferir relaciones jurídicas por el nombre comercial.

```bash
python -m finanzas.readers estado.pdf --institution fondeadora --lane debit --reconcile
python -m finanzas.readers estado.pdf --institution fondeadora --lane investments --reconcile
```

## Dos alcances

La vista débito revisa efectivo operativo. La vista inversiones conserva candidatos de traspasos internos y Apartados, con `scope=investment_transfer_evidence` e `investment_balance=None`. No representa un lector completo de estados de Bóveda ni usa el saldo operativo como capital invertido.

El origen de la evidencia es la cuenta operativa identificada. El destino de un traspaso sigue pendiente hasta identificar la inversión correspondiente; no se crean productos ni cuentas nuevas por una descripción.

## Formatos y campos no informados

- Estado de cuenta: saldo inicial/final, compras, depósitos, retiros, comisiones, interés y retención de la cuenta operativa. Puede incluir una tabla de cargos, abonos y saldo.
- Reporte de movimientos: depósitos/gastos y, cuando consta, una tabla de cantidades firmadas. No informa necesariamente saldos, interés, retención o tasas; esos campos se mantienen como `None`.
- Un campo porcentual vacío se conserva desconocido. Un porcentaje explícito de cero se conserva como cero, sin aplicarlo a una Bóveda.
- Un documento con solo resumen no demuestra ausencia de traspasos internos o inversiones. Una tabla presente y vacía se distingue de una tabla no incluida.

## Conciliación

Se verifican las fechas internas, la CLABE, las columnas monetarias, los saldos corrientes y los conceptos publicados del resumen. Los reportes permiten contrastar depósitos/gastos identificables, pero no cerrar un saldo que no publican.

Los traspasos internos reducen/aumentan la cuenta operativa. Los conceptos de Apartado pueden ser abonos o cargos; no se trata un abono completo como interés ni una cancelación como aportación externa. No se deduce rendimiento ni reinversión por la diferencia entre dos importes aislados.

Una secuencia de detalle puede conciliar aunque el resumen omita un concepto. Se conservan ambas representaciones y la diferencia exacta, sin ajuste ficticio. La vista inversiones nunca queda conciliada como posición de inversión con estos documentos operativos. Ningún resultado habilita importación automática.

La cobertura deduplica archivos SHA-256 y comprueba fechas. Solo compara continuidad de saldo cuando cierre y apertura están informados; dos valores desconocidos no se cuentan como coincidencia. Un mismo mes puede estar cubierto por un reporte limitado sin disponer del estado detallado de la inversión.

## Extracción y límites

Algunos PDF presentan espacios de fuente dentro de palabras, números y porcentajes. Se normalizan solo campos reconocidos, preservando el original y página/línea. Las fechas de extracción estándar se contrastan con las de disposición visual cuando ambas son legibles. No se aplica una eliminación global de espacios a las descripciones económicas.

No hay ID económico único por operación. No se deduplican filas por importe/fecha ni se enlazan cuentas por coincidencia de titular. Faltan contratos/estados de inversión para principal, fechas de vigencia/vencimiento, tasa, reinversión, rendimiento y retención de Apartados/Bóvedas.

El OCR local sigue disponible para ambas vistas y no hereda conciliación PDF. Los originales y los informes privados no se publican. Sin APIs nuevas, costos obligatorios, importación de Excel ni cálculo fiscal anual.

## Confirmación en la aplicación

Los estados operativos completos y conciliados se conectan al ledger mediante un plan, con revisión expresa de moneda cuando no está publicada. Los reportes sin saldos, los datos de Bóveda y los conceptos monetarios aún sin mapeo no se confirman por suposición. Ver [manual de importación operativa Fondeadora](IMPORTACION-FONDEADORA.md).
