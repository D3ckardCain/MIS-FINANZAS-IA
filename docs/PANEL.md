# Organización aprobada del panel

Decisión del titular: categorías separadas, instituciones dentro de cada categoría y dos vistas dentro de cada institución. Bandeja visual local implementada: categorías, instituciones, dos vistas, carga y revisión documental. Openbank, Mifel, BanCoppel, DiDi y Plata PDF tienen plan e importación al libro financiero; Fondeadora añade importación de estados operativos completos con revisión de moneda; Mifel y DiDi figuran como una sola cuenta remunerada por institución; SuperTasas confirma efectivo y conserva posiciones como observaciones documentales; Hey confirma pagos de la cuenta operativa y conserva pagarés/propuestas de reinversión separados; Kapital añade pagos operativos en ambos formatos y comisiones/devoluciones separadas; Doopla añade efectivo por componentes y cartera/atrasos observados, con retención desconocida o parcial explícita; Fintual muestra efectivo del portafolio y fondos observados por separado; Fintual USD añade efectivo USD con dividendos/retención extranjera y posiciones observadas; YoTePresto añade apertura acreditada, revisión de pagos múltiples y cancelaciones enlazadas con sus netos; CETESdirecto añade efectivo liquidado, cobros sin desglose e interés informado/clasificado separados; resumen patrimonial completo y demás instituciones pendientes.

## Navegación

El resumen global es una entrada independiente. Las categorías de la barra lateral son:

| Categoría | Segundo nivel | Tercer nivel |
| --- | --- | --- |
| Bancos | Institución | Cuenta de débito / Inversiones |
| SOFIPOs | Institución | Cuenta de débito / Inversiones |
| SOFOMes | Institución | Cuenta de débito / Inversiones |
| Instituciones de préstamo | Institución o plataforma | Cuenta de débito / Inversiones |
| Acciones | Institución o plataforma | Cuenta de débito / Inversiones |
| Criptomonedas | Exchange, plataforma o wallet | Cuenta de débito / Inversiones |
| FIBRAs | Institución o plataforma | Cuenta de débito / Inversiones |

Las FIBRAs permanecen en el alcance acordado previamente. CETESdirecto y Fintual se agrupan visualmente en Fondos y deuda; Por clasificar conserva las instituciones de categoría no confirmada. Esta agrupación configurable no determina régimen fiscal.

Una institución sin cuenta de débito mostrará «No aplica» en esa vista. No inventar una cuenta bancaria para exchanges, wallets o intermediarios. El detalle de inversiones podrá tener productos a la vista, contratos a plazo y otros instrumentos según corresponda.

## Dos vistas, dos lectores

Cada institución tendrá dos entradas de lectura independientes:

- **Débito:** lectura de la cuenta operativa, saldos y movimientos. Sirve para rastrear entradas, salidas y transferencias; no calcula rendimiento de la inversión ni convierte gasto de tarjeta en parte de la cartera.
- **Inversiones:** lectura de los productos que generan rendimiento, con aportaciones, retiros, cobros, retenciones, reinversiones, contratos y pendientes.

Pueden recibir el mismo PDF si contiene ambos productos. Comparten identidad documental, pero cada lector devuelve únicamente su sección, evidencia y conciliación.

Un lector no sustituye a otro si falta una sección. Los traspasos se enlazan entre ambas vistas para explicar aportación y retiro sin duplicar capital externo.

La vista de débito no implica ampliar el alcance a presupuesto de gastos personales o gestión de tarjeta de crédito. Se conserva el límite acordado.

## Resumen general

Debe distinguir patrimonio, capital externo aportado, rendimientos cobrados, retenciones documentadas y pendientes. Separar monedas/activos hasta disponer de valoración y tipo de cambio con fecha. No sumar un saldo de débito y su inversión como dos inversiones.

Una cuenta o posición tendrá un identificador único aunque pueda consultarse desde varias categorías. La agrupación visual no duplica movimientos ni participaciones.

## Presentación

Estilo GitHub oscuro: jerarquía clara, navegación lateral, pestañas de institución, tablas legibles, cifras explicables y acceso al documento/página. Evitar un tablero genérico de tarjetas sin contexto.

La revisión de importación tendrá vista previa, diferencias y estado de conciliación antes de confirmar. Consulta local offline; fuentes externas y sincronización requieren conexión.

Identidad corregida por el titular: Fintual MXN y Fintual USD pertenecen a Fintual. El perfil Alpaca queda como custodio/formato técnico, fuera del catálogo de instituciones. Cada portafolio conserva unidad, cuenta y movimientos separados.


## Evolución implementada

El libro financiero presenta tablas por categoría/institución/cuenta/moneda, filtro de cuenta y períodos documentales cronológicos. Cada fila muestra apertura, aportaciones, retiros, interés, retención, neto y cierre; su detalle abre componentes, diferencias y documento. Los huecos y cambios posteriores del libro son visibles. No suma monedas o valuaciones ni transforma cortes en meses naturales. [Manual de evolución](EVOLUCION.md).


## Nu en el libro

Cuenta Nu, Cajitas agregadas y garantía acreditada se muestran como cuentas separadas por producto. Las dos vistas documentales permanecen disponibles. La revisión de apertura/distribución global antecede a la confirmación; saldo disponible/congelado y cambios por nombre quedan como observaciones, sin duplicar activos. [Manual de importación](IMPORTACION-NU.md).


Cajitas individuales Nu: cada nombre acreditado aparece como producto propio en resumen/evolución, con su apertura/cierre/bruto/ISR. El total Cajitas queda como control; no representa otra cuenta. Congelado/disponible permanecen subconjuntos observados.
