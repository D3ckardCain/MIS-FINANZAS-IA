# Nu: resumen consolidado y evidencia de Cajitas

El lector optativo revisa el resumen global y conserva por separado evidencia de cuenta operativa, Cajitas y crédito con garantía. Esta etapa no reconstruye todavía el libro por cada Cajita ni confirma movimientos económicos.

```bash
python -m finanzas.readers estado.pdf --institution nu --lane debit --reconcile
python -m finanzas.readers estado.pdf --institution nu --lane investments --reconcile
```

## Estados de verificación independientes

`summary_reconciled` comprueba la ecuación global, bruto menos retención y neto de portada frente al anexo. La distribución de saldos se verifica aparte en `composition_issues`. La consola muestra ambos estados.

`detail_reconciled` permanece falso mientras falten cierre por Cajita/garantía y pareo económico de traspasos. Por ello `reconciled=False` y `ready_to_import=False` en esta etapa, aunque el resumen cuadre. No se presenta una extracción documental como contabilidad lista para guardar.

## Qué conserva

- Saldo global inicial/final, depósitos, gastos con signo original, comisión y rendimiento neto.
- Interés bruto, retención publicada y texto/porcentaje de las etiquetas de interés e ISR. No se recalcula impuesto usando esas etiquetas ni se presupone que una tasa describa todos los contratos congelados.
- Saldo en cuenta, Cajitas y garantía cuando se publican. Una sección ausente queda no informada, distinta de cero.
- Disponible y congelado como componentes de Cajitas, sin sumarlos otra vez al patrimonio.
- Filas por sección con fecha, descripción, candidatos de importe, fecha futura explícita y página/línea. Un congelamiento no es un ingreso y un importe ausente/ambiguo no se convierte en cero.

Las diferencias de distribución se conservan sin ajuste ni explicación fiscal inventada. Un saldo de garantía no es un límite de crédito adicional disponible para invertir.

## Identidad y movimientos internos

Las dos vistas comparten documento y cuenta. La vista débito expone filas operativas y la vista inversiones evidencia de Cajitas/garantía. El mismo traspaso puede tener dos representaciones: no se suman como dos aportaciones externas.

Los IDs de evidencia son huellas de archivo/página/línea, no IDs económicos de operación. No permiten deduplicar automáticamente capturas o documentos distintos. La conciliación de cada Cajita y la reconstrucción de referencias/fragmentos entre páginas permanecen pendientes.

El interés se reconoce una sola vez cuando se incorpore el libro. Que permanezca invertido no crea otro rendimiento ni aportación externa. Las fechas de descongelamiento no prueban cuánto es principal/interés sin datos suficientes. Los datos de tarjeta/garantía se conservan como contexto del dinero invertido, sin crear un módulo de presupuesto o deuda de tarjeta.

## Límites

La cobertura usa períodos internos y duplicados binarios; no rellena huecos con tasas, proyecciones o Excel. Los GAT se conservan como publicados y los campos ausentes como desconocidos. No calcula declaración anual, exenciones o acreditamientos.

PDF y OCR funcionan localmente con las dependencias existentes. Las imágenes no heredan verificaciones del PDF. No se importan datos reales ni Excel, ni se añaden APIs de pago. Los documentos y los informes del titular siguen siendo privados.
