"""
Constantes del módulo de prestaciones sociales (LOTTT).
"""
from decimal import Decimal


# ═══════════════════════════════════════════════════════════
#  LITERAL a) — GARANTÍA
# ═══════════════════════════════════════════════════════════

DIAS_GARANTIA_POR_TRIMESTRE = Decimal("15")
TRIMESTRES_POR_ANIO = 4


# ═══════════════════════════════════════════════════════════
#  LITERAL b) — DÍAS ADICIONALES
# ═══════════════════════════════════════════════════════════

DIAS_ADICIONALES_POR_ANIO = Decimal("2")
DIAS_ADICIONALES_TOPE = Decimal("30")  # Tope acumulativo


# ═══════════════════════════════════════════════════════════
#  LITERAL c) — RETROACTIVO
# ═══════════════════════════════════════════════════════════

DIAS_RETROACTIVO_POR_ANIO = Decimal("30")
MESES_PARA_FRACCION = 6  # Fracción > 6 meses cuenta como año


# ═══════════════════════════════════════════════════════════
#  OPCIONES DE MODELOS
# ═══════════════════════════════════════════════════════════

MODOS_CALCULO = [
    ("garantia", "Solo Garantía (Art. 142.a + 142.b)"),
    ("retroactivo", "Solo Retroactivo (Art. 142.c)"),
    ("auto", "Auto: el mayor de los dos (Art. 142.d)"),
]

FRECUENCIAS_DEPOSITO = [
    ("trimestral", "Trimestral (LOTTT)"),
    ("mensual", "Mensual"),
    ("anual", "Anual"),
]

TIPOS_ACREDITACION = [
    ("fideicomiso", "Fideicomiso bancario"),
    ("cuenta_aparte", "Cuenta aparte de la empresa"),
    ("autoadministrado", "Autoadministrado (sin depósito externo)"),
]

FUENTES_TASA = [
    ("manual", "Manual"),
    ("api_bcv", "API BCV"),
    ("otra", "Otra fuente"),
]

MONEDAS = [
    ("VES", "Bolívares"),
    ("USD", "Dólares"),
]