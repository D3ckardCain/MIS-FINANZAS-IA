# Mapeo económico posterior a la extracción

El catálogo documental está disponible para todos los formatos bancarios/institucionales presentes. Esta lista delimita lo que falta antes de importar movimientos. No confundir extracción con conciliación terminada.

| Perfil | Trabajo económico pendiente |
| --- | --- |
| BanCoppel | Conciliación PDF del formato conocido implementada; pendientes identidad económica, enlace de transferencias y revisión de discrepancias del propio documento |
| DiDi | Conciliación PDF de dos formatos implementada, depósitos/rendimientos separados; pendientes enlace de transferencias, vigencia contractual de escalones y formatos con retención distinta de cero |
| CETESdirecto | Conciliación PDF de efectivo y posiciones implementada; pendientes identidad global, costo fiscal, distribución de amortizaciones y revisión de diferencias de resumen/detalle |
| Doopla | Lector PDF con conciliación por secciones implementado; pendientes resolver discrepancias documentales, vigencia de anexos, identidad económica de pagos y tratamiento fiscal |
| Fintual | Lector optativo de fondos MXN implementado; pendientes lotes, liquidación por ejecución, homologación de fondos, diferencias de totales y enlace de transferencias |
| Alpaca | Perfil USD con PDF/imagen y revisión optativa implementado; pendientes identidad de ejecuciones, guiones, entradas/salidas agregadas, lotes, acciones corporativas y conversión fiscal |
| Fondeadora | Lector operativo de estados/reportes implementado; pendientes estados/contratos de Bóveda/Apartados, identidad y enlace de traspasos, capital, tasa, rendimiento y retención de inversión |
| Hey | Lector del formato de pagarés implementado; pendientes diferencias documentales, composición histórica del saldo anterior, formatos adicionales y confirmación de propuestas de reinversión |
| Kapital | Lectores de ambos formatos implementados; pendientes confirmar equivalencias/vencimientos, completar huecos y enlazar transferencias antes de importar |
| Nu | Resumen y evidencia por secciones implementados; pendientes resolver diferencias de distribución, reconstruir contratos/cierres por Cajita/garantía y parear traspasos |
| Openbank | Identidad estable, continuidad entre meses, revisión y confirmación transaccional |
| SuperTasas | Cuenta remunerada y contratos, vencimiento/capital, interés cobrado y estimaciones |
| Plata | Separar agregado y detalle, cashback y vínculo interno, rendimientos/ISR posteriores al corte |
| BingX/Pionex | Validar capturas reales, completar identidad/fills y zona horaria, convertir candidatos revisados en operaciones; costo, bots, derivados y conciliación pendientes |
| Mifel | Lector de cuenta remunerada implementado; pendientes contrapartidas, formatos/productos adicionales y reglas contractuales de devengo/fiscalidad |

Ninguna diferencia se resolverá creando movimientos ficticios. Las condiciones históricas y los documentos complementarios se incorporarán con su evidencia.
