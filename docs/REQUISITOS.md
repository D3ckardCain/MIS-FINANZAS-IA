# Alcance y reglas acordadas

Consolidación de las decisiones del proyecto al 2026-11-03. Este registro resume requisitos; no reproduce conversaciones ni documentos privados.

## Producto

- Organizar el panel por categoría: Bancos, SOFIPOs, SOFOMes, instituciones de préstamo, acciones, criptomonedas y FIBRAs. Dentro de cada categoría: instituciones; dentro de cada institución: Cuenta de débito e Inversiones. Resumen global separado.
- Dos lectores por institución: débito e inversiones, independientes y enlazables por transferencias. Si un producto no existe, mostrar No aplica. Detalle en [PANEL.md](PANEL.md).
- Bancos, SOFIPOs, SOFOMs, préstamos, fondos, FIBRAs, acciones y criptomonedas.
- Controlar capital aportado, retiros, rendimiento bruto, retenciones, comisiones, reinversiones, disponibilidad y vencimientos.
- Excluir gastos de cuenta corriente y tarjetas. Una cuenta de paso participa únicamente cuando aporta evidencia del recorrido del dinero.
- Interfaz profesional con lenguaje visual de GitHub: tipografía, colores y jerarquía. Primero claridad y conciliación; cada cifra debe poder explicarse.
- Costo operativo obligatorio objetivo: USD 0. Priorizar ejecución local y alternativas portables. No servicios que exijan tarjeta, pruebas temporales ni APIs de pago.
- Operación offline viable para consulta y registro local. Tasas vigentes, conexión con plataformas y sincronización necesitan conexión. No prometer funcionamiento completo offline.

## Evidencia y calidad

- Los estados de cuenta son fuente primaria. No convertir el Excel en movimientos; usarlo posteriormente para localizar inversiones y períodos faltantes.
- Documento, página/fila, cuenta, período y extracción deben ser rastreables. Mantener original, correcciones y revisión humana.
- Fechas efectivas según el contenido; separar operación, liquidación, registro y período devengado. No usar el nombre del archivo como fecha contable.
- No repartir pagos agrupados del fin de semana como hechos diarios sin evidencia. Un cálculo estimado debe identificarse como tal.
- Separar lo documentado, lo calculado y lo pendiente. Desconocido no equivale a cero. No inventar movimientos para cuadrar diferencias.
- Importaciones repetibles sin duplicar registros. Resolver versiones corregidas sin borrar la auditoría.

## Capital y rendimientos

- Cada traslado propio produce retiro en origen y aportación en destino. El resumen global excluye esos traslados de capital externo nuevo.
- Registrar un lado real aunque falte su contrapartida; dejar conciliación pendiente. Admitir posteriormente tramos múltiples y consolidaciones.
- Cashback destinado a inversión es aportación con origen cashback; no rendimiento del producto.
- El saldo inicial no es aportación nueva del período.
- Reinvertir no produce un segundo ingreso. Separar capital original, interés cobrado, interés reinvertido y retiro cuando la evidencia lo permita.
- Si el dinero es fungible y la composición no consta, no inventar qué parte transferida es capital o interés.
- Vencimiento y renovación son hechos distintos. Conservar contrato anterior, nuevo contrato, importes, plazos y tasas.
- A la vista y a plazo fijo requieren reglas distintas de disponibilidad, devengo y cobro.
- Versionar tasas por producto, contrato y vigencia. Considerar topes, escalones, condiciones promocionales, redondeo y base de días contractual. Nunca aplicar la tasa actual al pasado.
- Diferenciar proyecciones, devengo no cobrado y pagos efectivamente recibidos.

## ISR

- ISR retenido no equivale automáticamente a impuesto definitivo ni a declaración anual liquidada.
- Registrar importes realmente retenidos con su evidencia y ejercicio. La calificación provisional, definitiva o exenta necesita respaldo aplicable al caso.
- No volver a sumar una constancia anual si sus retenciones ya constan mensualmente. Conciliar y preservar versiones corregidas.
- No descontar dos veces una retención cuando un resumen ya presenta interés neto.
- El módulo SAT será posterior y usará fuentes oficiales por ejercicio; este incremento no calcula obligaciones fiscales.

## Cripto, acciones y siguientes fases

- Cripto: historial desde la primera operación; BingX, Pionex y wallets propias/frías.
- Cubrir spot, bots, derivados y productos de rendimiento. No duplicar resultados agregados del bot y sus operaciones subyacentes.
- Combinar archivos y conexión automática de solo lectura cuando exista una opción realmente gratuita y suficiente. No solicitar permisos de retiro ni trading.
- Conservar activo, red, unidades, comisiones y transferencias propias; separar operaciones realizadas y valoración no realizada.
- El soporte de unidades del núcleo no constituye todavía contabilidad de trading, costo fiscal, futuros ni valoración.
- Optimización de inversiones y comparación de ofertas mexicanas: fase futura con información verificada y riesgos, liquidez y fiscalidad comparables.
