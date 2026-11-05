# Nu: cuenta, Cajitas y garantía

El lector local separa ambas vistas y construye cambios por Cajita, movimientos de congelamiento y contrapartes documentales. Los saldos y rendimientos que el documento no desglosa quedan pendientes de evidencia, sin ajustes inventados.

```bash
python -m finanzas.readers estado.pdf --institution nu --lane debit --reconcile
python -m finanzas.readers estado.pdf --institution nu --lane investments --reconcile
```

La salida habitual contiene estados, conteos e incidencias. `--details` incluye información financiera sensible, las filas y `detail_review` con los asientos de cambio y sus parejas.

## Verificaciones independientes

- `summary_reconciled`: ecuación global, bruto menos retención y neto de portada/anexo.
- `composition_issues`: Cuenta + Cajitas + garantía frente al total, y disponible + congelado frente a Cajitas.
- `detail_reconciled`: fechas, importes, conceptos/signos, contrapartes internas, neto externo y disponibilidad del desglose para cerrar subcuentas.
- `reconciled`: exige que pasen todos los controles anteriores. Un estado explícitamente vacío y con ceros puede conciliar; eso no habilita importación.
- `ready_to_import`: siempre falso; este módulo entrega una revisión, no guarda movimientos financieros.

Se preservan las diferencias exactas. Una sección ausente es desconocida, no cero. Congelado es parte de Cajitas y no se suma otra vez al patrimonio. El saldo en garantía es dinero del titular; no se confunde con el límite de crédito.

## Lectura y procedencia

Se reconocen fechas completas, años impresos en la siguiente línea y fechas sin año cuando el período interno proporciona un único año. Las filas fuera del período quedan señaladas. Las descripciones y claves SPEI que continúan en la siguiente página se conservan junto a la evidencia inicial de página/línea. Se omiten encabezados, pies y páginas legales.

La Cajita se identifica por su nombre explícito normalizado, conservando la descripción original. No se corrigen nombres, se fusionan Cajitas renombradas ni se deducen propietarios externos. La clave de rastreo se conserva, incluso si una operación y su devolución usan la misma clave: ambos signos permanecen.

## Asientos y traspasos

`preview.detail_review` o `review_nu_document(preview)` entrega:

- `postings`: cambios de cuenta, disponible por Cajita, congelado por Cajita y garantía, con ID de evidencia.
- `pairs`: contraparte documental única entre cuenta y Cajita/garantía. Exige concepto explícito de depósito/retiro, mismo nombre, misma fecha y cantidades opuestas. Repeticiones ambiguas quedan sin parear.
- `unmatched_internal`: filas internas sin contraparte inequívoca.
- `external_net`: neto operativo excluyendo los traspasos explícitos; se coteja con depósitos/gastos publicados. «Externo» aquí significa fuera de las subcuentas Nu, no capital nuevo confirmado del titular.
- `unallocated_net_income`: rendimiento mensual publicado sin reparto individual acreditado.

Un depósito en Cajita reduce cuenta y aumenta Cajita; su pareja no es una segunda aportación externa. Congelar disminuye disponible y aumenta congelado por el mismo principal. Descongelar hace el movimiento inverso por el importe publicado; no se reconoce toda la liberación como ganancia. Un signo imposible se conserva en evidencia, se señala y no genera asientos de congelamiento.

Estos asientos son cambios documentales: no son saldos iniciales/finales reconstruidos. El rendimiento global se reconoce una vez y no se distribuye por tasas, saldos medios o diferencias entre importes de congelamiento. La reinversión no crea otra aportación externa.

## Historia y vencimientos

`review_nu_documents(previews)` deduplica documentos binarios, exige una sola cuenta y rechaza períodos solapados de archivos distintos. Acepta cualquiera de las dos vistas, que comparten evidencia y cuenta.

Los vencimientos se proponen únicamente si nombre y fecha futura explícita del congelamiento coinciden con una liberación posterior, con correspondencia única en ambos sentidos. `maturity_candidates` conserva capital congelado e importe liberado como datos distintos, estado `candidate_requires_contract` y sus evidencias. No deduce rendimiento, retención o tasa contractual de su diferencia. Coincidencias ambiguas y contratos sin contraparte permanecen en listas separadas.

Para meses faltantes, continuidad y cierre global se usa además `review_coverage`. Las fechas proceden del interior, no del nombre del archivo.

## Condiciones históricas y límites documentales

Se conservan tasas/etiquetas publicadas de interés e ISR, GAT y cada retención real. Una tasa de portada no sustituye las condiciones de un contrato congelado; una retención explícita cero no prueba exención ni impuesto anual definitivo. No se calcula declaración del SAT.

Cuando el estado solamente publica rendimiento global y saldos agregados de Cajitas, no se puede certificar el cierre de cada Cajita. Se entregan sus cambios y el rendimiento sin asignar, y `detail_reconciled` permanece falso con la causa concreta. Una diferencia en la composición global también bloquea conciliación completa. Resolver esos casos exige evidencia adicional; no más fórmulas ni un ajuste artificial.

Los datos de pagos de tarjeta/garantía sirven para rastrear efectivo, sin crear un módulo de presupuesto o deuda de tarjeta. Los IDs documentales no son IDs económicos y no deduplican capturas diferentes. Las imágenes conservan OCR local revisable, sin heredar las verificaciones de un PDF. No se usa Excel como movimientos, conexión bancaria, servicios de pago o importación automática. Fuentes e informes financieros permanecen privados.
