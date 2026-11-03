# Manual del núcleo inicial

## Qué hace

`finanzas.ledger` permite registrar movimientos inmutables con evidencia, consultar saldos por cuenta/unidad y fecha efectiva, sumar aportaciones externas acreditadas, identificar orígenes y contrapartidas pendientes, y consultar interés cobrado y retención documentada.

`Movement.amount` usa Decimal positivo; el tipo determina el signo. Solo una retención documentada puede tener importe cero. Cada cuenta del núcleo representa una sola unidad. La precisión admitida es de hasta 36 dígitos significativos, con exponente Decimal entre -30 y 30; las sumas ajustan su precisión sin redondeo monetario automático.

## Ejemplo ficticio

```python
from datetime import date
from decimal import Decimal
from finanzas.ledger import Evidence, Kind, Ledger, Movement, Origin

ledger = Ledger()
ledger.record(Movement(
    id="ficticio-1", account="ahorro_a", unit="MXN",
    effective_date=date(2026, 1, 5),
    kind=Kind.CONTRIBUTION, amount=Decimal("100.00"),
    evidence=Evidence("documento-ficticio", "pagina 1, movimiento 1"),
    origin=Origin.EXTERNAL,
))
print(ledger.balances())
```

## Reglas de uso

- Usar cadenas al construir Decimal; nunca float.
- `Evidence` conserva identificador documental y localizador; no almacena ni verifica el archivo original.
- El importador futuro deberá generar IDs estables y detectar documentos/operaciones duplicados. Hoy la idempotencia se garantiza únicamente cuando se repite el mismo ID y contenido. Contenido distinto con el mismo ID produce error y no sobrescribe.
- `Origin.UNKNOWN` conserva el movimiento en su cuenta, excluye su importe del subtotal de capital externo acreditado y lo muestra pendiente. Ese subtotal no certifica que todos los orígenes estén resueltos.
- `Origin.CASHBACK` conserva la categoría y cuenta como aportación externa a la cartera seguida. No lo clasifica como interés.
- `Origin.OWN_TRANSFER` o `Origin.REINVESTMENT` requieren `transfer_id`. El mismo vínculo admite un retiro y una aportación del mismo importe y unidad, en cuentas distintas. El usuario/importador propone el vínculo; el núcleo no adivina la correspondencia.
- Si falta una parte, la registrada permanece y el vínculo queda pendiente. Si se propone una contraparte incompatible, se rechaza esa propuesta sin borrar la parte válida.
- Reinvertir un saldo en otro contrato se representa con retiro y aportación enlazados. Si el interés queda en la misma cuenta, se registra el cobro una vez; este núcleo aún no ofrece asignación de lotes ni evento informativo de capitalización.
- `withholding_recorded` devuelve None si no hay retenciones documentadas, o la suma de las registradas. Una retención cero explícita devuelve cero. Ninguno de esos resultados acredita por sí solo cobertura completa ni ISR definitivo.
- Se admiten saldos negativos porque una historia incompleta puede comenzar con retiros. No equivale a autorizar un sobregiro.
- Unidades diferentes permanecen separadas. No hay tipo de cambio ni valoración en MXN.

## Límites actuales

Ledger funciona en memoria; para conservar movimientos utilizar Store, descrito en el [manual de persistencia](PERSISTENCIA.md). Ledger por sí solo no guarda datos al finalizar el proceso. No hay conexión bancaria ni sincronización.

No existe todavía cálculo diario por tasa, historial contractual, reparto capital/interés, conciliación múltiple, precio de activos, derivados, rendimiento ponderado, devengo ni aplicación visual. La persistencia y las correcciones versionadas pertenecen al módulo Store. Los saldos calculados representan solo movimientos registrados, no una certificación del saldo bancario.

No se realizan inferencias fiscales. Las comisiones e intereses son categorías básicas para efectivo; no resuelven IVA ni tratamiento fiscal particular.
