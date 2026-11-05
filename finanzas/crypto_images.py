"""BingX/Pionex: candidatos de operación desde capturas, siempre revisables."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
import unicodedata
from zoneinfo import ZoneInfo

from .imaging import LocalOcr, ImageEvidence, ImageReadError


def _fold(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)).casefold().strip()


ALIASES = {
    "order_id": ("order id", "id de orden", "id de la orden"),
    "trade_id": ("trade id", "execution id", "fill id", "id de ejecucion"),
    "transaction_id": ("transaction id", "txid", "id de transaccion"),
    "bot_id": ("bot id", "id del bot"),
    "time": ("time", "date", "fecha", "fecha y hora", "order time", "execution time", "hora"),
    "pair": ("trading pair", "pair", "symbol", "par", "simbolo"),
    "market": ("market", "product", "market type", "producto", "mercado", "tipo de mercado"),
    "side": ("side", "direction", "lado", "direccion"),
    "quantity": ("quantity", "filled quantity", "executed quantity", "cantidad", "cantidad ejecutada"),
    "contracts": ("position size", "contracts", "tamano de posicion", "contratos"),
    "price": ("price", "average price", "precio", "precio promedio"),
    "total": ("total", "value", "filled value", "valor", "importe"),
    "fee": ("fee", "fees", "trading fee", "comision", "comisiones"),
    "realized_pnl": ("realized pnl", "realized p&l", "pnl realizado", "p&l realizado"),
    "unrealized_pnl": ("unrealized pnl", "unrealized p&l", "pnl no realizado"),
    "pnl_displayed": ("pnl", "p&l", "profit", "beneficio"),
    "bot_profit": ("grid profit", "bot profit", "ganancia del bot", "beneficio del bot"),
    "funding": ("funding fee", "funding", "tarifa de financiacion", "financiacion"),
    "yield": ("interest", "yield", "rendimiento", "interes"),
    "status": ("status", "estado"),
}
_NUMERIC = {"quantity", "contracts", "price", "total", "fee", "realized_pnl",
            "unrealized_pnl", "pnl_displayed", "bot_profit", "funding", "yield"}


def parse_amount(value, *, decimal_mode="auto"):
    if decimal_mode not in ("auto", "international", "spanish"):
        raise ValueError("Convención decimal no admitida")
    found = re.fullmatch(r"\s*\$?\s*([+−-]?(?:\d[\d.,]*|\.\d+))(?:\s+([A-Za-z][A-Za-z0-9_-]{0,19}))?\s*", value)
    if not found:
        raise ValueError("Importe/unidad no reconocidos; no se corrigen O/0 ni I/1 automáticamente")
    token, unit = found.groups()
    token = token.replace("−", "-")
    if decimal_mode == "auto":
        if "," in token and "." in token:
            mode = "international" if token.rfind(".") > token.rfind(",") else "spanish"
        elif "," in token:
            chunks = token.lstrip("+-").split(",")
            if len(chunks) == 2 and len(chunks[1]) == 3 and chunks[0] != "0":
                raise ValueError("Separador decimal ambiguo")
            mode = "spanish" if len(chunks) == 2 else "international"
        else:
            unsigned = token.lstrip("+-")
            if unsigned.count(".") == 1:
                first, last = unsigned.split(".")
                if len(last) == 3 and first not in ("", "0"):
                    raise ValueError("Separador decimal ambiguo")
            mode = "international"
    else:
        mode = decimal_mode
    decimal, thousands = (".", ",") if mode == "international" else (",", ".")
    unsigned = token.lstrip("+-")
    pieces = unsigned.split(decimal)
    if len(pieces) > 2 or (len(pieces) == 2 and not pieces[1].isdigit()):
        raise ValueError("Formato decimal inválido")
    integer = pieces[0]
    groups = integer.split(thousands)
    if len(groups) > 1 and (not 1 <= len(groups[0]) <= 3 or
                           not groups[0].isdigit() or any(len(g) != 3 or not g.isdigit() for g in groups[1:])):
        raise ValueError("Agrupación de miles inválida")
    if not integer and not unsigned.startswith(decimal):
        raise ValueError("Importe inválido")
    try:
        amount = Decimal(token.replace(thousands, "").replace(decimal, "."))
    except InvalidOperation as error:
        raise ValueError("Importe inválido") from error
    if not amount.is_finite():
        raise ValueError("Importe no finito")
    return amount, unit.upper() if unit else None


@dataclass(frozen=True)
class FieldCandidate:
    name: str
    raw_value: str
    value: Decimal | str | None
    unit: str | None
    source_lines: tuple[str, ...]
    confidence: Decimal
    issues: tuple[str, ...]


@dataclass(frozen=True)
class CryptoOperationPreview:
    platform: str
    account: str | None
    evidence: ImageEvidence
    operation_kind: str
    fields: tuple[FieldCandidate, ...]
    issues: tuple[str, ...]
    timezone: str | None

    @property
    def ready_to_import(self):
        return False

    def field(self, name):
        found = [field for field in self.fields if field.name == name]
        return found[0] if len(found) == 1 else None

    @property
    def execution_identity(self):
        """Propuesta por cuenta/orden/fill; nunca toma la orden como único fill."""
        order, execution = self.field("order_id"), self.field("trade_id")
        if not self.account or not order or not execution or order.issues or execution.issues:
            return None
        if not order.value or not execution.value:
            return None
        return sha256(repr((self.platform, self.account, order.value, execution.value)).encode()).hexdigest()


def _label(line):
    folded = _fold(line)
    for name, aliases in ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            pattern = r"^" + re.escape(alias) + r"\s*(?:\(([A-Za-z][A-Za-z0-9_-]{0,19})\))?\s*(?::\s*(.*))?$"
            match = re.fullmatch(pattern, folded)
            if match:
                colon = line.find(":")
                value = line[colon + 1:].strip() if colon >= 0 else ""
                return name, value, match[1].upper() if match[1] else None
    return None


class CryptoImageReader:
    def __init__(self, platform, *, account=None, timezone=None, decimal_mode="auto"):
        if platform not in ("bingx", "pionex"):
            raise ValueError("Plataforma no admitida")
        if decimal_mode not in ("auto", "international", "spanish"):
            raise ValueError("Convención decimal no admitida")
        if timezone is not None:
            ZoneInfo(timezone)
        self.platform, self.account, self.timezone, self.decimal_mode = platform, account, timezone, decimal_mode

    def read_image(self, content, *, engine=None):
        return self.read_evidence((engine or LocalOcr()).read(content))

    def read_document(self, content, *, engine=None):
        return self.read_image(content, engine=engine)

    def read_evidence(self, evidence):
        if not isinstance(evidence, ImageEvidence):
            raise ValueError("Se requiere evidencia OCR")
        lines = evidence.lines
        full = _fold(" ".join(line.text for line in lines))
        other = "pionex" if self.platform == "bingx" else "bingx"
        if other in full and self.platform not in full:
            raise ImageReadError("La captura muestra otra plataforma")
        issues = list(evidence.issues)
        if other in full and self.platform in full:
            issues.append("Varias plataformas visibles: comprobar el alcance de la captura")
        if self.platform not in full:
            issues.append("Marca de plataforma no visible: confirmar selección contra la imagen")
        fields = []
        for index, line in enumerate(lines):
            labeled = _label(line.text)
            if labeled is None:
                continue
            name, raw, label_unit = labeled
            sources, confidence = (line.id,), line.confidence
            if not raw and index + 1 < len(lines) and _label(lines[index + 1].text) is None:
                next_line = lines[index + 1]
                raw = next_line.text.strip()
                sources += (next_line.id,)
                confidence = min(confidence, next_line.confidence)
            local_issues = []
            value, unit = raw or None, label_unit
            if name in _NUMERIC and raw:
                try:
                    value, value_unit = parse_amount(raw, decimal_mode=self.decimal_mode)
                    if label_unit and value_unit and label_unit != value_unit:
                        local_issues.append("Unidad de etiqueta y valor incompatibles")
                        value = None
                    unit = value_unit or label_unit
                    if unit is None:
                        local_issues.append("Unidad/activo no visible; no inferir MXN, USD ni USDT")
                except ValueError as error:
                    value = None
                    local_issues.append(str(error))
            if not raw:
                local_issues.append("Valor no visible")
            flagged_line = any("Baja confianza OCR:" in issue and any(source in issue for source in sources)
                               for issue in evidence.issues)
            if confidence < 85 or flagged_line:
                local_issues.append("Lectura OCR de baja confianza")
            issues.extend(name + ": " + issue for issue in local_issues)
            fields.append(FieldCandidate(name, raw, value, unit, sources, confidence, tuple(local_issues)))
        for name in {field.name for field in fields}:
            if sum(field.name == name for field in fields) > 1:
                issues.append("Campo repetido: " + name + "; varias operaciones o conflicto")
        by_name = {field.name: field for field in fields if sum(f.name == field.name for f in fields) == 1}
        market = _fold(str(by_name["market"].value)) if "market" in by_name else ""
        side = _fold(str(by_name["side"].value)) if "side" in by_name else ""
        kind = "unknown"
        if "bot_id" in by_name or "bot_profit" in by_name:
            kind = "bot_summary"
            issues.append("Resumen de bot: no duplicar con operaciones ni asumir beneficio realizado")
        elif "yield" in by_name:
            kind = "yield"
        elif any(term in market for term in ("futures", "future", "perpetual", "perpetuo", "derivado")):
            kind = "derivative"
        elif "spot" in market:
            kind = "spot_buy" if side in ("buy", "compra", "comprar") else (
                "spot_sell" if side in ("sell", "venta", "vender") else "spot")
        if kind == "unknown":
            issues.append("Tipo de operación no identificado por etiquetas explícitas")
        if "time" not in by_name:
            issues.append("Fecha/hora no visible")
        if not self.timezone:
            issues.append("Zona horaria pendiente; no usar ubicación del usuario como zona de plataforma")
        if not any(name in by_name for name in ("order_id", "trade_id", "transaction_id", "bot_id")):
            issues.append("Identificador de operación no visible")
        if "pnl_displayed" in by_name:
            issues.append("PnL genérico: no clasificar como realizado sin evidencia")
        if kind in ("spot_buy", "spot_sell", "spot", "derivative"):
            for name in ("pair", "quantity" if kind != "derivative" else "contracts"):
                if name not in by_name:
                    issues.append("Campo pendiente: " + name)
        status = _fold(str(by_name["status"].value)) if "status" in by_name else ""
        if status not in ("filled", "completed", "executed", "completada", "ejecutada"):
            issues.append("Estado de ejecución pendiente de comprobar")
        issues.append("Captura parcial: no acredita saldo total ni historial completo; revisión obligatoria")
        return CryptoOperationPreview(self.platform, self.account, evidence, kind,
                                      tuple(fields), tuple(issues), self.timezone)


class BingXImageReader(CryptoImageReader):
    def __init__(self, **kwargs):
        super().__init__("bingx", **kwargs)


class PionexImageReader(CryptoImageReader):
    def __init__(self, **kwargs):
        super().__init__("pionex", **kwargs)
