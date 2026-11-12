"""
Constantes del módulo de ausencias y vacaciones (LOTTT).
"""
from decimal import Decimal

# ═══════════════════════════════════════════════════════════
#  VACACIONES — LOTTT Art. 190 y 192
# ═══════════════════════════════════════════════════════════

DIAS_BASE_VACACIONES = 15
DIAS_BASE_BONO_VACACIONAL = 15
DIAS_MAX_VACACIONES = 30
DIAS_MAX_BONO_VACACIONAL = 30
INCREMENTO_ANUAL = 1

# ═══════════════════════════════════════════════════════════
#  VACACIONES COLECTIVAS — LOTTT Art. 191
# ═══════════════════════════════════════════════════════════

DIAS_COLECTIVOS_MAX = 15

# ═══════════════════════════════════════════════════════════
#  VENCIMIENTO — LOTTT Art. 192
# ═══════════════════════════════════════════════════════════

MESES_VENCIMIENTO_DEFAULT = 12

# ═══════════════════════════════════════════════════════════
#  FRACCIONAMIENTO
# ═══════════════════════════════════════════════════════════

MESES_PARA_FRACCION_VACACIONES = 1  # Fracción > 1 mes cuenta

# ═══════════════════════════════════════════════════════════
#  OPCIONES
# ═══════════════════════════════════════════════════════════

MESES_ES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Ago",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

MESES_ES_COMPLETO = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}