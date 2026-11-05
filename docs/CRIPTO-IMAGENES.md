# BingX y Pionex: capturas de operaciones

## Alcance

BingXImageReader y PionexImageReader extraen candidatos desde imágenes mediante OCR local. Se admite que una captura muestre una operación, un fill, un resumen de bot o un producto de rendimiento. No se asume que una captura represente la cuenta completa ni la totalidad del historial.

La entrada principal para estas plataformas es imagen. La configuración no afirma que las plataformas carezcan de otras exportaciones: los archivos y las conexiones de solo lectura siguen siendo posibilidades futuras del proyecto.

Son lectores iniciales por etiquetas en español/inglés. Se han probado con imágenes ficticias; falta validar sus etiquetas y diseños con capturas reales de las aplicaciones del titular. No están terminados los importadores económicos ni el cálculo fiscal de cripto.

## Uso

```python
from pathlib import Path
from finanzas.crypto_images import BingXImageReader, PionexImageReader

reader = BingXImageReader(account="mi_alias_local", timezone="UTC")
preview = reader.read_image(Path("operacion_privada.png").read_bytes())
print(preview.operation_kind, preview.issues)
```

timezone debe ser la zona horaria comprobada de la plataforma, no la ubicación del titular. Si se omite, queda pendiente. El lector conserva la fecha/hora visible como texto y no realiza conversiones horarias ni adivina el orden día/mes.

En el catálogo general se usa reader_for("bingx", "investments") o reader_for("pionex", "investments"). La vista de débito bancario no aplica a estos lectores.

## Campos candidatos

Identificadores de orden, ejecución/fill, transacción y bot; fecha/hora, par, mercado y lado; cantidad, contratos, precio, importe y comisión; PnL realizado, no realizado, PnL genérico, beneficio del bot, funding y rendimiento; estado de ejecución.

Cada candidato conserva texto original, valor Decimal cuando es inequívoco, unidad visible, líneas de origen, confianza OCR y problemas particulares. Los IDs conservan sus mayúsculas y ceros. Un campo ausente permanece ausente: comisión desconocida no equivale a comisión cero.

El lector distingue categorías orientativas spot_buy, spot_sell, spot, derivative, bot_summary, yield y unknown. Las categorías requieren etiquetas explícitas; Buy por sí solo no acredita que sea spot.

## Controles económicos

- No se infiere moneda: USD, USDT, BTC, contratos y MXN son unidades diferentes.
- Precio y cantidad no se intercambian. Un tamaño en contratos no se transforma en BTC.
- Separadores como 1,234 o 1.234 se consideran ambiguos cuando pueden ser decimal o miles. decimal_mode puede fijarse explícitamente como international o spanish después de verificar el formato.
- Conflicto entre unidad de etiqueta y valor deja el valor sin confirmar.
- Campos repetidos señalan varias operaciones o conflicto; no prevalece silenciosamente la última fila.
- PnL genérico no se convierte en PnL realizado. Beneficio de bot no se suma junto a sus operaciones subyacentes.
- Una orden cancelada/abierta o sin estado no se trata como ejecución confirmada.
- Sin fecha, identificador o zona horaria se conservan pendientes visibles.

## Identidad y capturas repetidas

La huella de imagen identifica evidencia, no la operación económica. Otra foto de la misma operación puede tener una huella distinta.

execution_identity solo propone una coincidencia cuando constan plataforma, alias local de cuenta, ID de orden e ID de ejecución/fill sin problemas de lectura. La misma orden puede tener varios fills: no basta usar únicamente su ID. La propuesta no inserta, fusiona ni elimina operaciones.

Este incremento no implementa deduplicación contable automática, conciliación con saldos del exchange, costo de adquisición, bot por operación, liquidación de derivados, impuestos ni conexión API.

## Revisión y privacidad

ready_to_import permanece False. El usuario o el flujo de revisión futuro debe contrastar la imagen antes de confirmar datos económicos. No se solicita ni utiliza contraseña, clave API, frase semilla, clave privada ni permisos de trading/retiro.

La imagen original se conserva fuera de Git; el lector no la archiva ni publica. El OCR y las pruebas funcionan localmente tras instalar dependencias.
