# Registro de avances

## 2026-11-03 — Primera base funcional

- Consolidado el alcance de inversiones, reglas de capital, reinversión, cashback, evidencia e ISR.
- Documentadas alternativas, límites y etapas; arquitectura inicial local sin dependencias de pago.
- Implementado núcleo en memoria con Decimal y movimientos inmutables.
- Incluidos 16 casos de prueba sintéticos: transferencias, contraparte faltante/incompatible, reinversión, cashback, importación repetida por ID, conflicto, retención desconocida/cero, origen desconocido, saldo inicial, unidades, fechas efectivas, precisión, validaciones y vínculo reutilizado.
- Verificación previa a publicación: 16 pruebas aprobadas mediante unittest sobre los mismos contenidos del repositorio, cargados en memoria.
- No se importaron estados ni Excel. No hay base de datos, interfaz ni motor fiscal implementados.
- Siguiente incremento: persistencia local y trazabilidad documental, antes de incorporar datos reales.

## 2026-11-03 — Persistencia y evidencia

- Implementado Store SQLite sin dependencias externas: documentos por huella SHA-256, decisiones de revisión, lotes atómicos, importes decimales exactos y múltiples evidencias.
- Correcciones explícitas con versión esperada, motivo e historia conservada; documento corregido no sustituye movimientos automáticamente.
- Implementadas copia consistente a destino vacío y recuperación de imagen SQLite.
- Añadidas pruebas de documentos solapados, conflictos, revisión, correcciones, recuperación y conexiones separadas.
- Verificación previa a publicación: 35 pruebas aprobadas y 2 omitidas por no disponer de escritura local. Las dos pruebas de archivo se ejecutarán mediante GitHub Actions.
- CI limitada a Ubuntu estándar en repositorio público, sin cachés ni artifacts; ejecución local independiente.
- No se importaron datos reales ni Excel. Siguiente módulo: vista previa del primer adaptador documental.

### Verificación completa de persistencia

- [GitHub Actions: 37 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/41577502496).
- Entorno: Ubuntu 24.04, Python 3.12.3, SQLite 3.45.1.
- Confirmados cierre/reapertura de archivos, copia a otro archivo y dos conexiones con control de versión.
- Resultado vinculado al commit 4f741507c18a5313d604d38019d863077dd6fe2a.
- Actualizada la acción checkout a v7 tras el aviso de deprecación de Node 20 observado en la primera ejecución.
- Finalizado el incremento de persistencia. Continúan pendientes los límites expresados en el manual; no se incorporaron registros reales.

## 2026-11-03 — Dos lectores y organización del panel

- Registrada la decisión del titular: categorías separadas, instituciones dentro de ellas, vistas de débito e inversiones por institución y resumen global independiente.
- Implementados dos lectores independientes de Openbank con resumen, filas, página/línea, controles contables y propuestas de transferencias.
- Contrastadas extracción por columnas y extracción lógica para conservar descripciones partidas.
- Lectura PDF local mediante pypdf 6.10.0, licencia BSD-3-Clause según metadatos del paquete; biblioteca externa solo para este extra.
- Añadidas 15 pruebas sintéticas del lector, incluida lectura de PDF generado en memoria; aprobadas localmente.
- Vista previa exclusivamente: no se aprobó ni guardó ningún movimiento financiero real.
- Pendientes interfaz, revisión de identidad y confirmación transaccional de importación.

### Verificación completa de los dos lectores

- [Suite completa: 52 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/41579036184).
- Commit probado: 42934e73c5075d5ed4bc92da5d7edbe748600717.
- Instalación del extra PDF verificada en entorno virtual; generación y lectura del PDF sintético sin archivos financieros privados.
- Cerrado el incremento de lectura y vista previa. La estructura del panel está documentada en PANEL.md; la interfaz y la confirmación de importación siguen pendientes.

## 2026-11-03 — Catálogo de todas las instituciones disponibles

- Añadido catálogo de 13 perfiles con vistas débito/inversiones: 26 entradas de lectura.
- Conservadas las dos implementaciones específicas conciliadas de Openbank.
- Los 12 perfiles adicionales extraen evidencia documental por sección; no se presentan como importadores contables terminados.
- Incluidos períodos del contenido, números Decimal, porcentajes, localizadores e IDs documentales compartidos cuando procede.
- Añadida consola local para listar lectores y consultar PDF, sin guardado ni acceso bancario.
- Diferenciada sección ausente de saldo cero/producto inexistente.
- Documentados límites, reglas particulares y mapeo económico pendiente por institución.
- Verificación local sintética: 73 pruebas aprobadas y 2 de disco omitidas en el entorno local; CI ejecutará la suite completa.
- Verificación privada adicional: lectores ejecutados sobre los formatos disponibles, sin incorporar documentos ni datos al repositorio.
- No se importó Excel ni se guardaron movimientos financieros reales.

### Verificación completa del catálogo

- [75 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/41580568736).
- Commit probado: b36a7b490c1e3e6e2bfc1143156680f66ce467ec.
- Cobertura de prueba adicional: componentes de pago/ISR en préstamos, precisión del precio de títulos y orden inverso de movimientos.
- Resultado: catálogo documental y consola operativos para las vistas registradas. Openbank conserva conciliación específica; los 12 perfiles adicionales siguen en revisión documental y no están autorizados por el software para importar.
- El avance no equivale a haber terminado los importadores económicos, lectores de constancias fiscales, cripto ni interfaz.

## 2026-11-04 — OCR y capturas de cripto

- Incorporada entrada de imagen en las 26 vistas documentales y dos lectores iniciales BingX/Pionex: catálogo de 28 entradas.
- OCR Tesseract local con Pillow, texto/coordenadas/confianza y huella original. Las imágenes no se envían a una API.
- La consola detecta PDF/imagen por contenido y permite seleccionar idioma OCR; la interfaz visual sigue pendiente.
- Candidatos cripto con unidades, precisión Decimal, ID de orden/fill, PnL por tipo, bot, funding y pendientes de zona horaria/estado.
- Comprobados importes ambiguos, campos ausentes/repetidos y propuestas de coincidencia entre fotos de una ejecución sin fusionar órdenes distintas.
- 108 pruebas locales aprobadas, sin omisiones, incluyendo OCR real sobre imágenes ficticias en cinco formatos y reapertura de archivos SQLite.
- No se validaron todavía capturas reales de las plataformas ni se importaron datos reales. Los originales permanecen fuera del repositorio.

### Verificación completa de OCR y cripto por imagen

- [GitHub Actions: 108 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/41965052220).
- Commit probado: 5cf304854318c9981b9eba0c0c0db37338c9e7ac.
- Extras Pillow 13.0.0 y pypdf 6.10.0 instalados correctamente en CI; Tesseract y modelos inglés/español disponibles.
- OCR real sobre imágenes ficticias en PNG, JPEG, WebP, TIFF y BMP; comprobados los recorridos de BingX/Pionex y detección de formato por contenido.
- Las propuestas permanecen pendientes de revisión: no se importaron movimientos ni se archivaron originales financieros reales.
- Pendientes: calibración con capturas reales, pantalla de carga/revisión y confirmación contable.

## 2026-11-04 — Conciliación de débito BanCoppel y cobertura documental

- Implementada lectura PDF detallada optativa de BanCoppel con fechas MM/DD dentro del período, orden inverso, interés bruto/neto, retención y tasa informativa.
- Contrastados importes/saldos por movimiento, depósitos, retiros, comisiones, IVA y ecuación de resumen; las discrepancias no crean ajustes.
- Añadida comprobación de documentos duplicados, huecos, solapamientos y continuidad de saldos para una misma cuenta identificada.
- La consola ofrece --reconcile en perfiles compatibles. La entrada de imagen sigue su revisión OCR, sin heredar la conciliación PDF.
- Validación adicional con documentos privados: el informe y su inventario no se publican en GitHub.
- 122 pruebas locales aprobadas, sin omisiones. Se conservan pruebas de OCR, cripto, núcleo y almacenamiento.
- No se importaron movimientos reales ni Excel. Las transferencias no se califican automáticamente como capital externo.

### Verificación completa de BanCoppel y cobertura

- [122 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/41967058012).
- Commit probado: 1558210d7da3c541ccf6e9f0076be3b569b5685d.
- Preservadas las verificaciones existentes de OCR, capturas cripto, núcleo y persistencia.
- El informe financiero del lote y sus referencias de integridad se guardaron de forma privada; no forman parte de este repositorio.
- El resultado sigue siendo revisión documental, sin importación automática ni ajustes ficticios.

## 2026-11-04 — CETESdirecto: efectivo y posiciones

- Implementado lector PDF de conciliación optativa para CETESdirecto, manteniendo el lector documental y OCR existentes.
- Separados efectivo, títulos, valuación, entradas/salidas, compras/ventas, amortización e ISR.
- Preservadas fechas de registro y liquidación, incluida operación registrada fuera del mes pero liquidada dentro del período documental.
- Conservadas etiquetas de resultados BONDDIA/GUBER/ENERFIN sin convertir valoración en cobro ni duplicar ISR acumulado.
- Añadida huella de texto normalizado, distinta de la huella binaria, para comparar evidencia equivalente sin fusionar movimientos.
- Validación con documentos privados e informe de cobertura privado; no se publican nombres particulares de archivos, fechas del inventario ni importes del titular.
- Añadidas pruebas sintéticas de formatos antiguos/nuevos, efectivo temporal negativo, diferencias de resumen, acumulados, posiciones vacías, PDF y consola.
- No se importaron movimientos reales ni Excel.

### Verificación completa de CETESdirecto

- [133 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/41969285172).
- Commit probado: bf75c51bc304e0712a089cc7af6b249938dc67a5.
- Conservadas las verificaciones de OCR, capturas cripto, BanCoppel, núcleo y persistencia.
- El informe del lote, sus faltantes y las referencias documentales se guardaron de forma privada, fuera del repositorio.
- No se importaron operaciones reales ni se resolvieron discrepancias mediante ajustes ficticios.

## 2026-11-05 — DiDi Cuenta: formatos de resumen y cuenta compartida

- Añadido lector optativo de conciliación para ambos formatos reconocidos, con disposición visual del resumen y detalle de movimientos.
- Conservados rendimientos, retención, transferencias pendientes, referencias partidas entre páginas y condiciones históricas publicadas.
- Las vistas de débito e inversión comparten identidad/evidencia; no representan saldos adicionales.
- Pruebas sintéticas de diferencias de resumen/saldos, referencias ausentes/duplicadas, tipos y moneda desconocidos, fechas, retención, PDF y consola.
- Revisión de documentos reales e informe de cobertura privados, sin publicar importes, identificadores ni inventario del titular.
- No se importaron movimientos reales ni datos de Excel. Sin nuevas APIs ni servicios externos.

### Verificación completa de DiDi Cuenta

- [145 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42030988263).
- Commit probado: 7eb9228ebf4a313a029a67ca5192a446f13905a1.
- Conservadas las verificaciones de OCR, cripto, Openbank, BanCoppel, CETESdirecto, núcleo y persistencia.
- El informe financiero y la cobertura documental se guardaron de forma privada.
- No se importaron movimientos reales ni se aplicaron ajustes para forzar la conciliación.

## 2026-11-05 — Doopla: efectivo y cartera por separado

- Añadido lector PDF optativo para ambas perspectivas de la cuenta de plataforma.
- Separados principal, interés, IVA ordinario/moratorio, ISR, comisión, depósitos/retiros e inversión/cancelación.
- Conservados signos del IVA del resumen, retención no informada frente a cero y cifras acumuladas del anexo.
- Añadidos estados independientes de conciliación del efectivo, componentes y documento completo; diferencias exactas con página/línea, sin ajustes ficticios.
- Revisión entre documentos de continuidad y anexos económicos repetidos pese a actividad de capital.
- Pruebas sintéticas y revisión de fuentes privadas; sin datos personales ni inventario financiero en el repositorio.
- No se importaron movimientos reales ni Excel. Identidad económica y flujo visual siguen pendientes.

### Verificación completa de Doopla

- [160 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42033120060).
- Commit probado: ae1415a164edfb7f66ec58348dc2465b2467fbad.
- Conservadas las verificaciones de OCR, cripto, Openbank, BanCoppel, CETESdirecto, DiDi, núcleo y persistencia.
- Informe financiero, cobertura y diferencias documentales guardados de forma privada.
- Efectivo conciliado y conciliación completa son estados distintos; no se importaron datos reales ni se ocultaron diferencias mediante ajustes.

## 2026-11-05 — Fondos Fintual y acciones/ETF Alpaca

- Añadido lector optativo de fondos MXN: posiciones anterior/actual, efectivo, operaciones, resumen y retención informativa separados.
- Añadido perfil Alpaca USD, dos perspectivas de una misma cuenta, PDF/imagen y revisión optativa de acciones, ingresos, retención extranjera y Memopost.
- Catálogo actualizado a 14 perfiles institucionales con dos vistas (28 entradas), más BingX/Pionex (30 entradas totales).
- Preservados guiones como no informados, importes mensuales frente a acumulados y diferencias exactas sin ajustes ficticios.
- Pruebas sintéticas de separación de capital/rendimiento, monedas, dividendos/retención, fechas, fuentes vacías, PDF y catálogo ampliado.
- Informes financieros y cobertura de documentos reales guardados de forma privada, sin publicar datos ni inventario del titular.
- No se importaron datos reales ni Excel; lotes, conversión fiscal a MXN e interfaz siguen pendientes.
