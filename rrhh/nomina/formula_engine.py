"""
Motor de evaluación de fórmulas de conceptos de nómina.

Permite que los conceptos tengan una fórmula configurable desde el admin.
Si la fórmula está vacía, se usa la lógica interna del motor (hardcoded).
"""
from decimal import Decimal, ROUND_HALF_UP


# ═══════════════════════════════════════════════════════════
#  WHITELIST DE FUNCIONES Y VARIABLES
# ═══════════════════════════════════════════════════════════

FUNCIONES_PERMITIDAS = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "int": int,
    "float": float,
    "Decimal": Decimal,
    "sum": sum,
}

VARIABLES_PERMITIDAS = {
    # Salario
    "salario_base",
    "salario_diario",
    "salario_mensual",
    "salario_normal",
    "salario_integral",
    "sueldo_periodo",
    "sueldo_descontado",
    "factor_periodo",
    # Periodo
    "dias_periodo",
    "dias_trabajados",
    "dias_faltas",
    "dias_vacaciones",
    "dias_incapacidad",
    # Horas
    "horas_extra_diurnas",
    "horas_extra_nocturnas",
    "horas_nocturnas",
    "valor_hora",
    # Parámetros
    "salario_minimo",
    "unidad_tributaria",
    "tasa_bcv_usd",
    "cestaticket_mensual_usd",
    # Bases previas
    "total_percepciones_previas",
    "total_gravado_previo",
    "base_ivss",
    "base_rpe",
    "base_banavih",
    "base_islr",
    # Constantes
    "DIA",
    "MES",
    "ANIO",
    "CERO",
    "UNO",
}


def r2(valor):
    """Redondea a 2 decimales."""
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ═══════════════════════════════════════════════════════════
#  VALIDACIÓN DE SEGURIDAD
# ═══════════════════════════════════════════════════════════

PALABRAS_PROHIBIDAS = [
    "__", "import", "exec", "eval", "open", "compile",
    "globals", "locals", "vars", "getattr", "setattr",
    "delattr", "input", "os.", "sys.", "subprocess",
    "shutil", "pickle", "shelve", "socket", "urllib",
    "requests", "builtins", "class ", "def ",
]


def validar_formula(formula):
    """
    Valida que una fórmula sea segura antes de evaluarla.

    Returns:
        (es_valida, mensaje_error)
    """
    if not formula:
        return True, None

    formula_lower = formula.lower()

    for palabra in PALABRAS_PROHIBIDAS:
        if palabra in formula_lower:
            return False, f"Contiene código no permitido: '{palabra}'"

    return True, None


# ═══════════════════════════════════════════════════════════
#  CONSTRUCCIÓN DEL CONTEXTO
# ═══════════════════════════════════════════════════════════

def construir_contexto(empleado, periodo, parametros, extras=None):
    """
    Construye el diccionario de variables disponibles para las fórmulas.

    Args:
        empleado: instancia de Empleado
        periodo: instancia de PeriodoNomina
        parametros: instancia de ParametroNomina
        extras: dict con variables adicionales (opcional)

    Returns:
        dict con las variables disponibles
    """
    salario_mensual = Decimal(str(empleado.salario_base or 0))
    salario_diario = salario_mensual / Decimal("30")
    dias_periodo = periodo.dias_periodo
    factor_periodo = Decimal(str(dias_periodo)) / Decimal("30")

    sueldo_periodo = salario_mensual * factor_periodo
    valor_hora = salario_diario / Decimal("8")

    contexto = {
        # ─── Salario ──────────────────────────────────
        "salario_base": salario_mensual,
        "salario_mensual": salario_mensual,
        "salario_diario": salario_diario,
        "salario_normal": salario_mensual,
        "salario_integral": salario_mensual,
        "sueldo_periodo": sueldo_periodo,
        "sueldo_descontado": sueldo_periodo,
        "factor_periodo": factor_periodo,

        # ─── Periodo ──────────────────────────────────
        "dias_periodo": Decimal(str(dias_periodo)),
        "dias_trabajados": Decimal(str(dias_periodo)),
        "dias_faltas": Decimal("0"),
        "dias_vacaciones": Decimal("0"),
        "dias_incapacidad": Decimal("0"),

        # ─── Horas ────────────────────────────────────
        "horas_extra_diurnas": Decimal("0"),
        "horas_extra_nocturnas": Decimal("0"),
        "horas_nocturnas": Decimal("0"),
        "valor_hora": valor_hora,

        # ─── Parámetros ───────────────────────────────
        "salario_minimo": Decimal(str(parametros.salario_minimo or 0)),
        "unidad_tributaria": Decimal(str(parametros.unidad_tributaria or 0)),
        "tasa_bcv_usd": Decimal(str(parametros.tasa_bcv_usd or 1)),
        "cestaticket_mensual_usd": Decimal(
            str(parametros.cestaticket_mensual_usd or 0)
        ),

        # ─── Bases previas (se llenan al avanzar) ─────
        "total_percepciones_previas": Decimal("0"),
        "total_gravado_previo": Decimal("0"),
        "base_ivss": Decimal("0"),
        "base_rpe": Decimal("0"),
        "base_banavih": Decimal("0"),
        "base_islr": Decimal("0"),

        # ─── Constantes útiles ────────────────────────
        "DIA": Decimal("1"),
        "MES": Decimal("30"),
        "ANIO": Decimal("360"),
        "CERO": Decimal("0"),
        "UNO": Decimal("1"),
    }

    if extras:
        contexto.update(extras)

    return contexto


# ═══════════════════════════════════════════════════════════
#  EVALUACIÓN
# ═══════════════════════════════════════════════════════════

def evaluar_formula(formula, contexto):
    """
    Evalúa una fórmula con el contexto dado.

    Args:
        formula: string con la expresión
        contexto: dict con variables

    Returns:
        (valor: Decimal | None, error: str | None)
    """
    if not formula or not formula.strip():
        return None, "Fórmula vacía"

    # Validar seguridad
    es_valida, error = validar_formula(formula)
    if not es_valida:
        return None, error

    # Filtrar contexto a solo variables permitidas
    contexto_filtrado = {
        k: v for k, v in contexto.items()
        if k in VARIABLES_PERMITIDAS
    }

    # Agregar funciones permitidas
    contexto_filtrado.update(FUNCIONES_PERMITIDAS)

    try:
        # Bloquear builtins para seguridad
        resultado = eval(
            formula,
            {"__builtins__": {}},
            contexto_filtrado,
        )

        # Convertir a Decimal
        if isinstance(resultado, bool):
            resultado = Decimal("1") if resultado else Decimal("0")
        elif not isinstance(resultado, Decimal):
            resultado = Decimal(str(resultado))

        return r2(resultado), None

    except NameError as e:
        return None, f"Variable no definida: {e}"
    except ZeroDivisionError:
        return None, "División entre cero"
    except SyntaxError as e:
        return None, f"Error de sintaxis: {e}"
    except TypeError as e:
        return None, f"Error de tipo: {e}"
    except Exception as e:
        return None, f"Error al evaluar: {e}"


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def probar_formula(formula, contexto_ejemplo=None):
    """
    Función auxiliar para probar una fórmula con datos de ejemplo.

    Uso desde el shell:
        from rrhh.nomina.formula_engine import probar_formula
        probar_formula("salario_base * 0.10")
    """
    if contexto_ejemplo is None:
        contexto_ejemplo = {
            "salario_base": Decimal("15000"),
            "salario_diario": Decimal("500"),
            "dias_periodo": Decimal("15"),
            "dias_trabajados": Decimal("15"),
            "dias_faltas": Decimal("0"),
            "factor_periodo": Decimal("0.5"),
            "sueldo_periodo": Decimal("7500"),
            "sueldo_descontado": Decimal("7500"),
            "salario_minimo": Decimal("130"),
            "unidad_tributaria": Decimal("43"),
            "tasa_bcv_usd": Decimal("36.50"),
            "cestaticket_mensual_usd": Decimal("40"),
            "horas_extra_diurnas": Decimal("0"),
            "horas_extra_nocturnas": Decimal("0"),
            "horas_nocturnas": Decimal("0"),
            "valor_hora": Decimal("62.50"),
            "DIA": Decimal("1"),
            "MES": Decimal("30"),
            "ANIO": Decimal("360"),
            "CERO": Decimal("0"),
            "UNO": Decimal("1"),
        }

    valor, error = evaluar_formula(formula, contexto_ejemplo)

    if error:
        print(f"❌ Error: {error}")
        return None

    print(f"✅ Resultado: {valor}")
    return valor