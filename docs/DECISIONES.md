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
