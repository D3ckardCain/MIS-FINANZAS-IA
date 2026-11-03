# MIS-FINANZAS-IA

Control de inversiones por institución y producto, con evidencia documental y resumen patrimonial separado. Proyecto en construcción.

## Estado actual

Primera entrega: reglas acordadas, plan de trabajo y núcleo local de movimientos **en memoria**, con pruebas sintéticas. Todavía no hay aplicación visual, base de datos, importador de estados, conexión bancaria ni cálculo de declaración anual. No se han importado datos reales.

El núcleo distingue aportaciones, retiros, intereses cobrados, ISR retenido, comisiones y saldos iniciales. Enlaza transferencias propias y reinversiones entre cuentas sin duplicar aportaciones externas ni intereses.

## Ejecutar las pruebas

Python 3.11 o posterior; biblioteca estándar, sin instalar paquetes:

```sh
python -m unittest discover -v
```

Las pruebas y el núcleo funcionan offline. Este incremento no requiere tarjeta, API, servidor, suscripción ni servicios externos. Consultar o actualizar GitHub sí requiere conexión. Los costos y límites de cualquier futura dependencia se revisarán antes de adoptarla.

## Documentación

- [Alcance y reglas acordadas](docs/REQUISITOS.md)
- [Decisiones y alternativas](docs/DECISIONES.md)
- [Plan, pendientes y criterios de aceptación](docs/PLAN.md)
- [Manual del núcleo y limitaciones](docs/NUCLEO.md)
- [Registro de avances](docs/AVANCES.md)

## Datos privados

Este repositorio es público. Solo contiene código, documentación general y ejemplos ficticios. Los estados de cuenta, documentos fiscales, datos personales, credenciales y registros financieros reales quedan fuera del repositorio. El Excel se utilizará después como referencia para detectar documentos faltantes; no será importado como movimientos.

No hay motor fiscal ni recomendaciones de inversión implementados.
