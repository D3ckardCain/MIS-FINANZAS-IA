# MIS-FINANZAS-IA

Control de inversiones por institución y producto, con evidencia documental y resumen patrimonial separado. Proyecto en construcción.

## Estado actual

Núcleo local de movimientos y persistencia SQLite con evidencia documental, revisión explícita, correcciones versionadas y copias recuperables. Pruebas exclusivamente sintéticas. Hay dos lectores de Openbank que generan vistas previas conciliadas: débito e inversiones. Todavía no hay aplicación visual, confirmación de importación, conexión bancaria ni cálculo de declaración anual. No se han importado datos reales.

El núcleo distingue aportaciones, retiros, intereses cobrados, ISR retenido, comisiones y saldos iniciales. Enlaza transferencias propias y reinversiones entre cuentas sin duplicar aportaciones externas ni intereses.

## Ejecutar las pruebas

Python 3.11 o posterior. El núcleo y SQLite usan la biblioteca estándar; la lectura PDF y su prueba necesitan el extra local:

```sh
python -m pip install -r requirements-pdf.txt
python -m unittest discover -v
```

Una vez instalado el extra, las pruebas y los lectores funcionan offline. Las pruebas de núcleo y persistencia también pueden ejecutarse sin ese extra: `python -m unittest tests.test_ledger tests.test_storage`.

El núcleo funciona offline. Este incremento no requiere tarjeta, API, servidor, suscripción ni servicios externos. Consultar o actualizar GitHub sí requiere conexión. Los costos y límites de cualquier futura dependencia se revisarán antes de adoptarla.

## Documentación

- [Alcance y reglas acordadas](docs/REQUISITOS.md)
- [Decisiones y alternativas](docs/DECISIONES.md)
- [Plan, pendientes y criterios de aceptación](docs/PLAN.md)
- [Manual del núcleo y limitaciones](docs/NUCLEO.md)
- [Manual de persistencia](docs/PERSISTENCIA.md)
- [Estructura aprobada del panel](docs/PANEL.md)
- [Lectores de Openbank](docs/OPENBANK.md)
- [Registro de avances](docs/AVANCES.md)

## Datos privados

Este repositorio es público. Solo contiene código, documentación general y ejemplos ficticios. Los estados de cuenta, documentos fiscales, datos personales, credenciales y registros financieros reales quedan fuera del repositorio. El Excel se utilizará después como referencia para detectar documentos faltantes; no será importado como movimientos.

No hay motor fiscal ni recomendaciones de inversión implementados.
