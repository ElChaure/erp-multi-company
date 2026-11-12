"""
Utilidades numéricas: conversión de números a letras, formateo de montos.
"""

# ═══════════════════════════════════════════════════════════
#  NÚMERO A LETRAS
# ═══════════════════════════════════════════════════════════

UNIDADES = [
    "", "UN", "DOS", "TRES", "CUATRO", "CINCO",
    "SEIS", "SIETE", "OCHO", "NUEVE", "DIEZ",
    "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE",
    "DIECISÉIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE",
    "VEINTE",
]

DECENAS = [
    "", "", "VEINTE", "TREINTA", "CUARENTA",
    "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA",
]

CENTENAS = [
    "", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS",
    "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS",
    "NOVECIENTOS",
]


def _decenas_a_letras(n):
    if n <= 20:
        return UNIDADES[n]
    elif n < 30:
        return "VEINTI" + UNIDADES[n - 20].lower()
    else:
        dec = n // 10
        uni = n % 10
        return DECENAS[dec] + (" Y " + UNIDADES[uni] if uni > 0 else "")


def _centenas_a_letras(n):
    if n == 100:
        return "CIEN"
    cen = n // 100
    resto = n % 100
    partes = []
    if cen > 0:
        partes.append(CENTENAS[cen])
    if resto > 0:
        partes.append(_decenas_a_letras(resto))
    return " ".join(partes)


def _miles_a_letras(n):
    if n < 1000:
        return _centenas_a_letras(n)
    miles = n // 1000
    resto = n % 1000
    partes = []
    if miles == 1:
        partes.append("MIL")
    else:
        partes.append(_centenas_a_letras(miles) + " MIL")
    if resto > 0:
        partes.append(_centenas_a_letras(resto))
    return " ".join(partes)


def _millones_a_letras(n):
    if n < 1_000_000:
        return _miles_a_letras(n)
    millones = n // 1_000_000
    resto = n % 1_000_000
    partes = []
    if millones == 1:
        partes.append("UN MILLÓN")
    else:
        partes.append(_miles_a_letras(millones) + " MILLONES")
    if resto > 0:
        partes.append(_miles_a_letras(resto))
    return " ".join(partes)


def numero_a_letras(monto, moneda="BOLÍVARES"):
    """
    Convierte un número a su representación en letras.

    Ejemplo:
        15234.56 → "QUINCE MIL DOSCIENTOS TREINTA Y CUATRO BOLÍVARES CON 56/100"
    """
    if monto < 0:
        return "MONTO NEGATIVO"

    entero = int(monto)
    decimales = round((monto - entero) * 100)

    letras = _millones_a_letras(entero)
    if not letras:
        letras = "CERO"

    return f"{letras} {moneda} CON {decimales:02d}/100"


def formatear_monto(monto, simbolo="Bs.", decimales=2):
    """Formatea un monto con separador de miles y símbolo."""
    if monto is None:
        return "—"
    try:
        return f"{simbolo} {float(monto):,.{decimales}f}"
    except (ValueError, TypeError):
        return str(monto)


def formatear_numero(valor, decimales=2):
    """Formatea un número sin símbolo."""
    if valor is None:
        return "—"
    try:
        return f"{float(valor):,.{decimales}f}"
    except (ValueError, TypeError):
        return str(valor)