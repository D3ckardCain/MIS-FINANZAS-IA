# Importar Nu al libro financiero

## Flujo en la aplicación

1. Sube el PDF y abre **Preparar importación financiera**. El archivo debe tener las dos lecturas específicas de cuenta/Cajitas. Si está protegido, introduce su contraseña; solo se conserva temporalmente en memoria.
2. Si el documento no publica moneda, confirma MXN con tus fuentes. Una moneda contradictoria bloquea el plan.
3. En **Acreditar distribución Nu por producto**, verifica con fuentes adicionales la apertura, interés bruto e ISR de Cuenta Nu, Cajitas y garantía cuando corresponda. El estado suele publicar estos conceptos solo de forma global. No basta con encontrar números que cuadren.
4. Marca la verificación y aplica la revisión. La aplicación comprueba los totales globales, el cierre de cada producto, las filas, las parejas de traspaso y la continuidad. Confirma solo el plan sin problemas pendientes.
5. Consulta los productos separados en **Libro financiero** y su evolución por período, con acceso al PDF original.

La apertura enlazada a un cierre contiguo confirmado aparece precargada. Eso no asigna automáticamente el rendimiento/ISR. Solo si ambos globales son cero y todos los productos tienen apertura contigua se puede preparar un plan sin un nuevo desglose: cero global con componentes no negativos acredita cero por producto. La confirmación financiera continúa siendo explícita.

## Qué se registra

- **Cuenta Nu:** entradas/salidas documentadas, SPEI y compras con tarjeta identificadas. Un concepto desconocido bloquea el lote completo; no se clasifica por signo solamente.
- **Cajitas · agregado:** una cuenta financiera que representa el total de todas las Cajitas. Puede sustituirse por **Cajitas individuales** mediante el desglose acreditado descrito abajo. No se registra el agregado a la vez.
- **Crédito con garantía:** cuenta separada si existe saldo/actividad o historia confirmada; exige cierre y tabla acreditados. La ausencia de ese saldo no se interpreta como cero.
- **Traspasos:** aportación en destino y reducción en origen, vinculadas solo con pareja documental única por nombre, fecha y cantidades opuestas. No añaden capital externo.
- **Interés/ISR globales:** una sola distribución revisada que debe sumar exactamente al resumen. Se reconocen **al cierre del período por resumen**, con esa procedencia explícita; no se presentan como fechas diarias de cobro. Cada retención por producto se distingue como asignación revisada, incluido cero.
- **Congelamientos/liberaciones:** observaciones documentales de liquidez dentro de Cajitas, sin sumar otro activo, inferir rendimiento desde la diferencia, modificar capital o crear reinversión. Disponible/congelado siguen siendo subconjuntos del total.

El resumen global es un control, no una tercera cuenta adicional a Cuenta/Cajitas. Garantía es otro producto únicamente cuando está acreditada. Se conservan emisor, tasas/GAT y nombres/claves de rastreo como observaciones/evidencia histórica.

## Controles y límites

Aperturas por producto suman la apertura global. Distribución de bruto e ISR coincide con ambos globales. Cada cierre se explica por apertura más filas más distribución neta. Depósitos y gastos externos a las subcuentas se cotejan **por separado**, además de su neto. Filas sin importe único, fuera del período, conceptos desconocidos, congelamientos de signo imposible, parejas ambiguas, secciones ausentes o composición discordante bloquean incluso con revisión manual.

La revisión identifica documento y versión y queda ligada al hash del plan/libro. Cambiarla exige preparar otro plan. Importación atómica, reintentos, reapertura, meses fuera de orden, límites contiguos y solapamientos utilizan los controles existentes. No se modifican originales ni se guarda la contraseña.

`NuReader.ready_to_import` permanece falso: el lector por sí solo no confirma datos. El adaptador financiero admite explícitamente la revisión de **agregados**; no afirma que el agregado por sí solo concilie cada Cajita. El modo individual sí exige cierre de cada Cajita con sus cifras acreditadas. Los saldos iniciales son anclas, no aportaciones nuevas. SPEI y gastos conservan origen pendiente; Cashback explícito positivo se registra como aportación con origen cashback, sin convertirlo en interés. Un reembolso genérico no se presume cashback. No hay deuda de tarjeta, tasas diarias recalculadas, reinversión automática o ISR anual.

Las imágenes siguen admitidas como evidencia OCR revisable, pero este incremento confirma solo PDF textual del formato conocido. No se leyó el Excel ni se importó contabilidad personal.

## Operación y pruebas

Funciona localmente sin Internet una vez instalados los extras PDF/imagen existentes. No añade dependencias, APIs o pagos obligatorios. Actualizar GitHub requiere conexión.

Diecinueve pruebas nuevas con datos ficticios cubren cuenta/Cajitas/garantía, neutralidad de traspasos y congelamientos, asignación global una vez, fechas de resumen, totales y cierres incompatibles, revisiones inválidas/ajenas/desactualizadas, tablas/conceptos/moneda, meses fuera de orden, apertura contigua sin asignación automática, ceros explícitos, cambio de hash, rollback/reintento/reapertura, contraseña y HTTP. JavaScript comprobado sintácticamente; el flujo de navegador se comprueba en Chrome de Actions, con datos ficticios.


## Cajitas individuales

En el plan, marca **Acreditar cada Cajita por separado**. Se proponen los nombres publicados en las filas. Completa apertura, cierre, bruto e ISR de cada una desde fuentes adicionales y añade las Cajitas sin movimientos. La aplicación calcula los totales exactos en el servidor, los coteja con el resumen y exige el cierre de cada Cajita desde sus propias filas.

Se confirma una cuenta por Cajita y se retira del lote la cuenta agregada. Los traspasos conservan su contraparte en Cuenta Nu. Las Cajitas sin actividad permanecen visibles y no desaparecen al cambiar de mes; una cerrada debe conservarse con cero acreditado. Nombres se normalizan para evitar duplicados; un cambio de nombre no fusiona cuentas automáticamente.

Un historial confirmado en modo agregado continúa en ese modo; uno individual continúa individual. Cambiar de granularidad exige una transición acreditada y no se realiza automáticamente. Esta restricción evita sumar dos veces el mismo dinero y conserva el historial existente. No se reescriben lotes antiguos.

Cierres individuales introducidos por el usuario siguen etiquetados como revisión, no como extracción automática del PDF global. El reconocimiento de interés/ISR por resumen mantiene fecha de cierre; las fuentes que no publican pagos diarios no permiten certificar fechas diarias. Congelamientos y vencimientos conservan su evidencia, sin inventar tasa contractual o reinversión.

Doce pruebas adicionales verifican Cajitas individuales activas/sin movimientos, totales/cierres, nombres ambiguos/inválidos, continuidad fuera de orden, Cajitas históricas, incompatibilidad de granularidad, rollback/reintento/reapertura, cashback explícito y confirmación HTTP con revisión normalizada. Se añade prueba automatizada de navegador Chrome en CI, sin dependencias del sistema operativo de la app: carga ficticia, formulario individual, confirmación, evolución y ancho móvil; capturas exclusivamente ficticias retenidas un día.
