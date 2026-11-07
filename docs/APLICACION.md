# Aplicación local: carga y organización documental

## Abrir

Requiere Python 3.11 o posterior y los extras existentes del repositorio:

```sh
python -m pip install -r requirements-pdf.txt -r requirements-image.txt
python -m finanzas.app
```

En Windows también se puede abrir `iniciar.bat`, una vez instaladas las dependencias. El navegador se abre en la dirección local que imprime el programa. Cerrar la pestaña no detiene el servicio; Ctrl+C en la consola lo detiene. Para usar un entorno virtual, activar ese entorno antes de iniciar.

La base predeterminada es `MIS-FINANZAS-IA/bandeja.sqlite3` dentro de LOCALAPPDATA en Windows o del directorio personal en otros sistemas. Está fuera del repositorio. Se puede elegir otra ruta con `--data RUTA` y otro puerto con `--port NUMERO`. `--no-browser` evita abrir automáticamente el navegador.

## Subir un archivo

1. Pulsar **Subir documento** y seleccionar un PDF o una imagen. Se admite un archivo por vez, de hasta 32 MiB.
2. La aplicación lee el contenido, identifica la institución y ejecuta sus dos lectores. No usa el nombre del archivo como fecha o identidad del emisor.
3. El original y el resultado se guardan juntos en SQLite. Volver a cargar exactamente el mismo archivo abre su registro existente, incluso con otro nombre. Documentos distintos que describan operaciones iguales todavía requieren conciliación económica.
4. Abrir **Cuenta de débito / operativa** o **Inversiones** para consultar los datos y sus alertas. Las tablas largas se paginan en grupos de cien filas sin eliminar registros guardados.

Una contraparte de transferencia puede mencionar otro banco: las declaraciones explícitas del emisor tienen prioridad. Si la identificación continúa ambigua, la aplicación pide elegir institución y vuelve a verificarla contra el contenido.

Si el PDF está protegido, el formulario solicita la contraseña. Se usa en memoria para ese intento, se borra del campo al enviarla y no se guarda en la base ni en logs. El lector específico de SuperTasas admite el PDF protegido; otros perfiles pueden conservar una lectura documental pendiente de conciliación.

Las imágenes usan el motor Tesseract y sus idiomas instalados localmente; consultar [manual de imágenes](IMAGENES.md). Cuando falta el motor o no puede leerse el formato, el archivo conserva su estado de revisión. Los PDF escaneados sin texto quedan identificados como necesitados de OCR; el renderizado/OCR automático multipágina todavía está pendiente. Se puede aportar una foto de cada página.

## Consultar y revisar

- La barra lateral organiza categorías e instituciones. La agrupación de navegación se puede cambiar y se conserva al reiniciar; no define el régimen fiscal histórico.
- **Fondos y deuda** agrupa CETESdirecto/Fintual. Instituciones cuya categoría no se ha confirmado aparecen en **Por clasificar**, sin inventar su naturaleza jurídica.
- **Descargar original** recupera exactamente los bytes guardados.
- **Marcar como revisado** registra una revisión documental con versión. Mantiene las alertas visibles y no importa movimientos al libro financiero.
- Reprocesar genera una nueva revisión del resultado y devuelve el documento a pendientes. Dos acciones sobre versiones distintas se rechazan para evitar sobrescribir una revisión reciente.

## Alcance de esta entrega

Implementado: aplicación visual local, carga individual PDF/imagen, detección, lectores por vista, archivo de originales, duplicados binarios, persistencia/reapertura, consulta, categorías y revisión documental.

Openbank, Mifel, BanCoppel, DiDi y Plata PDF, y estados operativos completos Fondeadora, disponen de plan financiero, confirmación al ledger y consulta de cierres por producto. Mifel y DiDi conservan una sola cuenta remunerada por institución en sus dos vistas. Ver [manual de Openbank](IMPORTACION-FINANCIERA.md), [manual de Mifel](IMPORTACION-MIFEL.md), [manual de BanCoppel](IMPORTACION-BANCOPPEL.md), [manual de DiDi](IMPORTACION-DIDI.md), [manual operativo Fondeadora](IMPORTACION-FONDEADORA.md) y [manual de Plata](IMPORTACION-PLATA.md). Siguiente trabajo: extender la normalización a las demás instituciones, resolver referencias/traspasos/reinversiones y completar el resumen patrimonial. Guardar una lectura documental no equivale a confirmar movimientos. No se presentan sumas patrimoniales de observaciones o saldos superpuestos.

Las constancias fiscales tienen lectores independientes; todavía falta conectarlas a este flujo visual. Tampoco hay cálculo fiscal anual, conexión bancaria, sincronización, notificaciones, valoraciones de mercado ni recomendaciones de inversión.

## Operación y costo

Funciona sin Internet después de instalar Python, las bibliotecas y, para imágenes, el motor OCR. Interfaz, fuentes y archivos son locales; no hay CDN, API de pago ni servicio de nube obligatorio. La disponibilidad depende del equipo y del espacio en disco propios; el volumen de datos aumenta con originales y resultados. El procesamiento es secuencial y puede tardar en estados extensos. No se ha probado aún instalación en el equipo Windows del titular.

El servidor escucha exclusivamente en `127.0.0.1`, verifica Host/Origin y exige un token local para cambios. No publica el archivo en la LAN ni en Internet. La base contiene documentos y datos sensibles sin cifrado propio: conserva las protecciones normales del equipo. La aplicación no modifica los estados fuente compartidos ni usa Excel como fuente de movimientos.

Validación: pruebas HTTP de carga/consulta/descarga, duplicados, revisión y control de origen; pruebas de reapertura SQLite, detección, PDF protegido, OCR y precisión decimal. La inspección visual en navegador usó datos ficticios; la prueba del transporte HTTP ejecutó el servidor real.

SuperTasas también permite confirmar efectivo a la vista y guardar posiciones a plazo como observaciones fechadas, sin convertir proyecciones en cobros o generar una segunda cuenta. Los pagos a plazo sin desglose acreditado de bruto/retención quedan bloqueados. Ver [manual SuperTasas](IMPORTACION-SUPERTASAS.md), incluido el desbloqueo temporal de PDF protegido sin guardar la contraseña.

Hey permite confirmar principal, interés bruto e ISR pagados en la cuenta operativa, conservando pagarés y propuestas de renovación como observaciones pendientes, sin segunda cuenta contable o reinversión automática. Las diferencias de contratos bloquean el lote completo aunque el efectivo concilie. Ver [manual Hey](IMPORTACION-HEY.md), con moneda revisada y contraseña transitoria para originales protegidos.

Kapital confirma pagos operativos en los dos formatos reconocidos y guarda pagarés como observaciones. Timbrado y descuento conservan sus filas; la devolución de comisión no se cuenta como capital o interés y los cargos se muestran netos. Ver [manual Kapital](IMPORTACION-KAPITAL.md), incluidos moneda y contraseña transitoria.

Doopla confirma efectivo por componentes, con IVA recibido/pagado y recompensas separados. Cartera y atrasos son observaciones; ISR ausente o cobertura mensual parcial dejan desconocidos la retención total y el neto. Ver [manual Doopla](IMPORTACION-DOOPLA.md), incluidos moneda, contraseña transitoria y bloqueo de anexos repetidos con actividad de capital.

Fintual confirma efectivo del portafolio y conserva fondos/valuación/rendimiento/ISR informativo como observaciones. El libro distingue su efectivo del total de fondos; la retención de efectivo permanece desconocida hasta acreditar su asignación. Ver [manual Fintual](IMPORTACION-FINTUAL.md).

Fintual USD confirma efectivo USD con dividendos, intereses, comisiones y retención extranjera separados. Posiciones/costo/resultados son observaciones; no se calcula ISR mexicano, ganancia por lote o conversión a MXN. Ver [manual Fintual USD](IMPORTACION-ALPACA.md).

YoTePresto permite revisar expresamente la apertura candidata de efectivo o enlazarla a un cierre contiguo confirmado compatible. Admite pagos/retenciones múltiples con desglose por fila revisado cuando falta, y cancelaciones enlazadas a originales, con componentes netos y controles por préstamo. Nunca convierte el saldo global en efectivo. Ver [manual YoTePresto](IMPORTACION-YOTEPRESTO.md).

CETESdirecto confirma efectivo por fecha de liquidación y registra ventas/amortizaciones como cobros sin desglose de principal/interés. El libro distingue interés informado del clasificado; este último y el neto permanecen desconocidos si falta asignación. Ver [manual CETESdirecto](IMPORTACION-CETESDIRECTO.md).

### Moneda ausente en un estado operativo Fondeadora

El plan pide revisar la moneda dentro de la aplicación. Seleccionar MXN y aplicar la revisión prepara un plan confirmable solo si el resto concilia; elegir otra moneda/no poder comprobarla mantiene el documento pendiente. Esta decisión queda en el plan aceptado, sin editar el original o su moneda extraída. Un reporte sin saldos no se habilita mediante esta selección.

Identidad corregida por el titular: Fintual MXN y Fintual USD pertenecen a Fintual. El perfil Alpaca queda como custodio/formato técnico, fuera del catálogo de instituciones. Cada portafolio conserva unidad, cuenta y movimientos separados.
