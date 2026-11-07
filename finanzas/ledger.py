"""Registro en memoria. Importación, persistencia y cálculo fiscal son fases posteriores."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from enum import Enum


class Kind(str, Enum):
    OPENING = "saldo_inicial"
    CONTRIBUTION = "aportacion"
    WITHDRAWAL = "retiro"
    INTEREST = "interes_cobrado"
    WITHHOLDING = "isr_retenido"
    FEE = "comision"
    FEE_REFUND = "devolucion_comision"
    VAT_RECEIVED = "iva_recibido"
    VAT_PAID = "iva_pagado"
    REWARD = "recompensa"
    DIVIDEND = "dividendo_cobrado"
    FOREIGN_WITHHOLDING = "retencion_extranjera"
    SECURITY_PROCEEDS = "cobro_valores_sin_desglose"


class Origin(str, Enum):
    EXTERNAL = "capital_externo"
    CASHBACK = "cashback"
    OWN_TRANSFER = "transferencia_propia"
    REINVESTMENT = "reinversion"
    UNKNOWN = "pendiente"


@dataclass(frozen=True)
class Evidence:
    document_id: str
    locator: str

    def __post_init__(self):
        if not self.document_id.strip() or not self.locator.strip():
            raise ValueError("Se requiere documento y localizador de evidencia")


@dataclass(frozen=True)
class Movement:
    id: str
    account: str
    unit: str
    effective_date: date
    kind: Kind
    amount: Decimal
    evidence: Evidence
    origin: Origin | None = None
    transfer_id: str | None = None

    def __post_init__(self):
        if not self.id.strip() or not self.account.strip() or not self.unit.strip():
            raise ValueError("Se requiere identificador, cuenta y unidad")
        if type(self.effective_date) is not date or not isinstance(self.evidence, Evidence):
            raise ValueError("Fecha efectiva y evidencia inválidas")
        if not isinstance(self.kind, Kind):
            raise ValueError("Tipo de movimiento inválido")
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise ValueError("Importe Decimal finito requerido; no usar float")
        if self.amount < 0 or (self.amount == 0 and self.kind not in (Kind.WITHHOLDING,Kind.FOREIGN_WITHHOLDING)):
            raise ValueError("Importe positivo; cero solo para retención documentada")
        if len(self.amount.as_tuple().digits) > 36 or not -30 <= self.amount.as_tuple().exponent <= 30:
            raise ValueError("Importe fuera de la precisión admitida")
        capital = self.kind in (Kind.CONTRIBUTION, Kind.WITHDRAWAL)
        if (capital and not isinstance(self.origin, Origin)) or (not capital and self.origin is not None):
            raise ValueError("Aportaciones y retiros requieren origen; los demás no")
        internal = self.origin in (Origin.OWN_TRANSFER, Origin.REINVESTMENT)
        if internal != bool(self.transfer_id):
            raise ValueError("Movimiento propio requiere vínculo; otros no lo admiten")
        if self.transfer_id is not None and not self.transfer_id.strip():
            raise ValueError("Vínculo vacío")

    @property
    def signed_amount(self):
        return self.amount.copy_negate() if self.kind in (Kind.WITHDRAWAL, Kind.WITHHOLDING, Kind.FOREIGN_WITHHOLDING, Kind.FEE, Kind.VAT_PAID) else self.amount


def _sum(values):
    values = tuple(values)
    if not values:
        return Decimal("0")
    # Precisión suficiente para todos los dígitos y los acarreos de la suma.
    places = max(v.adjusted() for v in values) - min(v.as_tuple().exponent for v in values) + 1
    with localcontext() as context:
        context.prec = max(28, places + len(str(len(values))) + 1)
        return sum(values, Decimal("0"))


class Ledger:
    def __init__(self):
        self._movements = {}

    @property
    def movements(self):
        return tuple(self._movements.values())

    def record(self, movement: Movement) -> bool:
        """False si el mismo ID y contenido ya existe; conflicto no sobrescribe."""
        if not isinstance(movement, Movement):
            raise ValueError("Se requiere un Movement validado")
        previous = self._movements.get(movement.id)
        if previous is not None:
            if previous != movement:
                raise ValueError("ID duplicado con contenido diferente")
            return False
        if any(m.account == movement.account and m.unit != movement.unit for m in self.movements):
            raise ValueError("Una cuenta del núcleo identifica una sola unidad")
        if movement.transfer_id:
            peers = [m for m in self.movements if m.transfer_id == movement.transfer_id]
            if len(peers) > 1:
                raise ValueError("Vínculo ya conciliado")
            if peers:
                peer = peers[0]
                if (peer.account == movement.account or peer.unit != movement.unit
                    or peer.amount != movement.amount or peer.kind == movement.kind
                    or peer.origin != movement.origin):
                    raise ValueError("Contrapartida incompatible; se conserva como pendiente")
        self._movements[movement.id] = movement
        return True

    def balances(self, through: date | None = None):
        """Saldo registrado por cuenta y unidad, no certifica historia completa."""
        selected = [m for m in self.movements if through is None or m.effective_date <= through]
        keys = sorted({(m.account, m.unit) for m in selected})
        return {key: _sum(m.signed_amount for m in selected if (m.account, m.unit) == key)
                for key in keys}

    def external_contributions(self, unit: str):
        """Aportes acreditados como externos/cashback, sin saldos iniciales ni traspasos."""
        return _sum(m.amount for m in self.movements
                    if m.unit == unit and m.kind == Kind.CONTRIBUTION
                    and m.origin in (Origin.EXTERNAL, Origin.CASHBACK))

    def pending_origins(self):
        return tuple(m.id for m in self.movements if m.origin == Origin.UNKNOWN)

    def pending_transfers(self):
        ids = {m.transfer_id for m in self.movements if m.transfer_id}
        return tuple(sorted(i for i in ids if sum(m.transfer_id == i for m in self.movements) == 1))

    def interest_received(self, unit: str):
        return _sum(m.amount for m in self.movements if m.unit == unit and m.kind == Kind.INTEREST)

    def withholding_recorded(self, unit: str):
        """None: no hay retención documentada. Cero: documento explícito con cero."""
        values = [m.amount for m in self.movements if m.unit == unit and m.kind == Kind.WITHHOLDING]
        return _sum(values) if values else None
