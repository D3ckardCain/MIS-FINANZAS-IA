# Doopla: efectivo, pagos y cartera

El lector PDF optativo conserva el resumen de valor de cuenta, el efectivo disponible, los movimientos, el anexo de inversiones y los registros de atraso/cobranza. Funciona localmente con las dependencias PDF existentes, sin nuevas APIs ni servicios.

```bash
python -m finanzas.readers estado.pdf --institution doopla --lane investments --reconcile
python -m finanzas.readers estado.pdf --institution doopla --lane debit --reconcile
```

La vista débito muestra la perspectiva del efectivo de la plataforma, no una cuenta bancaria adicional. Ambas vistas comparten cuenta y evidencia; no se suman como posiciones independientes.

## Qué separa

- Pagos: devolución de principal, interés, IVA y total, conservando los guiones como componentes no informados.
- Depósitos y retiros: movimientos de fondos, cuyo origen/destino requiere contrastar otras cuentas; no se asumen ingresos o gastos personales.
- Inversión y cancelación: movimientos internos entre efectivo y préstamos. El resumen puede publicar inversiones netas; se conserva también cada importe bruto.
- IVA ordinario, IVA moratorio, retención ISR y comisión Doopla: cargos separados de los intereses y del principal.
- Comisión e IVA de comisión: el resumen los desglosa; el detalle puede agruparlos en un solo cargo. No volver a cargar ambas representaciones.
- Cartera: importes invertidos, pagos acumulados, intereses acumulados, IVA acumulado, capital recuperado y pendiente. No se suman como cobros mensuales.
- Atrasos: alias, estatus, días y acción de cobranza, sin convertir automáticamente el capital en pérdida.

## Conciliación por partes

`cash_reconciled` verifica la ecuación del efectivo, la suma de movimientos y los subtotales de ingresos, egresos, recompensas e inversiones netas. No afirma que concilien las otras secciones.

`detail_reconciled` también exige que los componentes publicados de cada pago coincidan con su total. Las diferencias de un centavo se conservan, con página/línea e importes originales; no se redondean para ocultarlas.

`reconciled` exige además ecuación del valor de cuenta, resumen frente a movimientos, totales de cartera frente a filas y capital pendiente más efectivo frente al valor final. Una sección correcta no compensa otra pendiente. El lector mantiene `ready_to_import=False`: extraer no confirma movimientos. La aplicación dispone de un [plan financiero separado](IMPORTACION-DOOPLA.md) para efectivo por componente y cartera observada, con confirmación explícita y atómica.

La consola muestra por defecto estados, cantidades de filas/diferencias y problemas, sin importes ni alias. `--details` incluye datos sensibles; usarlo únicamente en un entorno privado.

## Formatos e incertidumbre

El lector preserva el signo publicado del IVA de intereses, que puede variar entre formatos. Contrasta por separado esa presentación y el cambio patrimonial que resulta de los movimientos; no cambia etiquetas para hacer coincidir resultados ni define su interpretación fiscal.

ISR ausente se guarda como `None`, distinto de cero explícito. No calcula impuestos finales, tasas fiscales ni acreditamientos anuales. Tampoco reconstruye tasas de préstamos a partir de pagos aislados.

El valor de una fila de cartera puede diferir del total del anexo. Se preservan ambos y se registra la diferencia, sin sustituir el capital pendiente por una cifra calculada. La cartera acumulada no acredita por sí sola un corte histórico fiable.

`review_doopla_documents` revisa cobertura, duplicados binarios, continuidad del valor de cuenta y continuidad del efectivo. Al repetirse las cifras económicas del anexo entre meses consecutivos con movimientos de capital, solicita revisar su vigencia. Es una señal documental, no una conclusión sobre la causa.

## Límites e identidad

Los movimientos de estos formatos no aportan un ID de operación único. Alias, fecha e importe pueden repetirse legítimamente: no se fusionan ni se eliminan filas por esa coincidencia. Se conserva archivo SHA-256 y página/línea para revisión. Falta resolver identidad económica antes de importar y enlazar transferencias propias.

Se reconocen tablas de disposición fija con fechas DD-MM-AAAA e importes del formato documentado. Filas o signos inesperados quedan pendientes. Los PDF escaneados se deben revisar mediante el lector de imagen/OCR existente; una imagen no hereda conciliación PDF. La interfaz admite confirmación dentro del alcance del manual; no se han guardado movimientos reales. La moneda ausente requiere revisión MXN por documento y el PDF protegido usa contraseña temporal sin guardarla.
