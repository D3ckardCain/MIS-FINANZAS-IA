"""Catálogo de lectores por institución y vista; lectura documental sin importación."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
import re
import unicodedata

from .storage import document_id
from .openbank import OpenbankDebitReader, OpenbankInvestmentReader


class ReaderError(ValueError):
    pass


def fold(value):
    text = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.replace("\u00ad", "-")).strip().lower()


_MONTHS = {
    "ene": 1, "enero": 1, "feb": 2, "febrero": 2, "mar": 3, "marzo": 3,
    "abr": 4, "abril": 4, "may": 5, "mayo": 5, "jun": 6, "junio": 6,
    "jul": 7, "julio": 7, "ago": 8, "agosto": 8, "sep": 9, "sept": 9,
    "septiembre": 9, "oct": 10, "octubre": 10, "nov": 11, "noviembre": 11,
    "dic": 12, "diciembre": 12,
}
_MONTH_PATTERN = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DAY = r"(?:0?[1-9]|[12]\d|3[01])"
_MONTH = r"(?:0?[1-9]|1[0-2]|" + _MONTH_PATTERN + ")"
_DATE_PATTERN = r"(?:\d{4}-\d{2}-\d{2}|" + _DAY + r"[ /.-]+" + _MONTH + r"\.?[ /.-]+\d{4}|" + _DAY + r"[ /.-]+" + _MONTH + r"\.?[ /.-]+\d{2})"
_NUMBER = re.compile(r"(?<![\w.,])[-+−]?\s*\$?\s*((?:\d{1,3}(?:,\d{3})+|\d*)\.\d+)(?![\w.,])")
_DATE_START = re.compile(r"^\s*(?:" + _DATE_PATTERN + r"|\d{1,2}/\d{1,2}|\d{1,2}(?=\s))", re.I)


def parse_date(value):
    value = fold(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    parts = [p for p in re.split(r"[ /.-]+", value) if p]
    if len(parts) != 3:
        raise ReaderError("Fecha documental no admitida")
    day, month, year = parts
    month = _MONTHS.get(month, int(month) if month.isdigit() else 0)
    year = int(year)
    return date(year + 2000 if year < 100 else year, month, int(day))


def periods(text):
    text = fold(text)
    found = []
    # Rangos completos con fechas ISO, numéricas o meses en español.
    for match in re.finditer(r"(" + _DATE_PATTERN + r")\s*(?:al|a|—|–|-)\s*(" + _DATE_PATTERN + r")", text):
        try:
            found.append((parse_date(match[1]), parse_date(match[2])))
        except ValueError:
            raise ReaderError("Rango de fechas inválido")
    # Nu, Hey y SuperTasas: primer día sin mes/año propio.
    short = r"(?<!\d)(?:del\s+|periodo\s*:\s*)?(\d{1,2})\s+al\s+(\d{1,2})\s+(?:de\s+)?(" + _MONTH_PATTERN + r")\s+(?:del?\s+)?(\d{4})"
    for match in re.finditer(short, text):
        found.append((date(int(match[4]), _MONTHS[match[3]], int(match[1])),
                      date(int(match[4]), _MONTHS[match[3]], int(match[2]))))
    # Reporte operativo Fondeadora: Mes día - mes día, año.
    for match in re.finditer(r"(" + _MONTH_PATTERN + r")\s+(\d{1,2})\s*-\s*(" + _MONTH_PATTERN + r")\s+(\d{1,2}),?\s+(\d{4})", text):
        found.append((date(int(match[5]), _MONTHS[match[1]], int(match[2])),
                      date(int(match[5]), _MONTHS[match[3]], int(match[4]))))
    if any(end < start for start, end in found):
        raise ReaderError("Período invertido")
    return tuple(dict.fromkeys(found))


@dataclass(frozen=True)
class Profile:
    key: str
    name: str
    identity: str
    debit_start: tuple[str, ...]
    investment_start: tuple[str, ...]
    shared_account: bool = False
    notes: tuple[str, ...] = ()


PROFILES = (
    Profile("alpaca", "Alpaca", r"alpaca",
            ("cash summary", "income", "fees", "transaction"),
            ("account summary", "holdings", "income", "transaction"),
            True, ("Acciones/ETF y efectivo USD pertenecen a una misma cuenta de corretaje.",
                   "Separar período y acumulado; Memopost no es una operación económica de efectivo.")),
    Profile("bancoppel", "BanCoppel", r"bancoppel",
            ("detalle de movimientos", "resumen de la cuenta", "calculo de intereses"),
            ("inversiones vigentes", "inversion a plazo"),
            notes=("Cuenta de paso: no interpretar sus entradas como aportación externa sin conciliación.",)),
    Profile("didi", "DiDi Cuenta", r"j\.p\. sofiexpress|didicuenta\.com",
            ("resumen de cuenta didi", "detalles de movimientos didi", "monto item", "item monto"),
            ("resumen de cuenta didi", "detalles de movimientos didi", "monto item", "item monto"),
            True, ("La misma cuenta genera rendimiento; Dépositos puede incluir esos rendimientos.",
                   "Conservar escalones y condiciones; no aplicar una tasa única a todo el saldo.")),
    Profile("cetesdirecto", "CETESdirecto", r"cetesdirecto\.com",
            (), ("resumen del portafolio", "posicion final", "posicion inicial", "movimientos del periodo"),
            notes=("Posición de mercado y efectivo son conceptos distintos.",
                   "Mantener operación y liquidación separadas; no cuadrar diferencias por ajuste ficticio.")),
    Profile("doopla", "Doopla", r"doopla\.mx",
            (), ("resumen", "efectivo disponible", "movimientos del periodo", "detalle de", "prestamos", "portafolio"),
            notes=("Separar capital, interés, IVA, comisiones e ISR; no sumar acumulados a los del mes.",
                   "La conciliación del efectivo no certifica conciliación de la cartera de préstamos.")),
    Profile("fintual", "Fintual", r"fintual",
            (), ("cartera periodo actual", "cartera periodo anterior", "resumen de movimientos",
                 "movimientos del periodo", "rendimiento neto del portafolio", "impuestos retenidos"),
            notes=("Títulos, precio y valuación no equivalen a interés cobrado.",
                   "No duplicar venta de títulos y retiro del efectivo; distinguir cuentas/PPR.")),
    Profile("fondeadora", "Fondeadora", r"apoyomultiple\.com|fondea\s+technologies|fondeadora\.com",
            ("detalles de la cuenta", "detalle del mes", "detalles del mes", "reporte de movimientos", "movimientos", "saldo inicial"),
            ("boveda", "rendimientos", "ahorro"),
            notes=("Un reporte operativo vacío no demuestra ausencia histórica de inversiones.",
                   "No inferir una Bóveda a partir de una mención publicitaria.")),
    Profile("hey", "Hey", r"hey,? banco|inversion hey",
            ("cheques", "saldo inicial", "dia concepto", "detalle de movimientos"),
            ("inversiones", "inversion hey", "inversion tasa", "inversiones vigentes", "fecha inversion"),
            notes=("Capital vencido, interés cobrado e ISR se conservan separados de la renovación.",
                   "Interés del resumen puede ser neto; devengado no equivale a cobrado.")),
    Profile("kapital", "Kapital", r"kapital",
            ("resumen informativo", "saldo inicial", "dia folio"),
            ("inversion a plazo", "gat", "tasa capital"),
            notes=("Interés bruto, ISR y total neto de contratos vigentes pueden ser proyecciones.",
                   "Conservar plazo, fecha inicial, vencimiento y base contractual de días.")),
    Profile("nu", "Nu", r"cuenta nu|nu mexico",
            ("detalle de movimientos en tu cuenta",),
            ("detalle de movimientos de tus cajitas", "dinero generado antes de impuestos"),
            notes=("Congelar y descongelar no es una aportación externa ni un segundo ingreso.",
                   "La tasa informativa mensual no sustituye la tasa de cada contrato congelado.")),
    Profile("openbank", "Openbank", r"openbank", ("cuenta debito open light",), ("apartado open",)),
    Profile("supertasas", "SuperTasas", r"supertasas\.com",
            ("resumen de movimientos en cuenta a la vista", "detalle de movimientos en cuenta a lavista",
             "detalle de movimientos en cuenta a la vista"),
            ("resumen de rendimiento en cuenta a la vista", "resumen de movimientos en cuenta a la vista",
             "detalle de movimientos en cuenta a lavista", "detalle de movimientos en cuenta a la vista",
             "resumen de inversiones a plazo vigentes"),
            True, ("La cuenta a la vista es compartida; no duplicar sus movimientos entre vistas.",
                   "Capital al vencimiento e interés neto estimado no son cobros ya realizados.")),
    Profile("plata", "Plata", r"banco plata",
            ("plata cuenta", "movimientos de plata cuenta"),
            ("ahorro flexible", "movimientos de ahorro flexible"),
            notes=("Depósitos y rendimientos es un agregado; no registrarlo otra vez junto al detalle.",
                   "Cashback es origen de aportación y debe conservar su vínculo.",
                   "Un cobro incluido en el documento puede estar registrado después del corte.")),
    Profile("mifel", "Mifel", r"banca mifel",
            ("resumen de cuenta a la vista", "detalles de la cuenta a la vista", "suma de retiros"),
            ("resumen de cuenta a la vista", "rendimientos y valuacion", "detalles de la cuenta a la vista",
             "suma de retiros", "inversiones a plazo", "fondos de inversion", "mesa de dinero"),
            True, ("La cuenta remunerada participa en ambas vistas; una sola identidad contable.",
                   "Conservar fechas/períodos de devengo de pagos agrupados e ISR separado.")),
)
_BY_KEY = {profile.key: profile for profile in PROFILES}


@dataclass(frozen=True)
class Observation:
    id: str
    page: int
    line: int
    section: str
    kind: str
    cells: tuple[str, ...]
    numbers: tuple[Decimal, ...]
    percentages: tuple[Decimal, ...]

    @property
    def locator(self):
        return f"pagina {self.page}, linea {self.line}"


@dataclass(frozen=True)
class DocumentPreview:
    institution: str
    lane: str
    document_id: str
    periods: tuple[tuple[date, date], ...]
    observations: tuple[Observation, ...]
    status: str
    issues: tuple[str, ...]
    shared_account: bool

    @property
    def ready_to_import(self):
        # La evidencia documental aún necesita un mapeo económico y revisión.
        return False


_STOP = (
    "glosario", "avisos legales", "comunicados", "informacion importante",
    "sello digital", "cadena original", "comprobante fiscal", "cargos objetados",
    "advertencias", "mensajes importantes", "nuestra guia", "condusef",
)
_KINDS = (
    ("tax_cumulative", r"isr.*acumulad|reten.*acumulad"),
    ("tax", r"\bisr\b|i\.s\.r|reten.*impuesto|impuesto.*reten"),
    ("cashback", r"cashback"),
    ("forecast", r"estimad|al vencimiento|al venc\b"),
    ("freeze", r"congel|descongel"),
    ("capital", r"capital|pago cap"),
    ("interest", r"interes|rendimiento|dinero generado"),
    ("fee", r"comision"),
    ("vat", r"\biva\b"),
    ("balance", r"saldo|posicion|valuacion|cartera"),
    ("transfer", r"spei|transfer|cuentas propias|cuenta propia"),
    ("movement", r"deposit|retiro|abono|cargo|compra|venta|pago"),
)


def _kind(text, section):
    for name, pattern in _KINDS:
        if re.search(pattern, text):
            return name
    if any(term in fold(section) for term in ("plazo", "inversiones vigentes", "tasa capital", "fecha inversion")):
        return "contract"
    return "documentary"


def _heading(value, prefixes):
    return any(value.startswith(prefix) for prefix in prefixes)


class StatementReader:
    """Lector documental de una vista; no es un importador contable."""
    def __init__(self, institution, lane):
        if institution not in _BY_KEY or lane not in ("debit", "investments"):
            raise ReaderError("Institución o vista no admitida")
        self.profile = _BY_KEY[institution]
        self.lane = lane

    def read_image(self, content, *, engine=None):
        from .imaging import read_statement_image
        return read_statement_image(content, self.profile.key, self.lane, engine=engine)

    def read_reconciled_pdf(self, content):
        """Conciliación estricta optativa; conserva el lector documental general."""
        if self.profile.key == "alpaca":
            from .alpaca import AlpacaReader
            return AlpacaReader(self.lane).read_pdf(content)
        if self.profile.key == "fondeadora":
            from .fondeadora import FondeadoraReader
            return FondeadoraReader(self.lane).read_pdf(content)
        if self.profile.key == "hey":
            from .hey import HeyReader
            return HeyReader(self.lane).read_pdf(content)
        if self.profile.key == "fintual" and self.lane == "investments":
            from .fintual import FintualInvestmentReader
            return FintualInvestmentReader().read_pdf(content)
        if self.profile.key == "didi":
            from .didi import DidiReader
            return DidiReader(self.lane).read_pdf(content)
        if self.profile.key == "doopla":
            from .doopla import DooplaReader
            return DooplaReader(self.lane).read_pdf(content)
        if self.profile.key == "bancoppel" and self.lane == "debit":
            from .bancoppel import BanCoppelDebitReader
            return BanCoppelDebitReader().read_pdf(content)
        if self.profile.key == "cetesdirecto" and self.lane == "investments":
            from .cetesdirecto import CetesDirectoInvestmentReader
            return CetesDirectoInvestmentReader().read_pdf(content)
        if self.profile.key == "openbank":
            return self.read_pdf(content)
        raise ReaderError("Conciliación detallada no disponible para este perfil/vista")

    def read_document(self, content, *, engine=None):
        if not isinstance(content, bytes):
            raise ReaderError("Se requieren los bytes del documento")
        if content[:1024].lstrip().startswith(b"%PDF-"):
            return self.read_pdf(content)
        return self.read_image(content, engine=engine)

    def read_pdf(self, content):
        try:
            from pypdf import PdfReader
            from pypdf.errors import PyPdfError
        except ImportError as error:
            raise ReaderError("Falta el extra PDF: instalar requirements-pdf.txt") from error
        if not isinstance(content, bytes):
            raise ReaderError("Se requieren los bytes del PDF")
        try:
            if self.profile.key == "openbank":
                cls = OpenbankDebitReader if self.lane == "debit" else OpenbankInvestmentReader
                return cls().read_pdf(content)
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ReaderError("PDF cifrado: no se intentan contraseñas")
            pages = tuple(page.extract_text(extraction_mode="layout") or "" for page in reader.pages)
            return self.read_pages(pages, document_id(content))
        except PyPdfError as error:
            raise ReaderError("PDF no legible; no se generan movimientos") from error

    def read_pages(self, pages, identifier):
        if self.profile.key == "openbank":
            cls = OpenbankDebitReader if self.lane == "debit" else OpenbankInvestmentReader
            return cls().read_pages(pages, identifier)
        if not isinstance(identifier, str) or not identifier.strip():
            raise ReaderError("Huella documental requerida")
        pages = tuple(pages)
        text = fold(" ".join(pages))
        if not text or not re.search(self.profile.identity, text):
            raise ReaderError("El documento no acredita la institución elegida")
        detected_periods = periods(" ".join(pages[:2]))
        issues = []
        if not detected_periods:
            issues.append("Período documental no reconocido; no se usa nombre ni fecha de correo")
        elif len(detected_periods) != 1:
            issues.append("Varios períodos detectados: revisión necesaria")
        own = self.profile.debit_start if self.lane == "debit" else self.profile.investment_start
        other = self.profile.investment_start if self.lane == "debit" else self.profile.debit_start
        observations = []
        section = None
        selected = False
        for page_no, page in enumerate(pages, 1):
            # Continúa una tabla entre páginas solo mediante filas de datos o encabezado repetido.
            continuing = section
            section = None
            for line_no, line in enumerate(page.splitlines(), 1):
                compact = fold(line)
                if not compact:
                    continue
                if _heading(compact, _STOP) or compact.startswith("emitido por"):
                    section = None
                    continuing = None
                    continue
                if _heading(compact, own):
                    section = compact
                    continuing = section
                    selected = True
                elif _heading(compact, other) and not self.profile.shared_account:
                    section = None
                    continuing = None
                    continue
                elif section is None and continuing and _DATE_START.match(compact):
                    section = continuing
                if section is None:
                    continue
                # No extraer datos de identidad de cabeceras personales como valores financieros.
                if re.search(r"\brfc\b|r\.f\.c|clabe|domicilio|numero de cliente|numero de cuenta", compact):
                    if compact.startswith(("movimientos de", "detalles de")):
                        continue
                    continue
                numbers = []
                for match in _NUMBER.finditer(line):
                    # El signo pertenece a la observación; no inferir si es cargo/abono por ausencia de signo.
                    token = match.group(0).replace("$", "").replace(",", "").replace("−", "-")
                    token = re.sub(r"\s+", "", token)
                    try:
                        numbers.append(Decimal(token))
                    except Exception:
                        raise ReaderError("Importe documental no reconocido")
                percent = tuple(Decimal(v.replace(",", ".")) for v in
                                re.findall(r"(\d+(?:[.,]\d+)?)\s*%", line))
                kind = _kind(compact, section)
                if numbers or percent or _DATE_START.match(compact) or _heading(compact, own):
                    stable = sha256(f"{identifier}:{page_no}:{line_no}".encode()).hexdigest()
                    cells = tuple(part.strip() for part in re.split(r"\s{2,}", line.strip()) if part.strip())
                    observations.append(Observation(stable, page_no, line_no, section, kind,
                                                    cells, tuple(numbers), percent))
        if not selected:
            issues.append("Sección no presente en este documento; no significa saldo cero ni producto inexistente")
            status = "section_missing"
        else:
            status = "review_required"
            issues.append("Evidencia extraída; falta mapeo económico y conciliación específicos para importar")
        issues.extend(self.profile.notes)
        return DocumentPreview(self.profile.key, self.lane, identifier, detected_periods,
                               tuple(observations), status, tuple(issues), self.profile.shared_account)


def reader_for(institution, lane):
    if institution in ("bingx", "pionex"):
        if lane != "investments":
            raise ReaderError("Esta plataforma usa capturas de operaciones; débito bancario no aplica")
        from .crypto_images import BingXImageReader, PionexImageReader
        return (BingXImageReader if institution == "bingx" else PionexImageReader)()
    return StatementReader(institution, lane)


def available_readers():
    return tuple((p.key, lane) for p in PROFILES for lane in ("debit", "investments")) + (
        ("bingx", "investments"), ("pionex", "investments"))


def main(argv=None):
    """Salida local; --details incluye evidencia privada, nunca realiza importación."""
    import argparse
    from dataclasses import asdict
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Lectores locales por institución y vista")
    parser.add_argument("pdf", nargs="?", metavar="ARCHIVO")
    parser.add_argument("--institution", choices=tuple(_BY_KEY) + ("bingx", "pionex"))
    parser.add_argument("--lane", choices=("debit", "investments"))
    parser.add_argument("--list", action="store_true", dest="list_readers")
    parser.add_argument("--details", action="store_true")
    parser.add_argument("--ocr-language", help="Idiomas locales, por ejemplo spa+eng")
    parser.add_argument("--reconcile", action="store_true", help="Conciliación PDF detallada si está disponible")
    args = parser.parse_args(argv)
    if args.list_readers:
        print(json.dumps(available_readers(), ensure_ascii=False))
        return 0
    if not args.pdf or not args.institution or not args.lane:
        parser.error("Indicar archivo PDF/imagen, --institution y --lane")
    try:
        from .imaging import LocalOcr
        reader = reader_for(args.institution, args.lane)
        content = Path(args.pdf).read_bytes()
        if args.reconcile:
            if not hasattr(reader, "read_reconciled_pdf") or not content[:1024].lstrip().startswith(b"%PDF-"):
                raise ReaderError("La conciliación detallada requiere un PDF y un perfil compatible")
            result = reader.read_reconciled_pdf(content)
        else:
            result = reader.read_document(content, engine=LocalOcr(languages=args.ocr_language))
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        return 2
    if args.details:
        output = asdict(result)
    elif hasattr(result, "evidence"):
        output = {"institution": args.institution, "lane": args.lane,
                  "source": "image", "lines": len(result.evidence.lines),
                  "issues": result.issues, "ready_to_import": False}
        if hasattr(result, "operation_kind"):
            output["operation_kind"] = result.operation_kind
            output["fields_detected"] = [field.name for field in result.fields]
    elif isinstance(result, DocumentPreview):
        output = {
            "institution": result.institution, "lane": result.lane,
            "status": result.status, "periods": result.periods,
            "observations": len(result.observations), "issues": result.issues,
            "ready_to_import": False,
        }
    elif hasattr(result, "entries"):
        output = {"institution": args.institution, "lane": result.lane,
                  "detail_reconciled": result.detail_reconciled, "reconciled": result.reconciled,
                  "entries": len(result.entries), "issues": result.issues + result.detail_issues,
                  "ready_to_import": False}
        if hasattr(result, "cash_reconciled"):
            output.update(cash_reconciled=result.cash_reconciled, loan_positions=len(result.loans),
                          differences=len(result.differences))
        if hasattr(result, "scope"):
            output.update(scope=result.scope, investment_balance_known=result.investment_balance is not None)
    else:
        output = {"institution": "openbank", "lane": result.lane,
                  "reconciled": result.reconciled, "issues": result.issues,
                  "rows": len(result.rows), "ready_to_import": False}
    print(json.dumps(output, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
