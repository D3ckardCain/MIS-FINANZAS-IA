"""OCR local de imágenes: evidencia revisable, sin contabilización automática."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import BytesIO, StringIO
import csv
import re
import shutil
import subprocess
import warnings


class ImageReadError(ValueError):
    pass


@dataclass(frozen=True)
class OcrLine:
    id: str
    text: str
    confidence: Decimal
    box: tuple[int, int, int, int]


@dataclass(frozen=True)
class ImageEvidence:
    document_id: str
    original_size: tuple[int, int]
    working_size: tuple[int, int]
    orientation_applied: bool
    image_format: str
    languages: str
    lines: tuple[OcrLine, ...]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class StatementImagePreview:
    institution: str
    lane: str
    evidence: ImageEvidence
    identity_detected: bool
    document_preview: object | None
    issues: tuple[str, ...]

    @property
    def ready_to_import(self):
        return False


def parse_tsv(text, document, *, threshold=Decimal("85")):
    groups = {}
    required = {"level", "page_num", "block_num", "par_num", "line_num",
                "left", "top", "width", "height", "conf", "text"}
    reader = csv.DictReader(StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE)
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ImageReadError("Salida OCR inválida")
    for row in reader:
        if row["level"] != "5" or not (row["text"] or "").strip():
            continue
        try:
            confidence = Decimal(row["conf"])
            box = tuple(int(row[k]) for k in ("left", "top", "width", "height"))
            if not confidence.is_finite() or not 0 <= confidence <= 100 or min(box) < 0:
                raise ValueError
        except (ValueError, TypeError, InvalidOperation):
            raise ImageReadError("Confianza o coordenadas OCR inválidas")
        key = tuple(row[k] for k in ("page_num", "block_num", "par_num", "line_num"))
        groups.setdefault(key, []).append((row["text"], confidence, box))
    lines, issues = [], []
    for key, words in groups.items():
        left = min(w[2][0] for w in words)
        top = min(w[2][1] for w in words)
        right = max(w[2][0] + w[2][2] for w in words)
        bottom = max(w[2][1] + w[2][3] for w in words)
        identifier = sha256((document + ":" + ":".join(key)).encode()).hexdigest()
        confidence = min(word[1] for word in words)
        lines.append(OcrLine(identifier, " ".join(w[0] for w in words), confidence,
                             (left, top, right - left, bottom - top)))
        if confidence < threshold:
            issues.append("Baja confianza OCR: " + identifier)
    if not lines:
        issues.append("No se reconoció texto; no equivale a un documento vacío")
    return tuple(lines), tuple(issues)


class LocalOcr:
    def __init__(self, *, languages=None, threshold=Decimal("85"), psm=6, timeout=45):
        threshold = Decimal(str(threshold))
        if not threshold.is_finite() or not 0 <= threshold <= 100:
            raise ValueError("Umbral OCR no admitido")
        if psm not in (3, 6, 11) or not 1 <= timeout <= 45:
            raise ValueError("Configuración OCR no admitida")
        self.languages, self.threshold, self.psm, self.timeout = languages, threshold, psm, timeout

    def _languages(self):
        if not shutil.which("tesseract"):
            raise ImageReadError("Falta Tesseract local; consultar docs/IMAGENES.md")
        try:
            result = subprocess.run(["tesseract", "--list-langs"], capture_output=True,
                                    text=True, timeout=self.timeout, check=False)
        except (subprocess.TimeoutExpired, OSError) as error:
            raise ImageReadError("No fue posible consultar idiomas OCR") from error
        if result.returncode != 0:
            raise ImageReadError("No fue posible consultar idiomas OCR")
        available = {line.strip() for line in result.stdout.splitlines()}
        requested = self.languages or ("spa+eng" if {"spa", "eng"} <= available else "eng")
        if not requested or any(language not in available for language in requested.split("+")):
            raise ImageReadError("Idioma OCR solicitado no instalado")
        return requested, (() if "spa" in requested.split("+") else
                           ("OCR sin modelo español: revisar acentos y etiquetas en español",))

    def read(self, content: bytes):
        if not isinstance(content, bytes) or not content:
            raise ImageReadError("Se requieren los bytes de una imagen")
        try:
            from PIL import Image, ImageOps, UnidentifiedImageError
        except ImportError as error:
            raise ImageReadError("Falta Pillow: instalar requirements-image.txt") from error
        identifier = sha256(content).hexdigest()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as source:
                    if source.format not in ("PNG", "JPEG", "WEBP", "TIFF", "BMP"):
                        raise ImageReadError("Formato de imagen no admitido")
                    if getattr(source, "n_frames", 1) != 1:
                        raise ImageReadError("Archivo con varias imágenes: separar sus páginas")
                    if source.width * source.height > 30_000_000:
                        raise ImageReadError("Imagen demasiado grande para este lector local")
                    original, image_format = source.size, source.format
                    oriented = source.getexif().get(274, 1) not in (None, 1)
                    working = ImageOps.exif_transpose(source).convert("RGBA")
                    white = Image.new("RGBA", working.size, "white")
                    white.alpha_composite(working)
                    buffer = BytesIO()
                    white.convert("RGB").save(buffer, format="PNG")
                    normalized, working_size = buffer.getvalue(), working.size
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
                Image.DecompressionBombWarning) as error:
            raise ImageReadError("Imagen no legible") from error
        languages, issues = self._languages()
        try:
            result = subprocess.run(
                ["tesseract", "stdin", "stdout", "-l", languages, "--psm", str(self.psm), "tsv"],
                input=normalized, capture_output=True, timeout=self.timeout, check=False)
        except (subprocess.TimeoutExpired, OSError) as error:
            raise ImageReadError("OCR no disponible o agotó el tiempo; sin movimientos") from error
        if result.returncode != 0:
            raise ImageReadError("Tesseract no pudo leer la imagen")
        try:
            tsv = result.stdout.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ImageReadError("Salida OCR no legible") from error
        lines, quality = parse_tsv(tsv, identifier, threshold=self.threshold)
        return ImageEvidence(identifier, original, working_size, oriented, image_format,
                             languages, lines, issues + quality)


def read_statement_image(content, institution, lane, *, engine=None):
    from .readers import reader_for, _BY_KEY, fold
    reader = reader_for(institution, lane)
    evidence = (engine or LocalOcr()).read(content)
    text = "\n".join(line.text for line in evidence.lines)
    detected = bool(re.search(_BY_KEY[institution].identity, fold(text)))
    issues, preview = list(evidence.issues), None
    if not detected:
        issues.append("Identidad institucional no visible o no reconocida; confirmar selección")
    elif institution == "openbank":
        issues.append("Imagen Openbank: revisar columnas; no hereda la conciliación del PDF")
    else:
        try:
            preview = reader.read_pages([text], evidence.document_id)
        except ValueError:
            issues.append("Texto OCR incompatible con el perfil; revisar contra la imagen")
    issues.append("Revisar importes, signos, fechas y campos faltantes; OCR no autoriza importación")
    return StatementImagePreview(institution, lane, evidence, detected, preview, tuple(issues))
