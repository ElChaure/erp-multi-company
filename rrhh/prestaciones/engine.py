"""
Motor de cálculo de prestaciones sociales (Art. 142 LOTTT).

Implementa:
    - Literal a): Garantía trimestral (15 días por trimestre)
    - Literal b): Días adicionales (2 días por año, hasta 30)
    - Literal c): Retroactivo (30 días por año o fracción > 6 meses)
    - Literal d): Comparación → se paga el mayor

Referencias:
    - LOTTT Art. 142 y 143
    - Sentencia TSJ N° 306 (26/07/2024, Ponencia Conjunta)
"""
from datetime import date, timedelta
from decimal import Decimal

from rrhh.nomina.utils import (
    r2,
    calcular_salario_diario,
    calcular_anios_antiguedad,
    calcular_meses_completos,
    calcular_factor_integracion,
)
from rrhh.models import (
    Empleado,
    ParametroNomina,
    NominaEmpleado,
)

from .constants import (
    DIAS_GARANTIA_POR_TRIMESTRE,
    DIAS_ADICIONALES_POR_ANIO,
    DIAS_ADICIONALES_TOPE,
    DIAS_RETROACTIVO_POR_ANIO,
    MESES_PARA_FRACCION,
)


# ═══════════════════════════════════════════════════════════
#  SALARIO INTEGRAL
# ═══════════════════════════════════════════════════════════

def calcular_salario_integral_diario(empleado, parametros=None, fecha=None):
    """
    Calcula el salario integral diario del empleado.

    Fórmula:
        salario_integral = salario_normal + alícuota_utilidades + alícuota_bono_vac

    Donde:
        - alícuota_utilidades = (salario_diario × días_utilidades) / 360
        - alícuota_bono_vac = (salario_diario × días_bono_vac) / 360

    Args:
        empleado: instancia de Empleado
        parametros: instancia de ParametroNomina (si None, se busca)
        fecha: fecha de referencia (default hoy)

    Returns:
        dict con:
            - salario_diario
            - alicuota_utilidades
            - alicuota_bono_vacacional
            - salario_integral_diario
    """
    if fecha is None:
        fecha = date.today()

    if parametros is None:
        parametros = ParametroNomina.objects.filter(
            empresa=empleado.empresa,
            anio=fecha.year,
            activo=True,
        ).first()

    # Salario diario (base)
    salario_mensual = Decimal(str(empleado.salario_base))
    salario_diario = calcular_salario_diario(salario_mensual)

    # Días de utilidades (según LOTTT: entre 30 y 120)
    dias_utilidades = Decimal(str(
        parametros.dias_utilidades_min if parametros else 30
    ))

    # Días de bono vacacional (según antigüedad)
    # NUEVO
    from rrhh.ausencias.vacaciones_engine import calcular_dias_bono_vacacional
    from rrhh.models import ConfiguracionVacaciones

    anios = calcular_anios_antiguedad(empleado.fecha_ingreso, fecha)

    # Obtener configuración de vacaciones de la empresa (soporta CC)
    config_vac = ConfiguracionVacaciones.objects.filter(
        empresa=empleado.empresa,
    ).first()

    dias_bono_vac = Decimal(str(
        calcular_dias_bono_vacacional(anios, config_vac)
    ))

    # Alícuotas
    alicuota_utilidades = r2(
        (salario_diario * dias_utilidades) / Decimal("360")
    )
    alicuota_bono_vac = r2(
        (salario_diario * dias_bono_vac) / Decimal("360")
    )

    salario_integral = r2(
        salario_diario + alicuota_utilidades + alicuota_bono_vac
    )

    return {
        "salario_diario": salario_diario,
        "dias_utilidades": dias_utilidades,
        "alicuota_utilidades": alicuota_utilidades,
        "dias_bono_vacacional": dias_bono_vac,
        "alicuota_bono_vacacional": alicuota_bono_vac,
        "salario_integral_diario": salario_integral,
    }


# ═══════════════════════════════════════════════════════════
#  TRIMESTRES
# ═══════════════════════════════════════════════════════════

def rango_trimestre(anio, trimestre):
    """
    Devuelve (fecha_inicio, fecha_fin) de un trimestre.

    T1: 01/01 - 31/03
    T2: 01/04 - 30/06
    T3: 01/07 - 30/09
    T4: 01/10 - 31/12
    """
    if trimestre not in (1, 2, 3, 4):
        raise ValueError("Trimestre debe ser 1, 2, 3 o 4.")

    rangos = {
        1: (date(anio, 1, 1), date(anio, 3, 31)),
        2: (date(anio, 4, 1), date(anio, 6, 30)),
        3: (date(anio, 7, 1), date(anio, 9, 30)),
        4: (date(anio, 10, 1), date(anio, 12, 31)),
    }
    return rangos[trimestre]


def dias_adicionales_acumulados(anios_servicio):
    """
    Calcula los días adicionales del literal b) según antigüedad.

    Regla:
        - A partir del 2° año: 2 días por año.
        - Acumulativos hasta un tope de 30 días.

    Returns:
        Decimal con los días acumulados.
    """
    if anios_servicio < 2:
        return Decimal("0")

    dias = Decimal(str((anios_servicio - 1))) * DIAS_ADICIONALES_POR_ANIO
    return min(dias, DIAS_ADICIONALES_TOPE)


# ═══════════════════════════════════════════════════════════
#  LITERAL a) + b) — GARANTÍA
# ═══════════════════════════════════════════════════════════

def calcular_garantia_trimestre(empleado, anio, trimestre, parametros=None):
    """
    Calcula el monto del depósito correspondiente a un trimestre.

    Fórmula:
        monto = (dias_garantia + dias_adicionales) × salario_integral_diario

    Args:
        empleado: instancia de Empleado
        anio: año (int)
        trimestre: 1-4
        parametros: instancia de ParametroNomina (opcional)

    Returns:
        dict con:
            - anio, trimestre
            - fecha_inicio, fecha_fin
            - dias_garantia (15)
            - dias_adicionales (2 × año, hasta 30)
            - salario_integral_diario
            - monto_ves
    """
    fecha_inicio, fecha_fin = rango_trimestre(anio, trimestre)

    # Solo si el empleado estaba activo en el rango
    if empleado.fecha_ingreso > fecha_fin:
        return None

    if empleado.fecha_egreso and empleado.fecha_egreso < fecha_inicio:
        return None

    # Anios de servicio al final del trimestre
    anios = calcular_anios_antiguedad(empleado.fecha_ingreso, fecha_fin)

    # Salario integral (al último día del trimestre)
    sal = calcular_salario_integral_diario(empleado, parametros, fecha_fin)

    # Días
    dias_garantia = DIAS_GARANTIA_POR_TRIMESTRE
    dias_adicionales = dias_adicionales_acumulados(anios)

    # Monto
    dias_totales = dias_garantia + dias_adicionales
    monto_ves = r2(dias_totales * sal["salario_integral_diario"])

    return {
        "anio": anio,
        "trimestre": trimestre,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "anios_servicio": anios,
        "dias_garantia": dias_garantia,
        "dias_adicionales": dias_adicionales,
        "dias_totales": dias_totales,
        "salario_integral_diario": sal["salario_integral_diario"],
        "detalle_salario": sal,
        "monto_ves": monto_ves,
    }


def calcular_garantia_acumulada(empleado, fecha_corte=None, parametros=None):
    """
    Calcula la garantía acumulada desde el inicio hasta la fecha de corte.

    Itera por todos los trimestres desde la fecha de ingreso.

    Args:
        empleado: instancia de Empleado
        fecha_corte: fecha hasta la cual calcular (default hoy)
        parametros: instancia de ParametroNomina (opcional)

    Returns:
        dict con:
            - trimestres: lista de dicts (uno por trimestre)
            - total_dias: suma de días
            - total_ves: monto total
    """
    if fecha_corte is None:
        fecha_corte = date.today()

    inicio = empleado.fecha_ingreso
    # Ajustar: si el ingreso fue a mitad de trimestre, solo se cuenta desde el siguiente
    anio = inicio.year
    trimestre = ((inicio.month - 1) // 3) + 1

    trimestres = []
    total_dias = Decimal("0")
    total_ves = Decimal("0")

    # Iterar hasta cubrir la fecha_corte
    while True:
        fecha_inicio, fecha_fin = rango_trimestre(anio, trimestre)
        if fecha_inicio > fecha_corte:
            break

        resultado = calcular_garantia_trimestre(
            empleado, anio, trimestre, parametros
        )

        if resultado:
            # Prorratear si el trimestre no está completo
            if fecha_inicio < empleado.fecha_ingreso:
                # El primer trimestre: prorratear según días trabajados
                dias_trabajados = (fecha_fin - empleado.fecha_ingreso).days + 1
                dias_trimestre = (fecha_fin - fecha_inicio).days + 1
                factor = Decimal(str(dias_trabajados)) / Decimal(str(dias_trimestre))
                resultado["monto_ves"] = r2(resultado["monto_ves"] * factor)
                resultado["prorrateado"] = True
                resultado["factor"] = factor

            trimestres.append(resultado)
            total_dias += resultado["dias_totales"]
            total_ves += resultado["monto_ves"]

        # Avanzar al siguiente trimestre
        trimestre += 1
        if trimestre > 4:
            trimestre = 1
            anio += 1

    return {
        "trimestres": trimestres,
        "total_dias": total_dias,
        "total_ves": r2(total_ves),
    }


# ═══════════════════════════════════════════════════════════
#  LITERAL c) — RETROACTIVO
# ═══════════════════════════════════════════════════════════

def calcular_retroactivo(empleado, fecha_corte=None, parametros=None):
    """
    Calcula el monto retroactivo del Art. 142.c.

    Fórmula:
        30 días × años de servicio × último salario integral diario
        + (fracción > 6 meses cuenta como año)

    Args:
        empleado: instancia de Empleado
        fecha_corte: fecha hasta la cual calcular (default hoy)
        parametros: instancia de ParametroNomina (opcional)

    Returns:
        dict con:
            - anios_servicio
            - meses_fraccion
            - fraccion_cuenta_como_anio (bool)
            - anios_para_calculo (anios + 1 si fracción > 6m)
            - dias_retroactivo (30 × anios_para_calculo)
            - salario_integral_diario
            - monto_ves
    """
    if fecha_corte is None:
        fecha_corte = date.today()

    # Años completos
    anios = calcular_anios_antiguedad(empleado.fecha_ingreso, fecha_corte)

    # Meses de la fracción (después del último año completo)
    from datetime import date as _date
    fecha_ultimo_aniversario = empleado.fecha_ingreso.replace(
        year=empleado.fecha_ingreso.year + anios
    ) if anios > 0 else empleado.fecha_ingreso

    meses_fraccion = calcular_meses_completos(
        fecha_ultimo_aniversario, fecha_corte
    )
    # Ajuste: si ya pasó el aniversario de este año, es otro año completo
    if anios > 0:
        meses_fraccion = calcular_meses_completos(
            empleado.fecha_ingreso.replace(
                year=empleado.fecha_ingreso.year + anios
            ),
            fecha_corte
        )

    fraccion_cuenta = meses_fraccion > MESES_PARA_FRACCION

    # Años para el cálculo
    anios_calculo = Decimal(str(anios))
    if fraccion_cuenta:
        anios_calculo += Decimal("1")

    # Días de retroactivo
    dias_retroactivo = DIAS_RETROACTIVO_POR_ANIO * anios_calculo

    # Salario integral (al momento del corte)
    sal = calcular_salario_integral_diario(empleado, parametros, fecha_corte)

    # Monto
    monto_ves = r2(dias_retroactivo * sal["salario_integral_diario"])

    return {
        "fecha_corte": fecha_corte,
        "anios_servicio": anios,
        "meses_fraccion": meses_fraccion,
        "fraccion_cuenta_como_anio": fraccion_cuenta,
        "anios_para_calculo": anios_calculo,
        "dias_retroactivo": dias_retroactivo,
        "salario_integral_diario": sal["salario_integral_diario"],
        "detalle_salario": sal,
        "monto_ves": monto_ves,
    }


# ═══════════════════════════════════════════════════════════
#  LITERAL d) — COMPARACIÓN
# ═══════════════════════════════════════════════════════════

def calcular_prestaciones(empleado, fecha_corte=None, parametros=None,
                           modo=None):
    """
    Calcula las prestaciones totales aplicando el Art. 142.d.

    Compara la garantía acumulada (a+b) contra el retroactivo (c)
    y devuelve el monto mayor según el modo configurado.

    Args:
        empleado: instancia de Empleado
        fecha_corte: fecha hasta la cual calcular (default hoy)
        parametros: instancia de ParametroNomina (opcional)
        modo: "garantia", "retroactivo" o "auto" (default auto)

    Returns:
        dict con:
            - garantia: dict del cálculo de garantía
            - retroactivo: dict del cálculo retroactivo
            - metodo_seleccionado: "garantia" o "retroactivo"
            - monto_final_ves: el mayor de los dos
    """
    if fecha_corte is None:
        fecha_corte = date.today()

    # Configuración de la empresa
    if modo is None:
        config = getattr(empleado.empresa, "configuracion_prestaciones", None)
        modo = config.modo_calculo if config else "auto"

    # Calcular ambos métodos
    garantia = calcular_garantia_acumulada(empleado, fecha_corte, parametros)
    retroactivo = calcular_retroactivo(empleado, fecha_corte, parametros)

    # Determinar método y monto final
    if modo == "garantia":
        metodo = "garantia"
        monto_final = garantia["total_ves"]
    elif modo == "retroactivo":
        metodo = "retroactivo"
        monto_final = retroactivo["monto_ves"]
    else:  # auto
        if garantia["total_ves"] >= retroactivo["monto_ves"]:
            metodo = "garantia"
            monto_final = garantia["total_ves"]
        else:
            metodo = "retroactivo"
            monto_final = retroactivo["monto_ves"]

    return {
        "fecha_corte": fecha_corte,
        "garantia": garantia,
        "retroactivo": retroactivo,
        "metodo_seleccionado": metodo,
        "monto_final_ves": monto_final,
    }