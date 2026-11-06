# Kapital: efectivo y pagarés en dos formatos

El lector optativo reconoce el formato con «Resumen del periodo» y contratos LD, y el formato con «Cuenta de cheques», folios operativos y tablas de pagarés. Funciona localmente con las dependencias PDF/OCR existentes, sin nuevas APIs.

```bash
python -m finanzas.readers estado.pdf --institution kapital --lane debit --reconcile
python -m finanzas.readers estado.pdf --institution kapital --lane investments --reconcile
```

Las dos vistas comparten evidencia, con resúmenes distintos: efectivo e inversión. `ready_to_import=False` permanece en el lector incluso si las comprobaciones concilian: extraer no confirma movimientos. La aplicación añade un [plan financiero explícito](IMPORTACION-KAPITAL.md) para pagos operativos y observaciones de pagarés, con confirmación atómica.

## Reglas de cada formato

En el formato anterior, las aperturas de pagaré pueden estar en movimientos de inversión, separados de transferencias enviadas. Se conservan los importes publicados de movimientos positivos/negativos de inversión y su efecto contrario en efectivo. No se introduce una salida ficticia por diferencia.

La columna Retiro anterior se publica con signo negativo: se conserva como `withdrawal_printed` y se deriva un cargo positivo para conciliar. La apertura con referencia LD se coteja contra fecha y capital contractual.

En el formato nuevo, depósitos/retiros ya incluyen principal e interés de vencimientos, retenciones y timbrado. Los componentes se cotejan por separado; no se suman una segunda vez a la ecuación del efectivo.

Cargo y descuento de timbrado se conservan como filas diferentes aunque compartan folio. La comisión efectiva neta se contrasta con ambos; no se borran por compensarse. Un saldo con signo final, como «0.01-», conserva su valor negativo.

## Contratos y cobros

Cada pagaré conserva identificador, producto, apertura, vencimiento, días, principal, tasa, GAT e interés al vencimiento. El formato nuevo añade ISR futuro, tasa neta y neto futuro. Los campos no publicados en el formato anterior permanecen desconocidos, no como cero.

El capital vigente se contrasta con el resumen, y cada neto futuro con capital + interés − ISR y su Total Vigentes particular. No se suma el capital de las apariciones mensuales repetidas ni se reconoce el interés futuro como un cobro mensual. No se recalculan importes mediante bases anuales o reglas fiscales supuestas.

## Revisión entre documentos

`review_kapital_documents` conserva todos los documentos y propone:

- Equivalencias de identificadores entre formatos cuando coinciden de forma única apertura, vencimiento, días, capital, tasa bruta e interés futuro, dentro de la misma cuenta identificada y en períodos sucesivos. No fusiona IDs ni sustituye condiciones publicadas.
- Cotejos de vencimiento cuando un contrato anterior coincide con tres filas contiguas de la misma fecha/folio: principal, interés y retención. Las proyecciones repetidas no crean varios cobros; una retención pagada diferente de la proyectada se conserva y se señala.

Todas las propuestas requieren revisión. No se confirma automáticamente una equivalencia, transferencia, vencimiento o reinversión. La CLABE identifica la cuenta en las fuentes reconocidas; cambiar el número de cliente o formato no crea por sí solo una cuenta nueva.

La cobertura compara por separado efectivo y capital de inversión, deduplicando solo archivos idénticos. Los huecos entre estados no se completan con proyecciones o Excel.

## Límites y evidencia

Se usan únicamente los encabezados de período para fechar el estado: apertura y vencimiento no son el intervalo mensual. Se conservan página/línea, signo original y formatos. Las descripciones partidas del formato anterior no se homologan ni prueban la propiedad de la contrapartida por su texto.

Los conceptos desconocidos, columnas inesperadas, referencias/categorías repetidas y diferencias exactas quedan pendientes. Un folio compartido entre principal/interés/ISR o cargo/descuento no implica duplicidad económica. Faltan identidad económica de importación y confirmación de contrapartidas.

El lector está limitado a las estructuras verificadas. Una cartera sin tablas reconocidas no se presume vacía. Las imágenes generan evidencia para revisar, sin heredar conciliación PDF. No calcula declaración anual ni determina la naturaleza fiscal definitiva de una retención. Los informes financieros y originales permanecen privados.

La confirmación registra el descuento de timbrado como devolución de comisión, con signo positivo y sin capital externo o interés. La moneda no publicada queda desconocida y requiere revisión MXN. El PDF protegido puede releerse con contraseña temporal, sin guardarla.
