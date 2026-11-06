# DiDi Cuenta: resumen y movimientos

El lector optativo de conciliación admite los dos formatos PDF reconocidos de DiDi Cuenta / J.P. Sofiexpress. Usa las fechas internas y verifica la cuenta en las páginas. El lector documental y el OCR local siguen disponibles.

```bash
python -m finanzas.readers archivo.pdf --institution didi --lane investments --reconcile
python -m finanzas.readers archivo.pdf --institution didi --lane debit --reconcile
```

Ambas vistas representan una misma cuenta: comparten huella y referencias. No deben sumarse como dos cuentas ni duplicarse en el consolidado. El lector no escribe en la base de datos ni habilita importación automática.

## Controles

- Extrae el resumen mediante disposición de columnas/filas del PDF. El orden del texto plano de las etiquetas no siempre coincide con el de los importes.
- Conserva saldo inicial, depósitos, retiros, promedio, rendimientos, retención y cierre por separado.
- Los depósitos del resumen incluyen los rendimientos: no se suman nuevamente como aportación.
- Separa créditos por rendimiento y transferencias pendientes de vincular. Una entrada no implica dinero externo nuevo; falta contrastar la contrapartida.
- Comprueba cada saldo corriente, las fechas, el cierre y los totales de depósitos, retiros y rendimientos.
- Reconstruye referencias CBS/SNCBS partidas entre líneas o páginas, sin usar CLABE ni datos del remitente como identificadores de operación.
- Conserva página/línea de inicio de cada movimiento, huella SHA-256 del archivo y huella de cuenta compartida entre vistas.
- Mantiene referencias ausentes/repetidas, filas desconocidas y diferencias como revisión pendiente; no descarta evidencia ni inventa ajustes.

## Tasas y retención

Conserva el texto de tasas, topes, GAT y fecha de cálculo/actualización, más las tasas anuales publicadas en ese documento. Esa fecha no se convierte en inicio de vigencia contractual. No aplica tasas actuales a períodos anteriores ni deriva una tasa diaria a partir de un abono agrupado.

La retención explícita de cero es un dato conocido. Una retención distinta de cero requiere ampliar y validar su desglose antes de dar el documento por conciliado. No se calcula el ISR anual definitivo.

## Límites

El formato reconocido requiere detalle con fecha completa, tipo Depósito/Retiro, importe/saldo MXN y referencias CBS/SNCBS. Otros formatos, comisiones o categorías quedan pendientes si no cuadran o no se reconocen. Un período sin filas requiere revisión; no se presume que no hubo actividad. No se recalcula el saldo promedio a partir de fechas de pago, que pueden agrupar varios días.

Las imágenes pasan por OCR y revisión, sin heredar conciliación del lector PDF. Los originales privados y los informes financieros no se publican. El lector funciona localmente con las dependencias PDF existentes, sin APIs externas.

## Confirmación en la aplicación

Los dos formatos textuales conciliados ya se conectan al ledger. Se conserva una cuenta compartida, se separa el interés incluido en depósitos y se guardan condiciones históricas. Ver [manual de importación DiDi](IMPORTACION-DIDI.md). Imágenes y formatos con retención no nula permanecen pendientes de confirmación financiera.
