# BanCoppel: conciliación PDF detallada

## Alcance

BanCoppelDebitReader agrega controles al formato conocido de Cuenta Efectiva/Digital. Complementa el lector documental y su entrada de imagen; no convierte una cuenta de paso en inversión ni administra gastos personales.

```python
from pathlib import Path
from finanzas.readers import reader_for

preview = reader_for("bancoppel", "debit").read_reconciled_pdf(
    Path("estado_privado.pdf").read_bytes()
)
print(preview.detail_reconciled, preview.reconciled, preview.issues)
```

```sh
python -m finanzas.readers estado_privado.pdf --institution bancoppel --lane debit --reconcile
```

El método específico BanCoppelDebitReader().read_pdf también está disponible. La consola conserva el resumen sin importes por defecto; --details contiene datos privados.

## Controles

- Huella del documento y huella interna de la cuenta, sin utilizar el nombre del archivo como fecha.
- Período documental único; fechas MM/DD del detalle resueltas dentro del período, incluido cambio de año.
- Detalle en orden inverso de origen, devuelto cronológicamente con página y línea.
- Entrada/salida derivada del cambio entre saldos y el importe impreso. Si no concilia, el sentido queda unresolved y el control lo señala.
- Identificación orientativa de intereses, comisiones, IVA, devolución SPEI, transferencias y efectivo. Ninguna categoría confirma aportación externa a la cartera.
- Comparación entre depósitos/retiros del detalle y el resumen, comisiones/IVA y saldo final.
- Conservación de interés bruto, retención, interés neto del período y tasa anual informativa. La retención no se declara impuesto definitivo.
- Fila fechada no reconocida, resumen cambiado/incompleto y contradicciones de bruto/retención/neto producen error explícito.

La tasa informativa pertenece al documento y no se aplica retroactivamente a contratos ni otros períodos. Si aparece retención no nula, se exige revisar cómo figura en el detalle; ese caso no se considera automáticamente conciliado.

## Diferencia entre controles

detail_reconciled indica que los importes y saldos de los movimientos forman una secuencia consistente hasta el cierre. reconciled exige además que el resumen completo y sus componentes coincidan.

El detalle puede conciliar y el resumen contener una discrepancia. Se conservan ambos hechos. No se distribuyen diferencias como rendimientos, gastos ficticios o ajustes para forzar igualdad.

ready_to_import sigue siendo False. Esta entrega no crea movimientos de inversión, no enlaza contrapartidas ni confirma el origen externo del dinero.

## Cobertura entre documentos

review_coverage compara documentos de una misma cuenta identificada:

- El mismo SHA-256 no duplica cobertura.
- Estados de cuentas diferentes o sin identificación no se comparan como una única historia.
- Versiones distintas del mismo período o solapamientos quedan señalados.
- Un hueco es un intervalo faltante dentro del tramo recibido; no se inventan movimientos ni se extrapola la apertura.
- Solo se comparan cierre/apertura de períodos consecutivos; no se exige continuidad a través de un hueco.

Los controles no prueban cobertura anterior al primer archivo ni que ya exista el estado del período en curso. La evidencia financiera y los inventarios particulares permanecen privados.

## Límites y pruebas

Este parser depende de la estructura de resumen y detalle conocida. Otros productos, diseños nuevos, PDF escaneado o cifras con formato diferente requieren adaptación; los errores se conservan visibles.

Las pruebas públicas usan extractos ficticios. Cubren cambio de año, saldo alterado, comisiones distintas en resumen/detalle, retención desconocida o positiva, filas ilegibles, PDF, consola, duplicados, cuentas diferentes, huecos y solapamientos. Los documentos reales no son fixtures del repositorio.

## Confirmación en la aplicación

El débito PDF conciliado se conecta al ledger como cuenta de paso. Se exige identidad única y moneda nacional explícita; cargos operativos e ISR permanecen separados y los orígenes de capital pendientes. Ver [manual de importación BanCoppel](IMPORTACION-BANCOPPEL.md). La vista de inversiones y la evidencia OCR no generan un producto financiero adicional.
