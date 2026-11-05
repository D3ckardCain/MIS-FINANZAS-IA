# Openbank: constancias PDF y XML

`OpenbankTaxReader` lee por separado el PDF de cada producto y su XML de retenciones. La constancia es evidencia fiscal, sin crear otro ingreso, otra aportación ni otra retención en los movimientos mensuales.

```bash
python -m finanzas.openbank_tax constancia.pdf
python -m finanzas.openbank_tax exportacion_xml.txt
```

La extensión no decide el formato: un archivo `.txt` puede contener XML con envoltura multipart. El lector admite XML directo o un único adjunto XML multipart. Conserva la huella del archivo original. Rechaza partes múltiples, DTD/entidades, formatos desconocidos y archivos de más de 8 MiB. No descarga esquemas, certificados ni recursos externos.

La consola muestra período, producto, conteos e incidencias. `--details` incluye cantidades, UUID y datos fiscales sensibles. PDF e imagen usan las dependencias locales existentes; el XML solo usa Python estándar. `read_image` conserva evidencia OCR revisable y no hereda las verificaciones estructuradas de PDF/XML.

## Datos distintos por producto

El PDF identifica Cuenta Débito Open Light o Apartado Open, período anual, referencia de producto/cliente, folio y UUID. Se preservan operación, gravado, exento, retención, nominal, real y pérdida inflacionaria. La repetición de retenciones se coteja; no se suma dos veces. No se equipara pérdida inflacionaria con una resta simple ni interés real con neto cobrado.

El XML admite retenciones 2.0, complemento de intereses 1.0 y timbre 1.1. Conserva referencia, emisor/receptor, período, UUID, cantidades y código de pago. La cuenta de una addenda se coteja con el folio y sus importes con el interés nominal. Los IDs de movimiento permanecen como texto exacto, sin redondearlos como números.

`compare_tax_formats(pdf, xml)` exige mismo UUID, período, emisor, receptor y referencia para identificar las dos representaciones del comprobante. Compara cada importe de manera independiente. Una igualdad de cantidades con UUID o producto diferentes no vincula constancias. Diferencias o incidencias bloquean el cotejo con la addenda; no se corrigen usando una representación como sustituta de la otra.

## Meses y addenda

```python
from finanzas.openbank_tax import OpenbankTaxReader, compare_tax_formats, compare_tax_months
reader = OpenbankTaxReader()
pdf = reader.read_pdf(pdf_bytes)
xml = reader.read_xml(xml_bytes)
formats = compare_tax_formats(pdf, xml)
review = compare_tax_months(pdf, monthly_previews, xml=xml)
```

`compare_tax_months` filtra la vista y período explícitos. Exige identidad compatible del receptor, una sola cuenta y meses completos. Deduplica archivos binarios, rechaza metadatos incompatibles y versiones distintas del mismo mes. Enumera los meses ausentes.

`observed_totals_match` indica igualdad de los totales observados de interés y retención con la constancia. **No acredita un año completo cuando `missing_months` tiene elementos.** Un estado recibido con saldo inicial cero no prueba que no existiera actividad anterior.

Las filas de addenda se cotejan con interés de débito por cuenta, fecha, importe y concepto explícito, con correspondencia única. Coincidencias ambiguas quedan pendientes. Es un cotejo de evidencia, sin importar de nuevo esas filas ni deduplicar otras operaciones solo por fecha/importe. El código restringe este cotejo de addenda al formato de cuenta débito reconocido; no deduce la vista de un XML aislado.

La referencia llamada «Número de cliente»/«Folio interno» del PDF no se equipara automáticamente al número de cuenta. Las correspondencias se entregan para revisión; `identity_link_confirmed=False`. La identidad del Apartado basada en la cuenta padre es documental, no un identificador fiscal propio demostrado.

## Límites

`signature_verified=False`: comparar XML/PDF no verifica criptografía del sello, autenticidad, vigencia ni estado ante SAT. No se consulta SAT. Los códigos/tipos de pago se conservan tal como aparecen, sin convertirlos en impuesto anual definitivo o cálculo de saldo a pagar/devolver.

`ready_to_import=False` siempre. Las constancias no rellenan automáticamente huecos mensuales. Retención cero no determina exención o deuda fiscal. No se aplican tasas actuales al pasado, reglas fiscales inferidas ni datos de Excel. Los informes y documentos reales permanecen privados; las pruebas del repositorio son ficticias.
