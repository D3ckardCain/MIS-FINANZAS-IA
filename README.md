# MIS-FINANZAS-IA

Control de inversiones por institución y producto, con evidencia documental y resumen patrimonial separado. Proyecto en construcción.

## Estado actual

Núcleo local de movimientos y persistencia SQLite con evidencia documental, revisión explícita, correcciones versionadas y copias recuperables. Pruebas exclusivamente sintéticas. Hay un catálogo de dos vistas para las 15 instituciones con formatos disponibles (30 entradas), todas con entrada PDF/imagen, más dos lectores de capturas de operaciones de BingX/Pionex (32 entradas en total). Openbank tiene conciliación específica y BanCoppel, CETESdirecto, DiDi, Doopla, Fintual, Alpaca, Hey, Kapital, Mifel, SuperTasas y Plata ofrecen conciliación PDF detallada optativa; YoTePresto añade resumen, diario operativo y observaciones de préstamos con controles separados; Nu añade resumen, cambios por Cajita/garantía, pareo de traspasos y candidatos de vencimiento; los cierres individuales sin desglose documental permanecen bloqueados. Fondeadora añade revisión operativa y evidencia de traspasos, con saldo de Bóveda pendiente; los otros perfiles extraen evidencia documental y requieren mapeo económico antes de importar. Ya hay aplicación visual local con carga individual, detección, dos vistas, originales, duplicados y revisión documental. Openbank, Mifel, BanCoppel y DiDi PDF, y los estados operativos completos Fondeadora, tienen plan financiero y confirmación atómica al ledger; Mifel y DiDi conservan una sola cuenta por institución compartida entre vistas y BanCoppel se trata como cuenta de paso. Las demás instituciones permanecen en extracción/revisión documental. No hay conexión bancaria ni cálculo de declaración anual. No se han importado datos reales.

El núcleo distingue aportaciones, retiros, intereses cobrados, ISR retenido, comisiones y saldos iniciales. Enlaza transferencias propias y reinversiones entre cuentas sin duplicar aportaciones externas ni intereses.

## Abrir la aplicación

Después de instalar los extras indicados abajo, ejecutar `python -m finanzas.app` o abrir `iniciar.bat` en Windows. Funciona localmente sin Internet. [Manual y límites de la aplicación](docs/APLICACION.md).

## Ejecutar las pruebas

Python 3.11 o posterior. El núcleo y SQLite usan la biblioteca estándar; los lectores de PDF e imagen necesitan sus extras. El OCR requiere además Tesseract local (ver manual de imágenes):

```sh
python -m pip install -r requirements-pdf.txt -r requirements-image.txt
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
- [Aplicación: carga, consulta y revisión](docs/APLICACION.md)
- [Importación financiera: Openbank](docs/IMPORTACION-FINANCIERA.md)
- [Importación financiera: Mifel](docs/IMPORTACION-MIFEL.md)
- [Importación financiera: BanCoppel](docs/IMPORTACION-BANCOPPEL.md)
- [Importación financiera: DiDi](docs/IMPORTACION-DIDI.md)
- [Importación financiera: Fondeadora operativa](docs/IMPORTACION-FONDEADORA.md)
- [Estructura aprobada del panel](docs/PANEL.md)
- [Lectores de Openbank](docs/OPENBANK.md)
- [Cuenta e inversiones a plazo de SuperTasas](docs/SUPERTASAS.md)
- [Cuenta operativa y cartera de YoTePresto](docs/YOTEPRESTO.md)
- [Cuenta y ahorro flexible de Plata](docs/PLATA.md)
- [Constancias PDF/XML de Openbank](docs/OPENBANK_CONSTANCIAS.md)
- [Catálogo y manual de lectores](docs/LECTORES.md)
- [Mapeo económico pendiente por perfil](docs/MAPEO-PENDIENTE.md)
- [Lectura de fotos y capturas](docs/IMAGENES.md)
- [BingX/Pionex por imagen](docs/CRIPTO-IMAGENES.md)
- [Conciliación detallada de BanCoppel](docs/BANCOPPEL.md)
- [Conciliación de CETESdirecto](docs/CETESDIRECTO.md)
- [Conciliación de DiDi Cuenta](docs/DIDI.md)
- [Revisión de efectivo y cartera Doopla](docs/DOOPLA.md)
- [Fondos Fintual en MXN](docs/FINTUAL.md)
- [Acciones/ETF y efectivo Alpaca USD](docs/ALPACA.md)
- [Cuenta operativa y traspasos Fondeadora](docs/FONDEADORA.md)
- [Pagarés y reinversión Hey](docs/HEY.md)
- [Efectivo y pagarés Kapital](docs/KAPITAL.md)
- [Cuenta remunerada y rangos Mifel](docs/MIFEL.md)
- [Lectores y conciliación documental de Nu](docs/NU.md)
- [Constancias de intereses y retenciones de Nu](docs/NU_CONSTANCIAS.md)
- [Registro de avances](docs/AVANCES.md)

## Datos privados

Este repositorio es público. Solo contiene código, documentación general y ejemplos ficticios. Los estados de cuenta, documentos fiscales, datos personales, credenciales y registros financieros reales quedan fuera del repositorio. El Excel se utilizará después como referencia para detectar documentos faltantes; no será importado como movimientos.

No hay motor fiscal ni recomendaciones de inversión implementados.
