"""
Constantes y parámetros legales de Venezuela para el cálculo de nómina.
Los valores son configurables desde el modelo `ParametroNomina`.
"""

from decimal import Decimal


# ═══════════════════════════════════════════════════════════
#  VALORES POR DEFECTO (referencia 2026)
# ═══════════════════════════════════════════════════════════

VALORES_DEFECTO = {
    # Salarios y unidades
    "salario_minimo": Decimal("130.00"),         # Bolívares
    "cestaticket_mensual": Decimal("40.00"),     # En USD equivalente
    "unidad_tributaria": Decimal("43.00"),       # UT para ISLR

    # Tasas IVSS
    "ivss_obrero_pct": Decimal("0.04"),          # 4%
    "ivss_patronal_pct": Decimal("0.09"),        # 9%
    "ivss_tope_salarios": Decimal("5"),          # Tope: 5 salarios mínimos

    # Tasas Paro Forzoso (RPE)
    "rpe_obrero_pct": Decimal("0.005"),          # 0.5%
    "rpe_patronal_pct": Decimal("0.02"),         # 2%
    "rpe_tope_salarios": Decimal("10"),          # Tope: 10 salarios mínimos

    # Tasas BANAVIH (Vivienda)
    "banavih_obrero_pct": Decimal("0.01"),       # 1%
    "banavih_patronal_pct": Decimal("0.02"),     # 2%

    # INCES
    "inces_patronal_pct": Decimal("0.02"),       # 2%

    # LOPCYMAT (varía según categoría de riesgo)
    "lopcymat_min_pct": Decimal("0.0075"),       # 0.75%
    "lopcymat_max_pct": Decimal("0.10"),         # 10%

    # Prestaciones sociales
    "dias_prestaciones_trimestre": 15,
    "dias_prestaciones_anio": 30,
    "dias_adicionales_por_anio": 2,
    "tope_dias_adicionales": 30,

    # Utilidades
    "dias_utilidades_min": 30,
    "dias_utilidades_max": 120,

    # Vacaciones
    "dias_vacaciones_base": 15,
    "dias_vacaciones_max": 30,
    "dias_bono_vacacional_base": 15,
    "dias_bono_vacacional_max": 30,

    # Aguinaldo
    "dias_aguinaldo": 15,

    # Factor de integración salarial
    "factor_integracion": Decimal("1.0493"),
}


# ═══════════════════════════════════════════════════════════
#  TARIFA ISLR MENSUAL (Venezuela, referencia)
# ═══════════════════════════════════════════════════════════

TARIFA_ISLR_MENSUAL = [
    # (limite_inferior, limite_superior, sustraendo, porcentaje)
    (Decimal("0.00"),    Decimal("1000.00"),  Decimal("0.00"),      Decimal("0.00")),
    (Decimal("1000.01"), Decimal("1500.00"),  Decimal("0.00"),      Decimal("0.06")),
    (Decimal("1500.01"), Decimal("2000.00"),  Decimal("30.00"),     Decimal("0.09")),
    (Decimal("2000.01"), Decimal("2500.00"),  Decimal("75.00"),     Decimal("0.12")),
    (Decimal("2500.01"), Decimal("3000.00"),  Decimal("135.00"),    Decimal("0.16")),
    (Decimal("3000.01"), Decimal("4000.00"),  Decimal("175.00"),    Decimal("0.20")),
    (Decimal("4000.01"), Decimal("6000.00"),  Decimal("335.00"),    Decimal("0.24")),
    (Decimal("6000.01"), Decimal("8000.00"),  Decimal("815.00"),    Decimal("0.28")),
    (Decimal("8000.01"), Decimal("10000.00"), Decimal("1375.00"),   Decimal("0.32")),
    (Decimal("10000.01"), Decimal("9999999"), Decimal("2015.00"),   Decimal("0.34")),
]


# ═══════════════════════════════════════════════════════════
#  CATEGORÍAS DE RIESGO LOPCYMAT
# ═══════════════════════════════════════════════════════════

CATEGORIAS_RIESGO_LOPCYMAT = [
    ("I", "Riesgo mínimo", Decimal("0.0075")),   # 0.75%
    ("II", "Riesgo bajo", Decimal("0.015")),     # 1.5%
    ("III", "Riesgo medio", Decimal("0.03")),    # 3%
    ("IV", "Riesgo alto", Decimal("0.05")),      # 5%
    ("V", "Riesgo máximo", Decimal("0.10")),     # 10%
]