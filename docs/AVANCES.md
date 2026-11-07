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

### Verificación completa de Fintual y Alpaca

- [176 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42035477324).
- Commit probado: 982b4eb0a6f4faf1179b06b7e1e795a81ede6caf.
- Conservadas las pruebas de OCR, capturas cripto, catálogo ampliado, lectores previos, núcleo y persistencia.
- Informes de ambos productos guardados de forma privada, con faltantes y diferencias documentales.
- MXN/USD, valuación/cobro, principal/rendimiento y período/acumulado permanecen separados; sin importación real ni ajustes ficticios.

## 2026-11-05 — Fondeadora: formatos operativos y traspasos de inversión

- Añadido lector optativo para estados operativos y reportes de movimientos, manteniendo el emisor impreso y los campos no informados.
- Vista inversiones limitada explícitamente a evidencia de traspasos/Apartados; no se usa saldo operativo como saldo invertido.
- Normalización localizada de espacios de fuente en campos, contraste de fechas y conservación de página/línea.
- Distinción entre tabla vacía y detalle no incluido; diferencias entre resumen y detalle preservadas sin ajustes.
- Corregida la cobertura común para no contar dos saldos desconocidos como continuidad verificada.
- Pruebas sintéticas de formatos, desconocido/cero, tasa vacía, traspasos, diferencias, fechas, cobertura, PDF y consola.
- Informe de los documentos reales guardado de forma privada. No se importaron movimientos reales ni Excel.

### Verificación completa de Fondeadora

- [189 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42039373304).
- Commit probado: ac281d0a953750003cf3e74c06dcadc9702aa48f.
- Conservadas las verificaciones de los lectores previos, OCR, cripto, monedas, núcleo y persistencia.
- Cobertura común verificada con saldos ausentes: no se cuentan como coincidencias de cero.
- Informe financiero y evidencia de Apartados guardados de forma privada; saldo de inversión pendiente, sin importación de datos reales.

## 2026-11-05 — Hey: pagarés y propuestas de reinversión

- Añadido lector optativo para ambas vistas del formato mensual reconocido, con cuenta operativa, resumen de pagarés y condiciones por contrato.
- Separados capital retornado, interés pagado, retención, devengado incluido en saldo y proyección al vencimiento.
- Añadidas propuestas de reinversión con referencias y cuatro filas fuente; sin confirmación ni importación automática.
- Comprobados saldos, resumen, tasas/plazos, pagos frente a contratos y total de portafolio; diferencias de totales futuros preservadas.
- Pruebas sintéticas de neto/bruto, devengo, contratos, referencias reutilizadas/duplicadas, PDF, consola y separación de vistas.
- Revisión con fuente real e informe privado. Sin publicación de datos del titular ni cambios de reglas fiscales; no se importaron datos reales o Excel.

### Verificación completa de Hey

- [203 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42043748201).
- Commit probado: 1a3dde032d1ddab5e2af98e500f9643b7c6f0867.
- Conservadas las pruebas de los lectores anteriores, OCR, cripto, núcleo, persistencia y cobertura de saldos desconocidos.
- Informe financiero privado con contratos y propuestas de reinversión; diferencias abiertas sin ajustes ficticios.
- No se importaron movimientos reales ni Excel, ni se confirmó automáticamente una renovación.

## 2026-11-05 — Kapital: formatos y vencimientos

- Añadido lector optativo en ambas vistas para el formato anterior y el nuevo, con efectivo y capital invertido separados.
- Preservados los movimientos de inversión fuera del resumen operativo anterior y los componentes ya incluidos en depósitos/retiros nuevos.
- Conservados timbrado/descuento, folios compartidos y saldos con signo final, sin compensar ni borrar evidencia.
- Contratos con condiciones históricas; campos de proyección no informados permanecen desconocidos.
- Añadida revisión entre documentos con propuestas de equivalencia de identificadores y cotejo de vencimientos, sin confirmación ni fusión automática.
- Pruebas sintéticas y revisión con documentos privados; informe de cobertura y contratos guardado de forma privada.
- No se importaron movimientos reales ni Excel ni se asumieron reglas fiscales anuales.

### Verificación completa de Kapital

- [219 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42047255047).
- Commit probado: 8a36989c68cc96767dbe30a2bee3cf830bd0f641.
- Conservadas las pruebas de lectores anteriores, OCR, cripto, núcleo, persistencia y cobertura.
- Cotejos entre formatos, timbrado compensado, saldos con signo final y vencimientos verificados con fuentes sintéticas.
- Informe financiero privado; sin importación real, fusión de contratos ni confirmación automática de vínculos.

## 2026-11-05 — Mifel: cobros y rangos remunerados

- Añadido lector optativo de cuenta a la vista remunerada para ambas vistas, sin duplicar saldo.
- Separadas fecha de cobro y fechas remuneradas, incluidos rangos que cruzan fin de mes.
- Cotejados saldos, depósitos/retiros, interés bruto, retención, posición y rangos; se preservan gráficos redondeados como ajenos al cálculo exacto.
- Agrupación documental de interés/retención por fecha y raíz de referencia, sin calcular impuestos anuales.
- Pruebas sintéticas de rangos, meses, duplicados, conceptos desconocidos, productos adicionales, PDF y consola.
- Fuente real e informe financiero privados; no se importaron movimientos ni datos de Excel.

### Verificación completa de Mifel

- [233 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42051723372).
- Commit probado: 5c3d270919a951a6d6e677a9f10dee82ac1f86ef.
- Se conservan las verificaciones de lectores previos, OCR, cripto, núcleo y persistencia.
- Informe y cobertura privados; sin importación real ni doble cómputo de rangos entre meses.

## 2026-11-05 — Nu: resumen y evidencia por secciones

- Añadido lector optativo de resumen consolidado, rendimiento bruto/neto y retención publicada.
- Separadas las evidencias de cuenta, Cajitas y garantía; congelamientos y fechas futuras no se convierten en ganancias.
- Conservadas distribución publicada, disponible/congelado y diferencias exactas sin ajustes.
- Estados explícitos de resumen/composición frente a detalle económico aún pendiente; no se marca listo para importar.
- Pruebas sintéticas de traspasos reflejados en dos secciones, garantías ausentes/cero, tasas publicadas, importes ambiguos, PDF y catálogo.
- Informe e inventario de fuentes reales privados. Sin importación real, Excel ni cálculo fiscal anual.

### Verificación de Nu y suite completa

- [245 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42054094723).
- Commit probado: d9c7a1b8753bb299859fdf9c755e99e64aefe42b.
- Se preservan lectores anteriores, OCR, cripto, núcleo, persistencia y revisión de cobertura.
- Nu mantiene detalle económico pendiente aunque concilie el resumen; no se fuerza cierre de diferencias de distribución.
- Informe financiero privado; sin importación de datos reales o Excel.

## 2026-11-05 — Nu: detalle y traspasos

- Corregidas fechas con año en otra línea o contextual y descripciones que continúan entre páginas.
- Añadidas claves SPEI, nombres explícitos de Cajita y conservación de devoluciones con la misma clave.
- Añadidos asientos de cambio para cuenta, disponible, congelado y garantía; los congelamientos son movimientos internos neutrales.
- Pareo documental único de depósitos/retiros entre secciones, con ambigüedades sin confirmar.
- Revisión histórica con duplicados, cuenta única, rechazo de solapamientos y candidatos de vencimiento por nombre/fecha explícitos.
- Detalle accesible desde API y consola; salida normal sin cantidades ni identificadores privados.
- Rendimiento global sin reparto publicado permanece sin asignar; saldos individuales no informados no se inventan. Las diferencias reales siguen bloqueando cierre.
- Pruebas sintéticas y revisión privada de fuentes; no se importaron datos reales ni Excel.

### Verificación del detalle de Nu

- [259 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42055981359).
- Commit probado: 0849887ff491bce63358e7302ea2d195624597fb.
- Incluye fechas antiguas, continuaciones entre páginas, traspasos ambiguos, neutralidad de congelamientos, devoluciones SPEI y candidatos de vencimiento sin calcular rendimientos implícitos.
- Revisión documental completada al alcance de las fuentes; el cierre individual sin desglose publicado y las diferencias de composición siguen bloqueados por evidencia. No se atribuye conciliación completa a un documento incompleto.
- Informe privado actualizado y sin importación financiera real.

## 2026-11-05 — Nu: variante documental del emisor

- Añadida variante de emisor bancario con conservación de la etiqueta por documento y reconocimiento de sus pies de página.
- La continuidad sigue la cuenta explícita sin duplicarla por un cambio del nombre del emisor.
- Se rechazan emisores desconocidos o contradictorios; no se infieren fechas regulatorias ni tratamiento fiscal.
- Ampliada la revisión de fuentes privadas y cobertura, sin publicar inventarios, saldos o archivos personales.
- Pruebas de variantes, ambigüedad, pie de página, catálogo PDF y duplicados.

### Verificación de la variante Nu

- [263 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42091872791).
- Commit probado: c4c12d0ca5b237c69bb914120a283c4e6b2c224b.
- Suite completa de lectores, OCR, cripto, núcleo, persistencia y cobertura conservada.
- Informe privado actualizado. Sin importación financiera, ajuste de diferencias ni reclasificación fiscal automática.

## 2026-11-05 — Nu: constancias fiscales documentales

- Añadido lector local separado de constancias, sin generar movimientos ni duplicar el rendimiento o las retenciones de los estados mensuales.
- Portada y cadena se conservan por separado, con diferencias explícitas de campos y aritmética, sin aplicar correcciones.
- Cotejo contextual con meses completos del período publicado, duplicados binarios, cuenta única y detección de períodos ausentes.
- Indicadores, tipo/códigos de pago, UUID y procedencia preservados; sin validación de firma/SAT ni cálculo de declaración anual.
- Un RFC genérico y la ausencia de número de cuenta impiden confirmar automáticamente el vínculo personal.
- Fuentes e informe privados; pruebas públicas ficticias y manual del lector.

### Verificación de constancias Nu

- [279 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42092938543).
- Commit probado: d11243e57fadc638ffe9a81397a3149b0287feb5.
- Incluye diferencias portada/cadena, períodos parciales del año, meses ausentes, duplicados, identidad fiscal, comparación contextual y salida de consola sin cantidades privadas.
- Se conserva la suite completa previa. No se generan movimientos desde constancias, correcciones monetarias ni cálculos del impuesto anual.

## 2026-11-05 — Openbank: cobertura y constancias PDF/XML

- Incorporada identidad documental por vista, con RFC en columnas y referencia de cuenta padre para Apartado, sin equipararla al folio fiscal.
- Admitido resumen completo explícito en cero sin tabla; ausencia de sección y tabla malformada siguen siendo casos distintos.
- Añadido lector de constancias por producto y XML directo/multipart con huella original e IDs exactos de addenda.
- Cotejo PDF/XML por UUID, producto, receptor, emisor y período, separado de igualdad de importes.
- Cotejo de totales mensuales observados y addenda, sin acreditar cobertura anual cuando faltan meses.
- Sin duplicar rendimientos, retenciones o documentos, sin escribir datos reales ni verificar firmas o consultar SAT.
- Fuentes, inventario e informe financiero privados; manuales y pruebas ficticias públicos.

### Verificación de Openbank y constancias XML

- [301 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42095107298).
- Commit probado: f3faa3a1b0a53be59adbec1ddc198f33fdd55040.
- Verificados PDF, XML directo/multipart, IDs exactos, identidad, discrepancias, doble representación fiscal, cobertura incompleta y resumen vacío sin tabla.
- Suite previa conservada. Informe y fuentes privados; ninguna importación financiera, validación criptográfica o consulta a SAT.

## 2026-11-05 — SuperTasas: efectivo y plazos

- Añadido lector específico para ambas vistas, con cuenta compartida, capital devuelto, interés pagado y proyecciones diferenciados.
- Preservados saldos iniciales no publicados, negativos entre paréntesis, importes con decimales variables y saldos inconsistentes sin ajustes.
- Posiciones mensuales con condiciones históricas; capital al vencimiento en sus formas publicadas y alerta por posición vencida aún listada como vigente.
- Cobertura, duplicados binarios y candidatos de apertura/devolución, sin fusionar contratos ni suponer reinversión.
- PDF protegido mediante contraseña explícita en memoria; sin incorporar credenciales a código, argumentos o vistas previas.
- Documentación y pruebas ficticias; fuentes e informe privados, sin importación real ni Excel.

### Verificación de SuperTasas

- [317 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42117349623).
- Commit probado: ea16c6832307174154a543520bff012480e48fc3.
- Cubiertos PDF protegido con contraseña ficticia, campos ausentes, signos negativos, proyecciones, vencimientos, cuenta compartida y candidatos ambiguos.
- Suite anterior conservada; informe financiero privado. Sin contraseñas reales en el repositorio, ajustes de saldos, importaciones ni cálculo fiscal anual.

## 2026-11-05 — YoTePresto: plataforma operativa y préstamos

- Añadido perfil institucional con dos vistas PDF/imagen: el catálogo suma 15 instituciones y 32 entradas, incluidas capturas cripto.
- Lectura específica de resumen global, efectivo, interés/IVA, comisiones y retenciones IVA/ISR, sin mezclar pagos compuestos con ganancias.
- «Ganaste» conserva su base observada por documento; retenciones ausentes quedan desconocidas, distintas de cero.
- Cartera admite formato con/sin usuario, tasas históricas y acumulados; atrasos se conservan aparte.
- Controles separados de resumen, saldos operativos y cartera, sin ordenar filas por saldo ni introducir ajustes.
- Historia con duplicados, continuidad de efectivo entre meses y controles de acumulados, sin reinversión automática o importación real.
- Documentos e informe privados; manuales y pruebas públicas ficticias.

### Verificación de YoTePresto y catálogo ampliado

- [334 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42124832410).
- Commit probado: 84817c729a1c1104d5aa5a65530f4c58a632515a.
- Cubiertos formatos con/sin usuario, acumulados, retenciones ausentes, IVA/ISR separados, bases de ganancia, continuaciones, diario, cartera, atrasos e identidad compartida.
- Catálogo y OCR verificados para 15 instituciones y 32 entradas. Suite previa conservada.
- Informe y fuentes reales privados; discrepancias preservadas sin ajustes, importación o cálculo fiscal anual.

## 2026-11-05 — Plata: cuenta y ahorro flexible

- Dos productos separados con relación compartida; saldo agregado cotejado sin descontar ISR dos veces.
- Conservados depósitos/rendimientos combinados, signos en continuaciones, referencias desconocidas y operaciones iguales legítimas.
- Cashback como aportación identificada y pares internos candidatos, sin duplicar capital externo.
- Fechas de operación/cargo y período separados; cargos posteriores al corte conservan alerta aunque cuadre el resumen.
- Tasas, promedio y GAT publicados; anexo CFDI excluido de movimientos.
- 348 pruebas locales aprobadas, incluidas 14 específicas; verificación remota aprobada.
- Documentación y datos sintéticos públicos; fuentes e informe privados. Sin importación real o cálculo fiscal anual.

### Verificación de Plata

- [348 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42126737348).
- Commit probado: 03b11fca8d48bb30eff917b51a32d742d25beb7c.
- Verificados ambos productos, cashback y vínculos candidatos, doble conteo ISR, continuaciones/encabezados, fechas fuera de corte, referencias desconocidas y exclusión de anexo fiscal.
- Suite anterior conservada; informe y fuentes privados. El siguiente trabajo del orden aprobado es conciliación/cobertura por institución.

## 2026-11-05 — Aplicación local y prioridad corregida

- Registrada la aclaración: los PDF son muestras para desarrollar lectores; los estados faltantes no bloquean la aplicación.
- Interfaz GitHub oscura con categorías, instituciones y pestañas de cuenta/inversiones; búsqueda y tablas paginadas.
- Carga individual, detección por contenido, prioridad al emisor frente a contrapartes, extracción de ambas vistas y fallback documental explícito.
- Original y resultado atómicos en SQLite, deduplicación binaria, descarga exacta, reapertura y revisión con control de versión; contraseñas solo en memoria.
- Sin APIs nuevas, CDN o servicios externos; localhost con verificación de Host/Origin y token para cambios.
- Inspección visual con documentos ficticios y pruebas HTTP del servidor real. PDF reales usados solo para probar formatos; sin informes personales nuevos ni importación al ledger.
- Importación financiera normalizada y resumen patrimonial siguen pendientes. Manual de aplicación y plan actualizados.

### Verificación de aplicación local

- [360 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42132916426).
- Commit probado: e190c356571816aff4bcc0b93cbdde7509dca650.
- Cubiertos HTTP real, carga y descarga exacta, duplicados, reapertura, dos vistas, retención de alertas, versiones de revisión, contraseña no persistida, identidad del emisor, OCR y precisión decimal.
- JavaScript validado con `node --check`; inspección visual de bandeja y ambas pestañas en navegador con ejemplo ficticio.
- La bandeja persistente está implementada. Próximo objetivo: normalización e importación financiera al ledger, sin depender de documentos faltantes.

## 2026-11-05 — Openbank: del documento al libro financiero

- Implementados plan automático, revisión visible y confirmación financiera desde la aplicación; extracción documental y aprobación financiera siguen separadas.
- Normalización de aportaciones/retiros, interés y retención explícita cero; orígenes no acreditados permanecen pendientes.
- Reducción/aportación de traspasos internos con pareja única, sin inflar capital externo; pares ambiguos bloqueados.
- Anclas de apertura/cierre por período, meses fuera de orden, solapamientos bloqueados y huecos de cobertura visibles.
- Guardado atómico de documento, aprobación, movimientos, evidencias, cobertura y plan; savepoints para transacciones anidadas.
- Control de versión y huella del plan/libro; reintentos idempotentes, sin cambios silenciosos en importaciones existentes.
- Primera consulta del libro con cierres por producto/fecha e intereses/retenciones de períodos importados.
- Pruebas y vista visual con documentos ficticios; ninguna contabilidad real confirmada. Otras instituciones, correcciones y resumen patrimonial completo siguen pendientes.

### Verificación de importación financiera Openbank

- [373 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42134255465).
- Commit probado: ba69f6b09666b2598cc7e3869e703ff7a40b373f.
- Trece pruebas nuevas verifican conversión, pares internos, ambigüedad, origen pendiente, precisión, idempotencia, reapertura, continuidad, meses fuera de orden, huecos, versiones/planes obsoletos, rollback completo y confirmación HTTP.
- Suite previa conservada; JavaScript validado. Inspección visual del plan y del libro con datos ficticios; prueba de generación de plan sobre formato real sin confirmar movimientos.
- Próxima integración: extender la capa financiera a otra institución, manteniendo los lectores y reglas particulares.

## 2026-11-05 — Mifel: confirmación financiera de cuenta remunerada

- Plan automático y confirmación en la aplicación, con un solo período/cuenta compartida entre ambas vistas.
- Normalizados interés bruto, retención ISR no nula o cero explícito y aportaciones/reducciones SPEI con origen pendiente.
- Conservados fecha de cobro, rango remunerado, referencias de los pares y condiciones históricas en el plan, sin duplicar por resumen/grupo.
- Nuevos controles de cierre/interés/ISR, continuidad y solapamientos; transacción, idempotencia y planes obsoletos reutilizados.
- Libro multiinstitución: Openbank y Mifel conviven sin colisiones, con cierres por fecha e interés menos ISR de períodos confirmados.
- Pruebas ficticias y generación de plan sobre el formato real, sin confirmar movimientos personales. Sin dependencias o servicios externos nuevos.
- Manual Mifel y documentación general actualizados; otras instituciones siguen pendientes de confirmación financiera.

### Verificación de importación financiera Mifel

- [387 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42135626963).
- Commit probado: 98585b689ba2f96c6c956ad649a3995952cea2a2.
- Catorce pruebas nuevas cubren cuenta compartida, ISR no nulo/cero, observación de interés cero, rangos remunerados, aportaciones/reducciones pendientes, duplicados, continuidad, orden de meses, bloqueo de discrepancias, rollback, coexistencia con Openbank y confirmación HTTP.
- Suite previa conservada; JavaScript validado. Plan automático y cuenta única con interés/ISR/neto comprobados en navegador con datos ficticios.
- Prueba de generación de plan con formato real sin confirmar movimientos personales. Manual y código públicos; datos financieros privados fuera del repositorio.

## 2026-11-05 — BanCoppel: confirmación financiera de cuenta de paso

- Conectado débito PDF al plan automático y confirmación del libro, sin crear producto de inversión ni segunda cuenta.
- Efectivo/SPEI/devoluciones como aportaciones/reducciones pendientes de origen y contrapartida, sin capital externo acreditado por suposición.
- Comisiones e IVA separados en filas de cargos operativos; ISR cero documentado e interés solo si está publicado.
- Identidad contradictoria rechazada y moneda nacional explícita requerida, sin inferir MXN por símbolo dólar.
- Reconciliación adicional de importes normalizados, fechas de cambio de año, duplicados binarios, solapamientos, continuidad y atomicidad.
- Libro con tres instituciones distintas, identificación de cuenta de paso y consulta separada de cargos e interés menos ISR.
- Manual y pruebas ficticias; muestra real usada para validar plan sin confirmar movimientos personales. Sin dependencias ni pagos nuevos.

### Verificación de importación financiera BanCoppel

- [400 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42136586720).
- Commit probado: 445543852e83afc35e68c82edcafea879df44d42.
- Trece pruebas nuevas cubren cuenta de paso, efectivo/SPEI/devoluciones con origen pendiente, comisiones/IVA/ISR separados, ausencia de interés, cambio de año, operaciones iguales legítimas, identidad y moneda, solapamientos, continuidad, reintentos/reapertura, rollback, tres instituciones y confirmación HTTP.
- Suite previa conservada y JavaScript validado; muestra real usada para generar plan sin confirmar movimientos personales.
- Código, manual y decisiones guardados; otras instituciones y conciliación entre cuentas permanecen pendientes.

## 2026-11-05 — DiDi: confirmación financiera de ambos formatos

- Plan automático y confirmación desde la aplicación para ambos formatos textuales de resumen.
- Cuenta y período únicos compartidos entre pestañas; aportaciones y rendimientos separados sin duplicar el interés incluido en depósitos.
- Retención cero explícita, referencias continuadas, fechas de cobro y condiciones históricas preservadas; transferencias con origen pendiente.
- Normalización vuelve a comprobar cierre, depósitos, retiros, interés e ISR; referencias ausentes/repetidas, diferencias o moneda no reconocida bloquean.
- Solapamientos, continuidad, meses fuera de orden y folios acotados por período; transacción e idempotencia reutilizadas.
- Cuatro instituciones coexisten en el libro sin fusionar cuentas ni duplicar las compartidas.
- Manual actualizado, pruebas ficticias y generación de plan con muestra real sin confirmar movimientos personales; sin dependencias o servicios nuevos.

### Verificación de importación financiera DiDi

- [413 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42138993692).
- Commit probado: d4d46872f0b8d302865f61c9fda666b0b6c70121.
- Trece pruebas nuevas cubren ambos resúmenes, cuenta compartida, interés incluido en depósitos, folios continuados y escalones preservados, cero/sin interés, orígenes pendientes, duplicados, meses fuera de orden, referencias/moneda/diferencias, rollback, cuatro instituciones y confirmación HTTP.
- Suite previa conservada y JavaScript validado; muestra real utilizada para generar plan sin confirmar movimientos personales.
- Código, manual, límites y decisiones guardados. Confirmación financiera de otras instituciones y conciliación entre cuentas siguen pendientes.

## 2026-11-06 — Fondeadora: cuenta operativa y revisión explícita de moneda

- Confirmación de estados operativos completos y conciliados; reportes sin apertura/cierre conservados como evidencia, sin saldos o impuestos inventados.
- Entradas/salidas, traspasos y Apartados con origen/destino pendientes; ninguna Bóveda, reinversión o segundo saldo creado desde las pestañas.
- Moneda desconocida conservada en extracción. Selección MXN revisada desde la app, vinculada al plan y confirmación; no sobrescribe moneda publicada contradictoria ni se aplica a otros documentos.
- Control adicional de fechas, cargos/abonos y totales; conceptos de compra/comisión/interés/ISR no nulos requieren adaptación antes de confirmar.
- Interfaz de moneda inspeccionada con datos ficticios; envío/revisión/confirmación probados por HTTP real, con rollback, versiones, reintentos y cinco instituciones.
- El reporte real permanece bloqueado por no publicar saldos, sin confirmar movimientos personales. Código y manual sin nuevas dependencias o servicios obligatorios.

### Verificación de importación operativa Fondeadora

- [429 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42236172498).
- Commit probado: 4c8e752dad3887aa0affd7272331a3eabf139750.
- Dieciséis pruebas nuevas cubren estados completos/vacíos, reportes sin saldo, destino desconocido, moneda publicada/revisada, restricciones y versiones HTTP, fechas, conceptos no mapeados, duplicados, continuidad, tasas desconocidas/cero, rollback y coexistencia de cinco instituciones.
- Suite previa conservada y JavaScript validado. Control de selección de moneda comprobado en navegador con una muestra ficticia; envío y confirmación comprobados por HTTP real.
- Reporte real correctamente bloqueado por ausencia de saldos de apertura/cierre; sin confirmar movimientos personales. Bóvedas, productos adicionales y reportes parciales permanecen fuera de la confirmación financiera.


## 2026-11-06 — Plata: confirmación financiera de débito y ahorro

- Plan automático y confirmación indivisible de dos productos, sin tercera cuenta por el agregado.
- Cashback como aportación, traspaso propio único enlazado, SPEI con origen pendiente y sin reinversión inferida.
- Interés/retención de filas sin duplicar el resumen combinado, ISR global o anexo fiscal; cero publicado por producto preservado.
- Fechas de operación/cargo conservadas; cargos fuera de corte bloquean ambos productos sin cambiar fechas.
- Controles de normalización, continuidad, solapamiento, versiones, transacción y reintentos; seis instituciones coexisten sin colisiones.
- Catorce pruebas nuevas; suite local de 443 pruebas aprobada y JavaScript validado. Muestra real comprobada solo mediante vista previa: bloqueo temporal correcto y cero movimientos confirmados.
- Manual y decisiones actualizados, sin nuevas dependencias o pagos obligatorios. Otros productos, imágenes y enlaces entre instituciones pendientes de confirmación financiera.

### Verificación de importación financiera Plata

- [443 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42287677713).
- Commit probado: 06fa7f42d96e4a29591b968d65d8edcf0a6c6f0c.
- Catorce pruebas nuevas cubren dos productos, cashback único, traspaso neutral, origen SPEI pendiente, ISR no nulo/cero, anexo excluido, corte temporal, operación/cargo separados, operaciones iguales legítimas, pares ambiguos, conceptos/moneda, continuidad, meses fuera de orden, duplicados, versiones, rollback, seis instituciones y confirmación HTTP.
- Suite previa conservada; JavaScript validado. Muestra real utilizada solo para vista previa: bloqueo por fechas fuera del período y ningún movimiento financiero confirmado.
- Código y manual publicados; confirmación desde imágenes, otros productos y conciliación entre instituciones siguen pendientes.


## 2026-11-06 — SuperTasas: efectivo y observaciones a plazo

- Plan y confirmación para efectivo conciliado, con posiciones a plazo fechadas en el plan y visibles por separado; ninguna cuenta o ganancia adicional por proyecciones.
- Apertura como reducción y devolución de principal como aportación, con origen pendiente; interés a la vista registrado una vez y cero ISR acotado al producto publicado.
- Moneda explícita o revisada por documento. PDF protegido releído con contraseña transitoria, sin guardarla en plan/base ni alterar originales.
- Bloqueo de pagos a plazo sin desglose acreditado de bruto/retención y de retenciones/comisiones no nulas, formatos incompletos o posiciones inconsistentes.
- Diecinueve pruebas nuevas: transacción, versiones, continuidad, meses fuera de orden, siete instituciones, moneda y contraseñas también por HTTP. JavaScript validado y muestra real probada solo mediante plan bloqueado, sin movimientos confirmados.
- Manual, decisiones y límites actualizados. Sin nuevas dependencias, servicios ni pagos obligatorios.

### Verificación de importación de efectivo SuperTasas

- [462 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42299302319).
- Commit probado: a84406f1f824bf6fd9830d8278f144c3f2a0d5ba.
- Diecinueve pruebas nuevas cubren efectivo único, observaciones a plazo sin duplicación, principal devuelto/apertura, interés e ISR cero acotados, cobros no soportados, moneda publicada/revisada/contradictoria, PDF protegido sin guardar contraseñas, versiones, rollback, continuidad, meses fuera de orden, siete instituciones y confirmación HTTP.
- Suite previa conservada y JavaScript validado. La muestra real se utilizó solo para comprobar el bloqueo de cobros a plazo sin desglose acreditado, con cero movimientos financieros confirmados.
- Manual y límites publicados. Cartera contable de contratos, cobros a plazo con detalle fiscal, comisiones/retenciones no nulas, reinversiones y confirmación desde imágenes permanecen pendientes.


## 2026-11-06 — Hey: pagos efectivos, pagarés y renovación pendiente

- Plan automático y confirmación atómica de efectivo con principal, interés bruto e ISR separados; neto, devengo y proyecciones sin nuevos cobros.
- Pagarés/resumen de inversiones observados por fecha y propuestas de renovación con sus cuatro evidencias pendientes; sin segunda cuenta, reinversión o capital externo inventados.
- Moneda explícita o revisada por documento y lectura de PDF protegido con contraseña transitoria, sin guardarla.
- Se exige conciliación de ambas vistas: discrepancias de proyección bloquean el lote completo sin importar solo efectivo.
- Dieciocho pruebas nuevas: retención real/cero, capital, proyecciones, folios por categoría, moneda, contraseñas, continuidad, transacción, reintentos, ocho instituciones y confirmación HTTP.
- Muestra real usada únicamente para plan: diferencia de Total Vigentes correctamente bloqueada y ningún movimiento personal confirmado. Manual, límites y decisiones actualizados; sin nuevas dependencias o pagos.

### Verificación de importación de pagos Hey

- [480 pruebas aprobadas, sin omisiones, intento 2](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42300205474/attempts/2).
- Commit probado: 5779daa7e4aacd8bb256c973af45ebeaf4e14a7b.
- Dieciocho pruebas nuevas cubren efectivo único, principal y apertura, bruto/neto/ISR real y cero, proyecciones y devengo, renovación pendiente con cuatro evidencias, categorías por referencia, moneda revisada, PDF protegido sin guardar contraseña, discrepancias, continuidad, meses fuera de orden, versiones, rollback, ocho instituciones y confirmación HTTP.
- Suite local y JavaScript aprobados. El primer intento remoto agotó el tiempo descargando paquetes OCR, antes de ejecutar pruebas; el reintento del mismo commit pasó completo sin cambios de código.
- Muestra real utilizada solo para verificar el bloqueo por diferencia de Total Vigentes; ningún movimiento personal confirmado. Manual y límites publicados; cartera contractual y reinversión confirmada permanecen pendientes.


## 2026-11-06 — Kapital: pagos en ambos formatos y timbrado compensado

- Plan automático y confirmación de pagos operativos, con pagarés/saldos de inversión observados por fecha; sin duplicar capital o proyecciones.
- Principal, interés e ISR pagados separados; apertura anterior conserva signo impreso y reduce efectivo, con origen pendiente.
- Tipo de devolución de comisión en el núcleo: descuento y cargo de timbrado preservados, sin aportación/ganancia artificial y con cargos netos en el libro.
- Moneda publicada/revisada y PDF protegido con contraseña transitoria; equivalencias entre contratos no fusionadas automáticamente.
- Dieciocho pruebas de integración y dos del núcleo: ambos formatos, pagos, timbrado compensado/no compensado, proyecciones, moneda, contraseñas, reintentos, versiones, rollback, nueve instituciones y confirmación HTTP.
- Muestra real genera plan listo dentro del alcance, sin confirmar movimientos personales. Manual, límites y decisiones guardados; sin nuevas dependencias o pagos.

### Verificación de importación de pagos Kapital

- [500 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42303313799).
- Commit probado: aaf0dac2a03688857030ba23738b281b3ded1484.
- Dieciocho pruebas de integración y dos del núcleo cubren ambos formatos, principal/interés/ISR, timbrado compensado/no compensado, devolución sin capital o interés, proyecciones desconocidas, referencias por categoría, moneda, PDF protegido, versiones, rollback, meses fuera de orden, huecos, nueve instituciones y confirmación HTTP.
- Suite local y JavaScript aprobados; ejecución remota completa sin omisiones. Muestra real utilizada solo para generar un plan listo, con cero movimientos personales confirmados.
- Código, manual y límites publicados; cartera contractual, equivalencias entre identificadores y reinversión confirmada pendientes.


## 2026-11-06 — Doopla: efectivo por componentes y cobertura de retención

- Plan automático y confirmación de pagos separados en principal/interés/IVA; inversión/cancelación y depósitos/retiros con origen pendiente.
- IVA recibido/pagado y recompensa como tipos específicos, sin capital/interés/ISR artificiales; comisión con IVA agrupada registrada una sola vez.
- ISR ausente queda desconocido; total y neto también si hay meses con cobertura incompleta. Retención documentada parcial y cero explícito diferenciados.
- Cartera y cobranza observadas sin cobros acumulados o pérdidas automáticas; continuidad de efectivo/plataforma y anexo repetido con actividad de capital bloqueado, en ambos órdenes de importación.
- Moneda explícita/revisada y PDF protegido con contraseña transitoria; transacción, reintentos y evidencia por fila/componente reutilizados.
- Veinte pruebas de integración y una del núcleo con datos ficticios: pagos, IVA, retención, recompensas, diferencias, duplicados legítimos, versiones, rollback, diez instituciones y confirmación HTTP. Ningún movimiento personal confirmado.
- Manual, límites y decisiones actualizados; sin nuevas dependencias, servicios o pagos obligatorios.

### Verificación de importación de efectivo Doopla

- [521 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42304406900).
- Commit probado: 47b01d5df4a0e8d97b3c3c5d66df40591a29bada.
- Veinte pruebas de integración y una del núcleo cubren pago por componentes, IVA separado, recompensa, comisión agrupada, ISR ausente/cero/no nulo y cobertura parcial, cartera/cobranza observadas, anexos repetidos, pagos iguales legítimos, moneda, PDF protegido, versiones, rollback, meses fuera de orden, diez instituciones y confirmación HTTP.
- Suite local y JavaScript aprobados; ejecución remota completa sin omisiones. Pruebas ficticias y ningún movimiento personal confirmado.
- Código, manual y límites publicados; cartera contable por préstamo, contrapartidas, reinversión, declaración anual y confirmación desde imágenes pendientes.


## 2026-11-06 — Fintual: efectivo del portafolio y valuación observada

- Plan automático y confirmación de efectivo con compras/ventas, depósitos/retiros y comisión/IVA separados; origen de capital pendiente.
- Posiciones anterior/actual, costo, valuación, variación, porcentaje, pendientes e ISR informativo conservados como observaciones sin ingresos/cargos adicionales.
- Etiqueta explícita de efectivo del portafolio en plan y libro; retención/neto de efectivo desconocidos hasta acreditar atribución fiscal.
- Moneda documentada y PDF protegido con contraseña transitoria; quince pruebas nuevas sobre conceptos, impuestos informativos, gastos, vacíos, duplicados legítimos, versiones, rollback, once instituciones y confirmación HTTP.
- Muestra real comprobada solo mediante plan bloqueado por inconsistencia del valor inicial de cartera; ningún movimiento personal confirmado. Manual y límites publicados, sin nuevas dependencias o pagos.

### Verificación de importación de efectivo Fintual

- [536 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42307559452).
- Commit probado: 58b9e27060317cd73ac9f5183a03a245e7390407.
- Quince pruebas nuevas cubren efectivo único, compra/venta sin ganancia supuesta, ISR informativo sin cargo o cero ficticio, valuación/porcentaje observados, comisión/IVA, vacío explícito, diferencias/NaN/moneda, duplicados legítimos, meses fuera de orden, versiones, rollback, PDF protegido, once instituciones y confirmación HTTP.
- Suite local y JavaScript aprobados; ejecución remota completa sin omisiones. La muestra real se utilizó solo para verificar el bloqueo de inconsistencia en la composición del saldo inicial, con cero movimientos personales confirmados.
- Código y manual publicados; unidades/costo por lote, continuidad de posiciones, atribución fiscal y reinversión confirmada permanecen pendientes.


## 2026-11-06 — Alpaca: efectivo USD, dividendos y retención extranjera

- Plan automático y confirmación de efectivo USD con compras/ventas, dividendos/intereses, comisiones y retención extranjera separados; sin ISR mexicano supuesto ni conversión de monedas.
- Tipos de dividendo y retención extranjera en el núcleo, incluido cero extranjero explícito sin generar cero mexicano.
- Posiciones/costo/resultados, acumulados y operaciones conservados como observaciones; Memopost solo excluido con efecto monetario cero acreditado.
- Control de Holdings frente a cierre, Cost and Fees frente a comisiones, secciones y conceptos admitidos. PDF protegido con contraseña transitoria, sin guardarla.
- Diecisiete pruebas de integración y dos del núcleo con datos ficticios: ingreso/impuesto, compra/venta, gastos, acumulados, discrepancias, instrumentos no admitidos, Memopost, versiones, rollback, doce instituciones/USD-MXN y confirmación HTTP.
- Código y manual preparados sin nuevas dependencias, servicios o pagos obligatorios; ningún movimiento personal confirmado.

### Verificación de importación de efectivo Alpaca

- [555 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42311958286).
- Commit probado: 8cede6caf098577d5f17bea35cef04aadee9a356.
- Diecisiete pruebas de integración y dos del núcleo cubren efectivo USD único, dividendos/retención extranjera distintos de interés/ISR mexicano, compra/venta, comisiones y Fees sin duplicar, cero extranjero, valuación/acumulados, Holdings/cierre, moneda/instrumentos, Memopost, meses fuera de orden, versiones, rollback, contraseña transitoria, doce instituciones y confirmación HTTP.
- Suite local y JavaScript aprobados; ejecución remota completa sin omisiones. Pruebas ficticias y ningún movimiento personal confirmado.
- Código, manual y límites publicados; lotes/costo, ganancia realizada calculada, fiscalidad mexicana, conversión documentada y reinversiones permanecen pendientes.


## 2026-11-06 — Corrección de identidad: Fintual MXN/USD

- Por instrucción del titular, Alpaca deja de ser institución de registro y navegación; se conserva exclusivamente como custodio/perfil técnico de Fintual USD.
- Detección, selección manual, bandeja, plan y libro muestran Fintual. Nuevos documentos financieros guardan Fintual como institución; MXN/USD mantienen cuentas e importes separados.
- Compatibilidad con documentos/lotes previos sin reescribir originales o auditoría, alterar referencias financieras o duplicar movimientos. Catálogo sin institución independiente Alpaca.
- Ocho pruebas nuevas de identidad, selección, dos portafolios, registro en base, compatibilidad, agrupación y flujo HTTP; manuales y documentación corregidos.

### Verificación de identidad Fintual

- [563 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42316543597).
- Commit probado: 99ae699ce479e5bc67e304f0400bfaf1d5638991.
- Ocho pruebas nuevas verifican institución/candidatos/catálogo Fintual, selección del lector USD, registro financiero como Fintual, cuentas MXN/USD separadas, presentación compatible de documentos/lotes anteriores sin reescribir auditoría ni duplicar, agrupación y HTTP.
- Suite local y JavaScript aprobados; ejecución remota completa. Corrección limitada a identidad, presentación y compatibilidad; importes e impuestos sin cambios.


## 2026-11-06 — YoTePresto: apertura acreditada y desglose de cobro único

- Plan automático con revisión explícita del candidato de apertura de efectivo o enlace a cierre contiguo confirmado, sin confundir saldo global con efectivo.
- Pago único enlazado a préstamo preexistente: principal cotejado con cambio de saldo e interés/IVA mensuales, con ISR e IVA retenido separados y comisión con IVA una vez.
- Cartera/acumulados/atrasos observados, sin rendimientos o capital externo duplicados. Pagos/retenciones múltiples, cancelaciones y referencias ambiguas bloqueados.
- Revisión de apertura ligada a documento, versión y plan; moneda y contraseña temporal también admitidas. Transacción, reintentos, continuidad y fechas preservados.
- Catorce pruebas nuevas de apertura, componentes, controles, cero/ausencia ISR, meses en ambos órdenes, revisión/rollback y confirmación HTTP; datos exclusivamente ficticios.
- Manual y límites documentados; sin nuevas dependencias o pagos. Fintual sigue siendo la institución de sus portafolios MXN/USD.

### Verificación de importación YoTePresto

- [577 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42317499606).
- Commit probado: b6a2994ec8cac983305db10c704b1af745cc0236.
- Catorce pruebas nuevas cubren candidato de apertura sin aprobación automática, revisión ligada al plan/versión, valores inválidos, principal/pago único, interés/IVA/ISR/comisión, ambigüedades, cero/ausencia de retención, enlace contiguo, meses fuera de orden, solapamientos, moneda, rollback, contraseña y flujo HTTP.
- Suite local y JavaScript aprobados; ejecución remota completa. Documentos ficticios y ningún movimiento personal confirmado.
- Código y manual publicados. Pagos múltiples, cancelaciones, cartera contable, reinversión, fiscalidad anual y confirmación desde imágenes pendientes. Identidad Fintual MXN/USD preservada.


## 2026-11-06 — CETESdirecto: efectivo liquidado y cobros sin desglose

- Plan automático y confirmación de efectivo, compras, cobros e ISR; posiciones, precios, resultados y acumulados como observaciones.
- Amortización/venta como cobro de valores sin asignación de principal/interés, sin calcular capital desde valuación o duplicar el interés informado. Interés clasificado/neto desconocidos mientras falte asignación.
- Registro y liquidación separados; fecha efectiva de liquidación dentro del período. Folios con distintas operaciones y cobros iguales legítimos conservan evidencias.
- Moneda documentada y contraseña transitoria para PDF protegido; columnas, cierres y totales normalizados, transacción y reintentos existentes.
- Dieciocho pruebas de integración y una del núcleo: efectivo/valuación, cobros, interés/ISR período-acumulado, fechas, códigos, vacíos, duplicados, meses fuera de orden, versiones/rollback, HTTP y coexistencia sin alterar Fintual MXN/USD.
- Muestra real usada solo para verificar bloqueo por efectivo de resumen/detalle discordante, sin confirmar movimientos personales. Manual y límites documentados, sin nuevas dependencias o pagos.

### Verificación de importación de efectivo CETESdirecto

- [596 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42318251572).
- Commit probado: a121e77cab6a01f23312eee9f97c2365a1a25e4a.
- Dieciocho pruebas de integración y una del núcleo cubren cuenta de efectivo, cobros sin principal/interés supuestos, interés informado/clasificado, ISR período/acumulado, registro/liquidación, folios por código, venta, columnas, vacíos, operaciones iguales legítimas, meses fuera de orden, versiones, rollback, contraseña, HTTP y coexistencia con Fintual MXN/USD.
- Suite local y JavaScript aprobados; ejecución remota completa. Muestra real usada únicamente para comprobar el bloqueo de discrepancia entre efectivo del resumen y detalle; ningún movimiento personal confirmado.
- Código, manual y límites publicados. Desglose de cobros, títulos/costo por lote, continuidad de posiciones, reinversión y fiscalidad anual pendientes; Fintual mantiene su identidad corregida.


## 2026-11-06 — Cierre de pagos múltiples y cancelaciones YoTePresto

- Desglose revisado por fila para pagos y retenciones múltiples, con préstamo acreditado, sumas exactas y controles mensuales; sin prorrateos de agregados.
- Cancelaciones de préstamo/pago/comisión/retención enlazadas a originales del mismo documento o meses anteriores. Reversos de componentes exactos y protección contra reutilizar/corregir un original sin resolver evidencia.
- Tipos de reverso/devolución y netos coherentes de interés/IVA/ISR/comisión; devoluciones sin ingreso o capital externo ficticios. Originales/auditoría conservados.
- Continuidad global/efectivo/saldos y cambios de acumulados por préstamo, en ambos órdenes de meses. Ausencia explícita de movimientos distinguida de tabla ausente.
- Interfaz de revisión y selección de originales, con confirmación ligada a versión/hash y operación atómica. PDF protegido y revisiones de apertura/moneda compatibles; documentación reescrita alrededor del flujo completo.
- Treinta pruebas nuevas del flujo y tres del núcleo, exclusivamente ficticias; ningún movimiento personal confirmado. Sin nuevas dependencias o pagos, manteniendo Fintual MXN/USD.


### Verificación del cierre de pagos múltiples y cancelaciones YoTePresto

- [629 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42321231780).
- Commit probado: a2e54295eebec3af4ada6bf53beee703543cb023.
- Treinta pruebas nuevas de integración y tres del núcleo verifican pagos/retenciones múltiples, revisión por fila, cancelaciones de los cuatro tipos con originales actuales o históricos, compatibilidad con planes anteriores, componentes exactos, dobles reversos, cambios del original, continuidad en ambos órdenes, importes/préstamos inválidos, tablas vacías/ausentes, versiones, rollback, PDF protegido y HTTP.
- Suite local y JavaScript aprobados; ejecución remota completa. Datos de prueba ficticios y ningún movimiento personal confirmado.
- Código y manual publicados. Si el documento no acredita el desglose o el original, la aplicación solicita revisión o bloquea la confirmación; no inventa información. Cartera contable completa, reinversión automática, fiscalidad anual y confirmación financiera desde imágenes conservan sus límites documentados.


## 2026-11-06 — Evolución financiera por cuenta y período

- Consulta local de solo lectura sobre instantánea SQLite: historia cronológica por cuenta/moneda y fechas internas del documento, sin reconstruir meses ni sumar posiciones.
- Panel por categoría/institución/producto, filtro de cuenta, tablas de apertura/aportaciones/retiros/interés/ISR/neto/cierre y detalle con evidencia y componentes.
- Separación de capital externo, cashback, traspasos, reinversión, dividendos, impuesto extranjero, IVA, comisiones y cobros de valores sin desglose. Desconocido no equivale a cero; cancelaciones/devoluciones pueden producir netos negativos.
- Cierre calculado frente al documental, huecos contiguos, revisiones posteriores y movimientos fuera de cobertura visibles, sin ajustar o reescribir el libro.
- Diecisiete pruebas nuevas con datos ficticios; coexistencia de trece instituciones integradas y Fintual MXN/USD sin institución independiente del custodio. Sin dependencias o pagos nuevos. Manual EVOLUCION.md y plan actualizados.
- Verificación sintáctica JavaScript y flujo HTTP; validación visual en navegador pendiente porque el ejecutable Chromium no está disponible en este entorno. Ningún dato personal importado.

### Verificación de evolución financiera

- [646 pruebas aprobadas, sin omisiones](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42326357613).
- Commit probado: 6351a1c52db88f6e09b49e7d94ca1a92b02711d6.
- Diecisiete pruebas nuevas: anclas y traspasos sin capital duplicado, períodos fuera de orden/huecos, desconocido/cero, Fintual MXN/USD, cobros sin desglose, cancelaciones históricas, precisión decimal, revisiones dentro/fuera de período y cuenta, coexistencia de trece instituciones, lectura consistente y HTTP.
- Suite local y JavaScript aprobados; ejecución remota completa. No se modificaron datos personales. La revisión visual en navegador permanece pendiente por ausencia de Chromium en este entorno.


## 2026-11-06 — Nu: confirmación financiera con distribución acreditada

- Cuenta/Cajitas agregadas/garantía separadas, con revisión de aperturas y distribución de bruto/ISR ligada a documento, versión y plan. Globales registrados una vez al cierre por resumen, no como pagos diarios.
- Traspasos con dos patas documentales únicas; congelar/descongelar conserva observación neutral, sin capital externo, ingresos o reinversión ficticios.
- Controles de composición, tablas, signos, fechas, importes, conceptos, depósitos/gastos brutos, cierres y continuidad. Apertura contigua no asigna rendimientos no nulos automáticamente.
- PDF protegido con contraseña temporal, revisión de moneda, emisor histórico, confirmación atómica y evolución por producto. Sin saldos individuales inventados por Cajita ni nuevas dependencias/pagos.
- Diecinueve pruebas nuevas, exclusivamente ficticias; ningún movimiento personal importado. Manual IMPORTACION-NU.md, documentación y decisión D029 actualizados. Revisión visual de navegador pendiente por ausencia de Chromium en el entorno.

### Verificación local de importación Nu

- 665 pruebas aprobadas, sin omisiones, en la suite completa local; JavaScript sin errores sintácticos.
- Commit del código probado: 125c2ccb4bad74a72715f285a212e3e29eab4962.
- Diecinueve pruebas nuevas verifican separación de productos, desgloses explícitos, traspasos, reconocimiento al cierre, controles de filas/totales, monedas, revisiones/planes, historia, atomicidad, contraseñas y HTTP.
- Código y manual publicados en main. La consulta de Actions todavía no devuelve una ejecución para este commit; verificación remota pendiente, sin atribuirle el resultado local. Revisión visual en navegador también pendiente por ausencia de Chromium en el entorno.


## 2026-11-06 — Cierre del flujo Nu por Cajita individual

- La ejecución pendiente del incremento anterior ya aprobó: [665 pruebas en GitHub](https://github.com/D3ckardCain/MIS-FINANZAS-IA/actions/runs/42327724619), commit 125c2ccb4bad74a72715f285a212e3e29eab4962.
- Desglose individual acreditado sustituye el agregado: cuenta por Cajita, incluso sin movimientos, con apertura/cierre/bruto/ISR y conciliación global e individual. Nombres normalizados, historia contigua, no omisión de Cajitas históricas ni mezcla automática de granularidades.
- Cashback explícito como aportación con origen, sin interés adicional; congelamientos como evidencia de liquidez, sin activo o reinversión duplicados.
- Doce pruebas adicionales y 677 pruebas locales aprobadas, sin omisiones; controles de JavaScript aprobados. Ningún dato personal importado.
- Chrome local no se pudo instalar: el destino de descarga entregó HTML en lugar del ZIP. Se incorpora comprobación automática de navegador en Actions con carga ficticia, revisión individual, confirmación, evolución y móvil; capturas de un día. Resultado remoto del nuevo incremento por verificar.
- Manuales, plan y decisión D030 actualizados; no se añadieron dependencias de pago ni servicios críticos externos.
