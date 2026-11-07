# Evolución financiera por cuenta y período

## Consultar

1. Abre **Libro financiero**. La sección **Evolución por período** aparece antes del resumen acumulado.
2. Selecciona una cuenta/producto o conserva todas. Las tablas se agrupan por categoría, institución, cuenta y moneda; la huella abreviada distingue cuentas diferentes.
3. Consulta saldo inicial, aportaciones, retiros, interés, ISR retenido, interés menos ISR y cierre de cada período.
4. Abre **Cierre conciliado / Revisar diferencias** para consultar componentes, diferencias y pendientes; **Abrir documento** lleva a su evidencia original y plan confirmado.

Los importes se conservan como cadenas decimales exactas, sin conversión a números flotantes en el navegador. Las tablas tienen desplazamiento horizontal para pantallas estrechas. El resumen acumulado permanece disponible en una sección desplegable.

## Qué significa cada cifra

- **Período:** fechas internas del estado confirmado. Un corte que cruza meses no se reparte artificialmente entre meses naturales.
- **Inicial / cierre:** anclas documentales. La apertura no genera una nueva aportación y el cierre no representa saldo actual de mercado.
- **Aportaciones / retiros:** movimientos de esa cuenta. Incluyen entradas/salidas propias, con su desglose en el detalle; no equivalen a capital externo global ni a ganancia.
- **Capital externo / cashback acreditados:** solo las aportaciones con esos orígenes ya clasificados. Cashback se muestra también individualmente. Origen desconocido conserva su contador pendiente.
- **Traspasos / reinversiones:** patas registradas con vínculo explícito; no se deducen por importe ni por un aumento del saldo. Los vínculos sin contraparte permanecen advertidos.
- **Interés e ISR:** componentes netos de sus cancelaciones/devoluciones. Un período puede tener interés negativo o devolución de ISR. Retención mexicana, retención extranjera, dividendos, IVA y comisiones permanecen separados.
- **Desconocido:** ausencia de retención documentada, cobertura parcial o interés sin asignación acreditada. Un cero publicado sí se conserva como cero. El interés clasificado parcial está disponible en el detalle sin presentarlo como total conocido.
- **Cobros de valores sin desglose:** cobros CETESdirecto pendientes de asignar a principal/interés. No se presentan como rendimiento completo.

No hay suma entre monedas o cuentas, valoración de posiciones, cálculo de rentabilidad porcentual, devengo diario interpolado, declaración anual ni recomendación financiera. Fintual MXN y USD conservan identidad Fintual y cuentas distintas.

## Controles de cobertura y revisiones

Cada consulta lee una instantánea consistente SQLite y usa la última versión de los movimientos. Calcula `inicial + cambio neto de efectivo` y muestra la diferencia **calculado menos documental**. No modifica el cierre ni introduce ajustes.

Una modificación de importe, tipo, fecha, cuenta, origen o vínculo respecto del lote confirmado genera revisión, aunque el cierre aritmético todavía coincida. Los movimientos añadidos al período también se señalan. Si una corrección mueve una operación a otro período se cuenta una vez en su fecha vigente y quedan señalados ambos períodos; si queda fuera de cobertura se muestra en la lista de movimientos fuera de períodos con acceso a su documento.

Los huecos aparecen únicamente entre períodos confirmados de una misma cuenta: no se inventan operaciones ni se presume cobertura anterior al primer estado o posterior al último. Solo se compara apertura con cierre anterior cuando son contiguos. Meses cargados fuera de orden se presentan cronológicamente; reabrir o repetir la carga no duplica la historia.

**Cierre conciliado** significa que los movimientos vigentes de ese período explican el cierre publicado y conservan el lote confirmado. No certifica historia completa, origen de fondos, posiciones de cartera o ISR anual definitivo.

## Operación local y validación

Consulta y cálculos funcionan sin Internet mientras el servicio local esté iniciado. No se añadieron dependencias, APIs ni pagos obligatorios. Actualizar GitHub requiere conexión.

`GET /api/book/evolution` devuelve cuentas con su historial y movimientos fuera de cobertura, mediante las mismas restricciones de acceso local existentes. Es una consulta de solo lectura, sin cambiar documentos, revisiones ni movimientos.

Diecisiete pruebas nuevas con documentos ficticios cubren dos vistas, anclas, traspasos, cifras exactas, períodos fuera de orden, huecos, reapertura/reintento, desconocido/cero, cobros sin desglose, Fintual MXN/USD, cancelaciones históricas, correcciones dentro/fuera de período y cuenta, coexistencia de las trece instituciones integradas, transacción de lectura y HTTP. Comprobación sintáctica JavaScript incluida. No se declara verificación visual en navegador: este entorno no dispone del ejecutable Chromium.
