# Nu: constancias de intereses y retenciones

El lector `NuTaxReader` conserva las constancias como evidencia anual o del período explícito. No crea aportaciones, intereses cobrados ni otra retención en el libro de movimientos. Los importes ya registrados en los estados mensuales no se suman de nuevo.

```bash
python -m finanzas.nu_tax constancia.pdf
python -m finanzas.nu_tax constancia.pdf --details
```

La salida habitual muestra período, comprobaciones y diferencias, sin cantidades, UUID o huellas personales. `--details` contiene información fiscal sensible. La lectura es local, con la dependencia PDF existente y sin servicios de pago.

## Campos y versiones documentales

Se reconoce la constancia Nu con cadena original versión 2.0 y complemento 1.0. Se conservan por separado portada y cadena: monto de operación, gravado, exento, retención total, base, retención del período, interés nominal, interés real y pérdida inflacionaria. También se conservan las etiquetas/códigos de pago e impuesto, indicadores, período, UUID, huellas de RFC y páginas de procedencia.

Se verifica identidad fiscal portada/cadena, período, formato y campos repetidos. Las diferencias entre representaciones quedan visibles en `differences`; no se elige una como corrección de la otra. Se coteja gravado más exento contra operación en cada representación y las dos etiquetas de retención. No se inventa una identidad entre interés nominal, real y pérdida inflacionaria.

La extracción de la cadena no verifica sello, firma, autenticidad, vigencia o estado del comprobante ante SAT. `signature_verified=False` y `ready_to_import=False` siempre. Emisores, formatos o períodos ambiguos se rechazan; versiones no reconocidas requieren un mapeo explícito.

## Comparación con estados mensuales

```python
from finanzas.nu_tax import NuTaxReader, compare_nu_tax
certificate = NuTaxReader().read_pdf(pdf_bytes)
review = compare_nu_tax(certificate, monthly_previews)
```

`compare_nu_tax` toma únicamente los meses del período de la constancia, que puede comenzar después de enero. Exige estados mensuales completos de una sola cuenta; deduplica archivos binarios y rechaza dos archivos diferentes para el mismo mes. Los meses ausentes se enumeran, sin tratar un subtotal parcial como total anual.

La comparación coteja interés nominal contra bruto mensual y retención total contra retenciones mensuales. No compara el interés real con el neto cobrado. `monthly_totals_match` significa coincidencia numérica con meses completos; no significa que la constancia carezca de diferencias internas o esté validada fiscalmente. Las incidencias se entregan por separado en `issues`.

La constancia no informa número de cuenta y un RFC genérico no identifica por sí mismo al titular. Por ello la comparación entre las fuentes entregadas es contextual y `identity_link_confirmed=False`, incluso si las sumas coinciden. No mezcla automáticamente cuentas por institución, nombre o igualdad de importes.

## Límites fiscales

El tipo de pago se registra literalmente como lo publica la institución. Retención, interés nominal, real, gravado y exento son campos distintos; ninguno se interpreta automáticamente como impuesto definitivo. La lectura no calcula declaración anual, acreditamientos, exenciones legales ni tasas históricas. Esas reglas requieren un módulo y validación propios.

La evidencia OCR de una imagen se conserva mediante `read_image`, con los mismos controles locales del catálogo. No hereda las comprobaciones estructuradas de una constancia PDF ni se transforma automáticamente en declaración o movimiento financiero.

Fuentes, cadenas, UUID, informes y discrepancias del titular permanecen privados. Las pruebas públicas utilizan exclusivamente datos ficticios.
