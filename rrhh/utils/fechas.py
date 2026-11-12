"""
Utilidades de fechas para documentos formales.
Acepta date, datetime o strings ISO.
"""

from datetime import date, datetime


MESES_ES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE",
}

MESES_ES_TITULO = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def _to_date(valor):
    """
    Normaliza cualquier valor a `date`:
    - `datetime` → `.date()`
    - `date` → tal cual
    - `str` ISO → `date.fromisoformat()`
    - otros → None
    """
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor)
        except (ValueError, TypeError):
            return None
    return None


def mes_en_letras(mes_numero, mayusculas=True):
    """Convierte un número de mes (1-12) a su nombre en español."""
    if mayusculas:
        return MESES_ES.get(mes_numero, "")
    return MESES_ES_TITULO.get(mes_numero, "")


def fecha_larga(fecha):
    """
    Devuelve una fecha en formato largo: "15 de Octubre de 2026".
    Acepta date, datetime o string ISO.
    """
    fecha = _to_date(fecha)
    if not fecha:
        return ""
    return f"{fecha.day} de {MESES_ES_TITULO[fecha.month]} de {fecha.year}"


def fecha_corta(fecha):
    """Formato dd/mm/yyyy. Acepta date, datetime o string ISO."""
    fecha = _to_date(fecha)
    if not fecha:
        return ""
    return fecha.strftime("%d/%m/%Y")