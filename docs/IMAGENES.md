# Lectura de fotos y capturas

## Estado implementado

Las 28 vistas documentales existentes aceptan imágenes mediante read_image. BingX y Pionex tienen, además, lectores de capturas de operaciones; el catálogo suma 30 entradas. Se mantienen los lectores PDF existentes.

El motor es Tesseract local, con Pillow para abrir la imagen. No se contratan APIs, no se requiere tarjeta ni cuenta de un proveedor OCR. Una vez instalados el motor y los modelos de idioma, la lectura funciona offline. Instalar paquetes/modelos y actualizar GitHub sí necesita conexión.

La interfaz de carga visual todavía no está construida. Esta entrega incluye API Python y consola local. El resultado es una vista previa con revisión pendiente; no crea movimientos ni aprueba documentos.

## Instalación para desarrollo

En Debian/Ubuntu:

```sh
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-spa
python -m pip install -r requirements-pdf.txt -r requirements-image.txt
```

En Windows se necesita el ejecutable local tesseract en PATH, con los modelos de inglés/español instalados, además de los paquetes Python. No se ha validado todavía una instalación Windows del proyecto.

El lector consulta los idiomas locales. Prefiere spa+eng cuando ambos están disponibles; si solo usa inglés, conserva una advertencia. Un idioma solicitado que no está instalado produce un error explícito.

Referencia técnica: [documentación de Tesseract](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html).

## Usar imágenes en una institución

```python
from pathlib import Path
from finanzas.readers import reader_for

image = Path("captura_privada.jpg").read_bytes()
preview = reader_for("mifel", "investments").read_image(image)
print(preview.issues)
```

read_document detecta PDF por su contenido; para otros archivos usa el lector de imagen. No confía en la extensión. Las clases específicas OpenbankDebitReader y OpenbankInvestmentReader también ofrecen read_image.

```sh
python -m finanzas.readers captura_privada.jpg --institution mifel --lane investments
python -m finanzas.readers operacion_privada.png --institution bingx --lane investments --ocr-language eng
```

La consola muestra estado y nombres de campos, sin valores financieros por defecto. --details imprime la evidencia y valores privados para revisión local; no publicar esa salida en GitHub.

## Evidencia y calidad

- Huella SHA-256 de los bytes originales; la entrada no se modifica.
- Tamaño original, tamaño de trabajo, formato, idioma y orientación EXIF aplicada.
- Texto, rectángulo y confianza mínima de palabras por línea.
- Coordenadas relativas a la imagen de trabajo ya orientada, no a la imagen original sin rotación.
- Confianza inferior a 85 genera una alerta. Ese valor es una medida del OCR, no una probabilidad garantizada de exactitud.
- Se conserva el texto dudoso: nunca se convierte automáticamente O en 0, I en 1 ni se inventan signos o decimales.

El lector recibe bytes y devuelve evidencia; no archiva la imagen ni sus copias. El llamador debe conservar el archivo original privado. La base de datos actual solo registra la referencia documental cuando se use su flujo de revisión; no almacena imágenes dentro de SQLite.

Una imagen sin texto no significa saldo cero. Identidad institucional no visible, fechas ilegibles y columnas dudosas quedan pendientes. La conciliación del PDF de Openbank no se hereda a su versión fotografiada.

## Formatos y límites

Se admiten PNG, JPEG, WebP, BMP y TIFF de una sola imagen, hasta 30 millones de píxeles. El límite del proceso OCR es 45 segundos por llamada. TIFF multipágina debe separarse antes de leerlo. HEIC, corrección automática de perspectiva y reconstrucción de tablas OCR no están implementados.

Las fotos pueden tener desenfoque, reflejos, rotaciones sin EXIF, recortes o fondos oscuros. El motor intenta leerlas, pero esos casos requieren comprobar el original. No se promete exactitud por detectar texto con confianza alta.

Varias fotos no se unen automáticamente como si fueran un estado completo. Mantienen evidencia independiente; las relaciones entre páginas o capturas se resolverán durante revisión.

## Revisión pendiente

ready_to_import es siempre False para OCR. El análisis documental existente puede aprovechar el texto reconocido cuando la identidad y el formato son compatibles, pero no se confirma su contabilidad.

Los originales privados, capturas, texto reconocido y datos de cuentas quedan fuera del repositorio público. Las pruebas generan imágenes ficticias en memoria o en archivos temporales.
