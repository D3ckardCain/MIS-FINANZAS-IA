# Decisiones y alternativas

## D001 — Base local sin dependencias externas obligatorias

**Decisión:** núcleo Python con biblioteca estándar y persistencia SQLite local implementada en el segundo incremento.

**Ventajas:** ejecución offline, portabilidad, sin API ni suscripción obligatoria; pruebas reproducibles.
**Costo y límites:** requiere equipo propio y Python; no ofrece por sí solo acceso remoto, sincronización ni cifrado; las copias de la base se gestionan mediante Store.
**Alternativas:** servicios alojados pueden simplificar despliegue pero sus cuotas, tarjeta y continuidad deben verificarse antes de seleccionarlos.
**Revisión:** escoger interfaz y distribución cuando el flujo documental esté definido. No se eligió un proveedor de nube.

## D002 — Dos niveles de aportación

**Decisión:** aportación a una inversión y capital externo global son conceptos separados. Un traslado propio conserva retiro y aportación enlazados.
**Ventaja:** permite explicar el saldo de cada cuenta sin inflar el patrimonio.
**Límite:** los vínculos pendientes o importes distintos exigen conciliación, no emparejamiento por coincidencia casual.
**Primera implementación:** pares del mismo importe/unidad y origen, entre dos cuentas distintas; fechas efectivas pueden diferir.
**Pendiente:** asignaciones múltiples, comisiones de red, conversiones y dinero en tránsito. No sumar cuentas en distintas unidades como si fueran MXN.

## D003 — Evidencia antes de automatización

**Decisión:** comenzar con estados reales revisados, adaptador por formato y vista previa antes de confirmar. Excel solo como referencia posterior.
**Ventaja:** evita trasladar errores de fórmulas o suposiciones a la base.
**Límite:** necesita revisión inicial por institución y seguimiento de faltantes.

## D004 — Separar cobro, reinversión y fiscalidad

**Decisión:** rendimiento cobrado, retención y traslado a nuevo contrato son movimientos distintos.
**Ventaja:** renovación no duplica ingreso ni nueva aportación externa.
**Límite:** el primer núcleo no calcula tasas, intereses futuros, costo fiscal ni declaración; tampoco atribuye automáticamente capital/interés a un traslado.

## D005 — Repositorio público con datos sintéticos

**Decisión:** registrar requisitos, código, problemas y soluciones generales; mantener estados y datos privados fuera de Git.
**Ventaja:** documentación revisable sin publicar información financiera.
**Límite:** el historial público no sustituye el archivo privado ni la futura auditoría local de movimientos.
**Prevención:** exclusiones de Git para formatos documentales y bases locales; no sustituyen revisar cada cambio antes de publicarlo.

## D006 — Entregas pequeñas verificables

**Decisión:** cerrar un incremento funcional por vez con pruebas que comprueben reglas financieras.
**Ventaja:** discutir problemas concretos y preservar decisiones.
**Límite:** una prueba del núcleo no valida un importador, una tasa contractual o una obligación fiscal.

## D007 — Persistencia con revisión y versiones

**Decisión:** SQLite local, importes Decimal como texto y lotes transaccionales. Las correcciones crean versiones con motivo y control de versión esperada.
**Ventajas:** conservación de evidencia e historial, recuperación local y ausencia de suscripción.
**Límites:** un escritor a la vez; validación del ledger completo en memoria. No guardar archivos originales dentro de la base en este incremento.
**Alternativa:** otro motor relacional si el volumen o la concurrencia lo justifican; el modelo de IDs/evidencia y los valores decimales son portables.

## D008 — Pruebas de disco en GitHub, aplicación independiente

**Decisión:** CI con Ubuntu estándar solo en repositorio público; sin artifacts ni cachés. Ejecución local de pruebas sigue siendo suficiente para desarrollar.
**Costo verificado:** los runners estándar en repositorios públicos no generan cargos de cómputo según [GitHub](https://docs.github.com/en/billing/concepts/product-billing/github-actions), consultado el 2026-11-03.
**Límites:** conexión, disponibilidad y políticas de GitHub; el workflow se omite si el repositorio pasa a privado. No se usan runners de mayor capacidad ni servicios de pago.

## D009 — Dos lectores y dos vistas por institución

**Decisión del titular:** categorías separadas, instituciones dentro de ellas y dos vistas por institución: Cuenta de débito e Inversiones. Resumen global aparte.
**Implementación inicial:** OpenbankDebitReader y OpenbankInvestmentReader procesan secciones independientes del mismo documento.
**Ventaja:** trazabilidad del dinero sin mezclar gasto operativo con rendimiento ni duplicar transferencias.
**Límites:** no todas las plataformas tienen débito; mostrar No aplica. La navegación aprobada está especificada, todavía no construida.

## D010 — Vista previa antes de importar

**Decisión:** los lectores de Openbank devuelven datos y controles, sin guardar ni aprobar.
**Ventaja:** la revisión de evidencia e identidad ocurre antes del registro.
**Límite:** ausencia de referencias estables o formato desconocido debe resolverse; un saldo que cuadra no basta para autorizar una importación automática.

## D011 — Imágenes como evidencia con OCR local

**Decisión del titular:** todos los lectores admitirán foto/captura cuando no haya PDF; BingX/Pionex usarán capturas de operaciones.
**Implementación:** Tesseract local y Pillow. El OCR conserva texto, coordenadas, confianza y huella original; no crea movimientos.
**Ventajas:** funcionamiento offline después de instalar dependencias, sin tarjeta, API de pago ni envío a proveedor OCR. Modelos y formatos portables.
**Límites:** instalación del ejecutable/modelos, consumo del equipo propio, calidad de imagen y revisión necesaria. No hay carga visual ni archivo de originales implementados.
**Cripto:** unidades explícitas, Decimal, órdenes/fills distintos, PnL por tipo y bot separado de sus operaciones. No se supone que la captura sea el historial completo.

## D012 — La aplicación procesa; el chat desarrolla y verifica

**Aclaración del titular:** los PDF compartidos sirven para programar/probar. La prioridad es que el usuario suba los documentos a la aplicación y esta organice y procese sus datos. La ausencia temporal de estados no bloquea el desarrollo.
**Implementación:** interfaz web local con biblioteca estándar, JavaScript/CSS locales y SQLite documental separado del ledger. Conserva originales, salidas por vista y revisión versionada. Sin dependencias nuevas, nube o pagos obligatorios.
**Límites:** esta entrega archiva y consulta extracciones; falta normalizar y confirmar operaciones financieras en el ledger. No confundir revisión documental con importación contable. Procesamiento secuencial, PDF escaneado multipágina y constancias visuales pendientes.

## D013 — Plan financiero y anclas documentales por período

**Decisión:** primera normalización confirmable para Openbank PDF. Plan recalculado desde el original, revisión y estado del ledger; confirmación en una única transacción con aprobación/evidencia/cobertura.
**Ventaja:** reintentos no duplican, fallos no dejan importaciones parciales, y traspasos internos mantienen reducción/aportación enlazadas.
**Historia:** apertura y cierre se conservan como anclas por período; no se generan aportaciones ni aperturas mensuales acumulables. Esto admite meses fuera de orden. El libro muestra el último cierre documental por cuenta y fecha; el neto de movimientos del ledger sin apertura no se presenta como saldo total.
**Límites:** sin deduplicación económica inferida entre documentos: solapamientos bloqueados, huecos visibles y diferencias de continuidad pendientes. Orígenes de débito desconocidos no se cuentan como capital externo acreditado. Las demás instituciones conservan sus lectores, sin confirmar automáticamente sus salidas.

## D014 — Mifel comparte cuenta entre las dos vistas

**Decisión:** las pestañas operativa e inversión representan la misma cuenta remunerada. Se confirma un solo período y un lote único, con origen SPEI pendiente y sin transferencia ficticia entre pestañas.
**Cobros:** interés bruto e ISR de filas se conservan separados; los grupos netos y el resumen no originan movimientos adicionales. Fecha de cobro y rango remunerado permanecen independientes. Tasas/GAT se guardan como datos históricos.
**Control:** cuenta/período/folio identifica cada fila del formato; solapamientos se bloquean. Se reutilizan transacción atómica, versión del plan, anclas y continuidad. El libro distingue institución y cuenta, con interés menos ISR explícito para consulta.
**Límites:** falta enlace entre instituciones, correcciones, otros productos y confirmación desde imágenes. La retención no determina por sí misma el impuesto anual.

## D015 — BanCoppel como cuenta de paso

**Decisión:** confirmar débito como aportaciones/reducciones operativas con origen pendiente, sin inferir rendimiento, capital externo o transferencia propia. Comisiones e IVA son cargos de filas, separados del ISR. Solo un interés explícito es ingreso por interés.
**Identidad y moneda:** cuenta única y leyenda de moneda nacional requeridas; símbolo dólar, ausencia o contradicción no acreditan MXN. Fechas se resuelven por el período interior, incluido cambio de año.
**Control:** anclas y continuidad de períodos, evidencia por fila, bloqueo de solapamientos, confirmación atómica y reintentos idempotentes. Depósitos iguales legítimos se conservan; no se enlazan por coincidencia de importe/fecha.
**Límites:** falta conciliación entre instituciones/origen de efectivo y devoluciones, otros productos, imágenes y formatos con retención no nula. No se abre una inversión desde la pestaña adicional.

## D016 — DiDi: interés incluido en depósitos y cuenta compartida

**Decisión:** confirmar una cuenta y un período compartidos por las dos vistas. Los depósitos del resumen incluyen interés, pero el ledger registra capital e interés por sus filas, sin sumarlos dos veces.
**Identidad:** referencia de operación acotada a cuenta/período; se conservan continuaciones, fechas y evidencia. Operaciones iguales con folios distintos permanecen separadas; estados solapados se bloquean.
**Condiciones:** tasas y texto de escalones/topes se guardan como información histórica del estado; fecha de cálculo no se interpreta como inicio contractual ni se aplica una tasa única.
**Límites:** transferencias con origen pendiente, retención no nula sin formato admitido bloqueada, sin reinversión inferida o cálculo SAT. Reutiliza controles de normalización, continuidad, versiones y transacción atómica.

## D017 — Fondeadora operativa y moneda acreditada o revisada

**Decisión:** confirmar únicamente estados operativos completos y conciliados. Reportes sin apertura/cierre permanecen evidencia parcial; saldo operativo cero no acredita saldo cero de Bóveda. Traspasos/Apartados registran flujo operativo con origen/destino pendientes, sin cuenta o propiedad inventada.
**Moneda:** la extracción conserva moneda desconocida si no aparece. La aplicación permite revisión explícita MXN para ese documento, vinculada al plan/revisión y conservada al confirmar. No puede sobrescribir moneda extranjera/contradictoria ni habilitar otros conceptos faltantes.
**Control:** apertura/cierre y totales normalizados, fechas sin reordenar, conceptos no mapeados bloqueados, tasas vacías distintas de cero y transacción/idempotencia existentes. Sin nuevas dependencias, servicios, tablas de preferencias globales o cambios al original.
