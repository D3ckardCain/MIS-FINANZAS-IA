# Registro revisado de BingX y Pionex

## Cargar y registrar una captura

1. Sube la foto/captura y abre su detalle. El OCR propone campos; no registra automáticamente operaciones ni corrige letras confundidas con números.
2. En **Registro revisado de operación cripto**, identifica la cuenta/subcuenta con un alias estable y selecciona el tipo. Usa siempre el mismo alias para la misma cuenta, y otro para una subcuenta diferente. La plataforma procede de la captura identificada.
3. Abre **Ver captura original**, contrasta los campos y corrige/completa los que falten con tus fuentes. La fecha/hora debe incluir desplazamiento, por ejemplo `2026-01-05T12:00:00+00:00`. No se supone la zona horaria de la plataforma ni la del titular.
4. Acredita el estado y los datos, prepara el registro, revisa sus efectos y confirma. Cambiar un campo exige preparar de nuevo. La marca de revisión documental general no sustituye esta confirmación.
5. Abre **Registro cripto** para consultar operaciones, variaciones registradas por activo y todas las capturas que acreditan cada una.

La nueva entrada del panel permanece separada del libro de efectivo bancario. Las capturas no son estados de cuenta y no publican aperturas o cierres completos.

## Tipos separados

| Tipo | Datos mínimos | Efecto admitido |
| --- | --- | --- |
| Spot compra/venta | Cuenta, fecha con desplazamiento, orden, ejecución, activos base/cotizado, cantidad e importe ejecutado sin comisión, estado ejecutado | Variación de ambos activos y comisión documentada en su propio activo |
| Rendimiento pagado | Cuenta, fecha, identificador de pago, activo, importe y estado pagado | Abono del activo y comisión documentada |
| Derivado | Orden/ejecución, contratos/unidad, par, fecha y ejecución acreditada; PnL/funding opcionales con activo de liquidación | Observación, sin alterar efectivo o posiciones spot automáticamente |
| Resumen de bot | Bot, fecha y estado resumen; beneficio/activo opcionales | Observación, sin sumar beneficio a los fills o al rendimiento pagado |

El importe spot es el ejecutado **sin comisión** y debe acreditarse; no se obtiene multiplicando precio por cantidad. Una compra reduce el activo cotizado y aumenta el base; una venta hace lo contrario. La comisión puede estar en cualquiera de ellos o en un tercer activo. No se convierte USD en USDT, ni entre activos/monedas.

Comisión ausente queda desconocida: importe y activo deben estar ambos acreditados o ambos ausentes. Cero exige importe cero y activo explícitos. Comisiones negativas/rebajas requieren otro tipo acreditado y no se absorben como una comisión positiva. El precio publicado permanece en la evidencia OCR; no se deduce costo fiscal ni ganancia realizada de la variación registrada.

## Duplicados e identidad

- Spot/derivado: plataforma + cuenta/subcuenta + familia + orden + **ejecución**. Una orden puede tener varios fills. Una orden sin ejecución no identifica una operación completa.
- Pago de rendimiento: plataforma + cuenta + identificador de pago.
- Bot: plataforma + cuenta + bot + instante del resumen. Otro instante es otra observación, no otro ingreso.

IDs conservan mayúsculas/minúsculas. Alias de cuenta se normalizan en espacios y mayúsculas para evitar variantes accidentales. Las fechas con desplazamientos distintos que representan el mismo instante se normalizan a UTC. No se trunca precisión superior a microsegundos.

Dos fotos de la misma identidad y los mismos datos añaden evidencia a una sola operación. Una segunda foto con datos incompatibles queda pendiente: no sobrescribe ni duplica lo confirmado. Completar una comisión desconocida previamente confirmada requiere resolver ese conflicto; no se actualiza silenciosamente.

## Qué significan las variaciones

**Variación registrada no es saldo actual.** No se ha acreditado aquí todo el historial, depósitos/retiros, transferencias de wallets ni saldos iniciales. Una salida neta negativa no demuestra deuda. Si faltan comisiones, el neto está incompleto. No se calculan tenencias globales, costo por lote, resultado fiscal, conversión a MXN o ISR.

El PnL realizado/no realizado, funding y beneficio de bot son observaciones de esas capturas; no se suman al registro spot ni se presentan como efectivo conciliado. Un resumen no se duplica con operaciones subyacentes. Futuros/contratos, bots y pagos requieren sus identificadores y campos específicos.

## Persistencia y alcance

SQLite local separado (`.crypto.sqlite3`) conserva operaciones y relación de evidencias con revisión original. El archivo de bandeja conserva la imagen. Confirmación atómica, documento/versión y hash del plan/libro impiden confirmar un plan desactualizado; cualquier fallo revierte operación y evidencia. Reintentar/reabrir no duplica registros. No se escribe al ledger bancario para inventar saldo o interés en pesos.

PDF no se trata como captura cripto. Los campos ausentes o de baja confianza requieren revisión, no cero automático. Importación de archivos de plataforma, API automática, wallets, contabilidad de posiciones/futuros, conciliación de depósitos/retiros y correcciones económicas posteriores forman parte de incrementos siguientes.

Funciona localmente sin Internet con los extras OCR ya existentes. No incorpora paquetes, APIs ni servicios de pago nuevos. GitHub solo se necesita para actualizar el código y sus pruebas, no para registrar capturas.

## Pruebas

Diecinueve pruebas nuevas, exclusivamente ficticias: OCR revisable, compra/venta, activo de comisión, desconocido/cero, dos fotos y varios fills, cuentas/plataformas/USD/USDT, conflictos, estados/IDs/unidades/importes/horas, precisión decimal, pagos, futuros/bots observados, atomicidad, reintentos/reapertura, revisión/hash, PDF rechazado y HTTP con imagen original.

Chrome automatizado prueba apertura de la captura original, edición/revisión spot, plan antes de confirmar, registro por activo separado del banco y ancho móvil. Los flujos Nu y traspasos permanecen en la suite. Las capturas de prueba son ficticias y se conservan un día.


## Validación publicada

[707 pruebas y flujos Chrome de Nu, traspasos y cripto aprobados](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42381269241). Capturas de revisión de la imagen, registro en escritorio y móvil inspeccionadas con datos ficticios. El flujo de navegador confirma una ejecución spot y comprueba sus variaciones nativas sin crear movimientos bancarios.
