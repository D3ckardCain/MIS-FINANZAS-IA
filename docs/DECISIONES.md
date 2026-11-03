# Decisiones y alternativas

## D001 — Base local sin dependencias externas obligatorias

**Decisión:** núcleo Python con biblioteca estándar; SQLite local es la primera opción a evaluar para persistencia. No se ha creado aún la base de datos.

**Ventajas:** ejecución offline, portabilidad, sin API ni suscripción obligatoria; pruebas reproducibles.
**Costo y límites:** requiere equipo propio y Python; no ofrece por sí solo acceso remoto, sincronización, respaldo ni cifrado.
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
