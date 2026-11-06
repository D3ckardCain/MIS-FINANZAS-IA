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

Openbank PDF ya dispone de plan financiero, confirmación al ledger y consulta de cierres por producto. Ver [manual de importación financiera](IMPORTACION-FINANCIERA.md). Siguiente trabajo: extender la normalización a las demás instituciones, resolver referencias/traspasos/reinversiones y completar el resumen patrimonial. Guardar una lectura documental no equivale a confirmar movimientos. No se presentan sumas patrimoniales de observaciones o saldos superpuestos.

Las constancias fiscales tienen lectores independientes; todavía falta conectarlas a este flujo visual. Tampoco hay cálculo fiscal anual, conexión bancaria, sincronización, notificaciones, valoraciones de mercado ni recomendaciones de inversión.

## Operación y costo

Funciona sin Internet después de instalar Python, las bibliotecas y, para imágenes, el motor OCR. Interfaz, fuentes y archivos son locales; no hay CDN, API de pago ni servicio de nube obligatorio. La disponibilidad depende del equipo y del espacio en disco propios; el volumen de datos aumenta con originales y resultados. El procesamiento es secuencial y puede tardar en estados extensos. No se ha probado aún instalación en el equipo Windows del titular.

El servidor escucha exclusivamente en `127.0.0.1`, verifica Host/Origin y exige un token local para cambios. No publica el archivo en la LAN ni en Internet. La base contiene documentos y datos sensibles sin cifrado propio: conserva las protecciones normales del equipo. La aplicación no modifica los estados fuente compartidos ni usa Excel como fuente de movimientos.

Validación: pruebas HTTP de carga/consulta/descarga, duplicados, revisión y control de origen; pruebas de reapertura SQLite, detección, PDF protegido, OCR y precisión decimal. La inspección visual en navegador usó datos ficticios; la prueba del transporte HTTP ejecutó el servidor real.
