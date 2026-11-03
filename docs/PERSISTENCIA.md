# Manual de persistencia local

## Estado

Módulo `finanzas.storage`, SQLite con la biblioteca estándar de Python 3.11 o posterior. No requiere instalar un servidor, conectarse a Internet ni contratar servicios. `Ledger` sigue siendo el cálculo en memoria; `Store` guarda y recupera movimientos.

No existe todavía interfaz de importación ni lector de PDF. Ningún documento financiero real se ha incorporado al sistema.

## Uso básico con datos ficticios

El directorio elegido debe existir. Un archivo de base de datos se conserva después de cerrar el proceso.

```python
from datetime import date
from decimal import Decimal
from finanzas.ledger import Evidence, Kind, Movement, Origin
from finanzas.storage import Store, movement_id

# Usar un directorio privado fuera del repositorio para registros reales.
with Store("ejemplo.sqlite3") as store:
    document = store.register_document(
        b"contenido exclusivamente ficticio", "banco_ficticio",
        date(2026, 1, 1), date(2026, 1, 31),
    )
    # Esta llamada representa una revisión explícita; no certifica el contenido.
    store.review_document(document, "approved", "ejemplo sintético revisado")
    operation = Movement(
        id=movement_id("banco_ficticio", "ahorro_a", "referencia_ficticia_001"),
        account="ahorro_a", unit="MXN", effective_date=date(2026, 1, 5),
        kind=Kind.CONTRIBUTION, amount=Decimal("100.00"),
        evidence=Evidence(document, "página 1, fila 1"),
        origin=Origin.EXTERNAL,
    )
    store.record_many([operation])
    print(store.load_ledger().balances())
```

Ejecutar el ejemplo de nuevo no vuelve a sumar la aportación.

## Identidad y documentos solapados

- El identificador documental es SHA-256 de los bytes del archivo. Renombrarlo no crea otro documento. El original no se almacena: debe conservarse por separado y verificarse contra esa huella cuando se consulte.
- El período se recibe del contenido revisado, no del nombre del archivo. Metadatos incompatibles para la misma huella producen un conflicto; su corrección histórica aún no tiene API.
- La identidad del movimiento usa institución, cuenta interna y referencia estable. La referencia debe venir de la operación o de una identidad revisada; no inventarla con importe y fecha, ya que pueden repetirse.
- Si no hay referencia suficiente, el adaptador futuro mantendrá el candidato pendiente. Todavía no hay detección semántica automática de duplicados.
- Dos documentos pueden aportar evidencia al mismo ID de movimiento. Si el contenido económico coincide, se agrega evidencia sin volver a sumar.
- Dentro de un lote no se admiten IDs repetidos: revisar la extracción antes de confirmarlo.
- Cada componente de una operación agrupada necesita su identidad: capital, interés, retención y comisión no deben compartir ID.

## Revisión y correcciones

Un documento empieza pendiente. `review_document` registra cada cambio de decisión y su motivo. Solo documentos aprobados permiten incorporar movimientos o nueva evidencia. Una revisión posterior rechazada no borra hechos previamente registrados; exige revisión explícita de los movimientos afectados.

`record_many` aplica el lote completo o no aplica nada. Guarda Decimal como texto, fechas ISO, unidad, origen y vínculo. Relee el estado bajo una transacción de escritura para no sobrescribir cambios de otra conexión.

Para corregir un movimiento, enviar su mismo ID con el contenido revisado y:

```python
store.record_many(
    [movimiento_corregido],
    corrections={movimiento_corregido.id: (version_actual, "motivo de la corrección")},
)
```

La versión esperada evita corregir sobre una vista antigua. Cada cambio económico crea una versión, conservando importes, fechas, evidencia y motivo anteriores. `history(id)` y `evidences(id, version)` permiten revisarlos. Agregar evidencia equivalente no genera una nueva versión económica.

Si un traslado conciliado cambia de importe, corregir ambos lados en el mismo lote. Una corrección de un solo lado incompatible se rechaza íntegramente.

Un nuevo documento puede indicar `supersedes=huella_anterior`; eso no reemplaza movimientos automáticamente. Su aprobación y las correcciones siguen siendo explícitas.

## Copia y recuperación

```python
from finanzas.storage import Store

with Store("ejemplo.sqlite3") as original, Store("respaldo_nuevo.sqlite3") as copia:
    original.backup_to(copia)

with Store("respaldo_nuevo.sqlite3") as recuperado:
    print(recuperado.load_ledger().balances())
```

El destino debe estar vacío; no sobrescribe una copia con registros. La copia obtiene una instantánea SQLite consistente y transfiere todas las tablas en una transacción del destino. Incluye documentos, decisiones, versiones y evidencias. No incluye los PDF originales.

También existen `snapshot()` y `Store.from_snapshot(bytes)`: recuperación de una imagen SQLite en una conexión nueva en memoria. Se comprueban versión de esquema, integridad, referencias y reglas del ledger. Para conservarla en archivo se puede copiar a un Store nuevo.

La base y sus copias contienen información privada y no están cifradas por este módulo. Deben permanecer en almacenamiento privado fuera de Git.

## Verificación y límites

`python -m unittest discover -v` ejecuta también pruebas de cierre/reapertura de archivos, copia a archivo y dos conexiones. La variable `FINANZAS_TEST_NO_DISK=1` omite exclusivamente esas dos pruebas para entornos sin escritura; una ejecución con omisiones no equivale a validar persistencia en disco.

GitHub Actions ejecuta la suite completa en Ubuntu estándar únicamente cuando el repositorio es público, sin artifacts ni cachés. La verificación local sigue disponible sin GitHub.

SQLite es adecuado para esta primera aplicación local de un usuario; serializa las escrituras y el módulo carga el ledger completo para validar. No es una arquitectura de alta concurrencia ni historial ilimitado en memoria. La futura migración puede conservar IDs, importes decimales y evidencias; no hay API propietaria de un proveedor.

Pendiente: adaptadores documentales, interfaz de revisión, auditoría de edición de metadatos documentales, anulación de movimientos, verificación del archivo original al abrir evidencia, migraciones de esquema y cifrado integrado. Este módulo no calcula tasas ni obligaciones fiscales.
