import re

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_PHONE_ALLOWED_RE = re.compile(r"^[\d\s()+\-]+$")


def clean_required_text(value: str, *, field_name: str, min_length: int = 1, max_length: int = 200) -> str:
    stripped = (value or "").strip()
    if _CONTROL_CHARS_RE.search(stripped):
        raise ValueError(f"{field_name} contiene caracteres no permitidos")
    if len(stripped) < min_length:
        raise ValueError(f"{field_name} no puede estar vacío")
    if len(stripped) > max_length:
        raise ValueError(f"{field_name} no puede superar los {max_length} caracteres")
    return stripped


def clean_optional_text(value: str | None, *, max_length: int = 300) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if _CONTROL_CHARS_RE.search(stripped):
        raise ValueError("Contiene caracteres no permitidos")
    if len(stripped) > max_length:
        raise ValueError(f"No puede superar los {max_length} caracteres")
    return stripped


def validate_cuit(value: str | None) -> str | None:
    """CUIT/CUIL: no es obligatorio (no hay requisito documentado que lo exija),
    pero si se carga uno debe tener 11 dígitos. Se preserva el formato original
    (con o sin guiones) tal como ya lo hace el resto del sistema."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > 20:
        raise ValueError("CUIT/CUIL demasiado largo")
    digits = re.sub(r"\D", "", stripped)
    if len(digits) != 11:
        raise ValueError("CUIT/CUIL debe tener 11 dígitos (ej: 20-12345678-9)")
    return stripped


def validate_phone(value: str | None) -> str | None:
    """Teléfono: no es obligatorio y no se impone un formato internacional
    rígido. Solo se rechazan valores claramente inválidos (letras, muy cortos)."""
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > 30:
        raise ValueError("Teléfono demasiado largo")
    if not _PHONE_ALLOWED_RE.match(stripped):
        raise ValueError("Teléfono contiene caracteres no permitidos")
    digits = re.sub(r"\D", "", stripped)
    if len(digits) < 6:
        raise ValueError("Teléfono debe tener al menos 6 dígitos")
    return stripped
