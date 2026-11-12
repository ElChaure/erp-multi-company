"""
Motor de cálculo de nómina Venezuela.

Orquesta:
  1. Carga de datos del periodo y empleados
  2. Cálculo de percepciones (sueldos, cestaticket, horas extra, etc.)
  3. Cálculo de deducciones (ISLR, IVSS, RPE, BANAVIH, préstamos)
  4. Cálculo de aportes patronales
  5. Persistencia del detalle y totales
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction, models

from .formula_engine import construir_contexto, evaluar_formula
from django.utils import timezone

from ..models import (
    NominaEmpleado, NominaDetalle, IncidenciaNomina,
    ParametroNomina, ConceptoNomina, PeriodoNomina, Empleado,
)
from .islr import calcular_islr_periodo, calcular_islr_mensual
from .ivss import (
    calcular_ivss, calcular_rpe, calcular_banavih,
    calcular_inces, calcular_lopcymat,
)
from .utils import (
    r2, calcular_salario_diario, calcular_anios_antiguedad,
    calcular_meses_completos,
)


# ═══════════════════════════════════════════════════════════
#  EXCEPCIONES
# ═══════════════════════════════════════════════════════════

class NominaError(Exception):
    """Error durante el cálculo de nómina."""
    pass


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def obtener_parametros(empresa, anio):
    """Obtiene los parámetros de nómina de la empresa para el año."""
    try:
        return ParametroNomina.objects.get(empresa=empresa, anio=anio, activo=True)
    except ParametroNomina.DoesNotExist:
        raise NominaError(
            f"No hay parámetros de nómina configurados para {empresa.razon_social} "
            f"en el año {anio}."
        )


def obtener_conceptos(empresa):
    """Devuelve los conceptos activos (globales + de la empresa)."""
    return ConceptoNomina.objects.filter(
        activo=True,
    ).filter(
        # Conceptos globales (empresa=None) o de la empresa
        models.Q(empresa__isnull=True) | models.Q(empresa=empresa)
    ).order_by("prioridad", "codigo")


# ═══════════════════════════════════════════════════════════
#  CÁLCULO DE PERCEPCIONES
# ═══════════════════════════════════════════════════════════

def calcular_percepciones(empleado, periodo, parametros, incidencias):
    """
    Calcula todas las percepciones del empleado.

    Orden:
      1. Percepciones con lógica hardcodeada (sueldo, horas extra, etc.)
      2. Percepciones con fórmula configurable (conceptos fijos con formula)
    """
    percepciones = []
    total_percepciones = Decimal("0")
    total_gravado = Decimal("0")
    total_exento = Decimal("0")

    # ─── Datos base ──────────────────────────────────────
    salario_mensual = Decimal(str(empleado.salario_base))
    salario_diario = calcular_salario_diario(salario_mensual)
    dias_periodo = periodo.dias_periodo
    factor_periodo = Decimal(str(dias_periodo)) / Decimal("30")

    # ─── Agrupar incidencias por tipo ────────────────────
    incidencias_por_tipo = {}
    for inc in incidencias:
        incidencias_por_tipo.setdefault(inc.tipo, []).append(inc)

    dias_faltas = sum(
        Decimal(str(i.cantidad)) for i in incidencias_por_tipo.get("falta", [])
    )
    horas_extra_diurnas = sum(
        Decimal(str(i.cantidad))
        for i in incidencias_por_tipo.get("hora_extra_diurna", [])
    )
    horas_extra_nocturnas = sum(
        Decimal(str(i.cantidad))
        for i in incidencias_por_tipo.get("hora_extra_nocturna", [])
    )
    horas_nocturnas = sum(
        Decimal(str(i.cantidad))
        for i in incidencias_por_tipo.get("hora_nocturna", [])
    )
    dias_feriados = sum(
        Decimal(str(i.cantidad))
        for i in incidencias_por_tipo.get("feriado_trabajado", [])
    )

    dias_trabajados = dias_periodo - int(dias_faltas)
    sueldo_periodo = salario_mensual * factor_periodo
    sueldo_descontado = max(
        sueldo_periodo - (salario_diario * dias_faltas), Decimal("0")
    )
    valor_hora = salario_diario / Decimal("8")

    # ─── Contexto para fórmulas ──────────────────────────
    contexto = construir_contexto(
        empleado, periodo, parametros,
        extras={
            "dias_faltas": dias_faltas,
            "dias_trabajados": Decimal(str(dias_trabajados)),
            "horas_extra_diurnas": horas_extra_diurnas,
            "horas_extra_nocturnas": horas_extra_nocturnas,
            "horas_nocturnas": horas_nocturnas,
            "valor_hora": valor_hora,
            "sueldo_periodo": sueldo_periodo,
            "sueldo_descontado": sueldo_descontado,
            "factor_periodo": factor_periodo,
        },
    )
    
    # ─── Días de vacaciones ────────────────────────────────
    dias_vacaciones = sum(
        Decimal(str(i.cantidad))
        for i in incidencias_por_tipo.get("vacacion", [])
    )
    dias_incapacidad = sum(
        Decimal(str(i.cantidad))
        for i in incidencias_por_tipo.get("incapacidad", [])
    )


    # ═══════════════════════════════════════════════════════
    #  1. PERCEPCIONES HARDCODEADAS
    # ═══════════════════════════════════════════════════════

    # Sueldo básico
    percepciones.append({
        "codigo": "001",
        "nombre": "Sueldo básico",
        "tipo": "percepcion",
        "naturaleza": "gravado",
        "cantidad": dias_trabajados,
        "base_calculo": salario_mensual,
        "importe": r2(sueldo_descontado),
        "gravado": r2(sueldo_descontado),
        "exento": Decimal("0"),
        "base_ivss": r2(sueldo_descontado),
        "forma_parte_salario_normal": True,
    })
    total_percepciones += sueldo_descontado
    total_gravado += sueldo_descontado

    # ─── Prima vacacional (si tomó vacaciones) ────────────
    if dias_vacaciones > 0:
        prima_vacacional = (
            dias_vacaciones * salario_diario * Decimal("0.25")
        )
        percepciones.append({
            "codigo": "005",
            "nombre": "Prima vacacional",
            "tipo": "percepcion",
            "naturaleza": "gravado",
            "cantidad": float(dias_vacaciones),
            "base_calculo": r2(salario_diario),
            "importe": r2(prima_vacacional),
            "gravado": r2(prima_vacacional),
            "exento": Decimal("0"),
            "base_ivss": r2(prima_vacacional),
            "forma_parte_salario_normal": True,
        })
        total_percepciones += prima_vacacional
        total_gravado += prima_vacacional


    # Horas extra diurnas
    if horas_extra_diurnas > 0:
        monto_he = horas_extra_diurnas * valor_hora * Decimal("1.5")
        percepciones.append({
            "codigo": "010",
            "nombre": "Horas extra diurnas",
            "tipo": "percepcion",
            "naturaleza": "gravado",
            "cantidad": float(horas_extra_diurnas),
            "base_calculo": r2(valor_hora),
            "importe": r2(monto_he),
            "gravado": r2(monto_he),
            "exento": Decimal("0"),
            "base_ivss": r2(monto_he),
            "forma_parte_salario_normal": True,
        })
        total_percepciones += monto_he
        total_gravado += monto_he

    # Horas extra nocturnas
    if horas_extra_nocturnas > 0:
        monto_hen = horas_extra_nocturnas * valor_hora * Decimal("1.8")
        percepciones.append({
            "codigo": "011",
            "nombre": "Horas extra nocturnas",
            "tipo": "percepcion",
            "naturaleza": "gravado",
            "cantidad": float(horas_extra_nocturnas),
            "base_calculo": r2(valor_hora),
            "importe": r2(monto_hen),
            "gravado": r2(monto_hen),
            "exento": Decimal("0"),
            "base_ivss": r2(monto_hen),
            "forma_parte_salario_normal": True,
        })
        total_percepciones += monto_hen
        total_gravado += monto_hen

    # Bono nocturno
    if horas_nocturnas > 0:
        monto_bn = horas_nocturnas * valor_hora * Decimal("0.30")
        percepciones.append({
            "codigo": "012",
            "nombre": "Bono nocturno",
            "tipo": "percepcion",
            "naturaleza": "gravado",
            "cantidad": float(horas_nocturnas),
            "base_calculo": r2(valor_hora),
            "importe": r2(monto_bn),
            "gravado": r2(monto_bn),
            "exento": Decimal("0"),
            "base_ivss": r2(monto_bn),
            "forma_parte_salario_normal": True,
        })
        total_percepciones += monto_bn
        total_gravado += monto_bn

    # Cestaticket
    if parametros.cestaticket_mensual_usd > 0:
        monto_cesta_mensual = (
            Decimal(str(parametros.cestaticket_mensual_usd))
            * Decimal(str(parametros.tasa_bcv_usd))
        )
        monto_cesta_periodo = monto_cesta_mensual * factor_periodo
        percepciones.append({
            "codigo": "020",
            "nombre": "Cestaticket",
            "tipo": "percepcion",
            "naturaleza": "exento",
            "cantidad": dias_periodo,
            "base_calculo": r2(monto_cesta_mensual),
            "importe": r2(monto_cesta_periodo),
            "gravado": Decimal("0"),
            "exento": r2(monto_cesta_periodo),
            "base_ivss": Decimal("0"),
            "forma_parte_salario_normal": False,
        })
        total_percepciones += monto_cesta_periodo
        total_exento += monto_cesta_periodo

    # Feriados trabajados
    if dias_feriados > 0:
        monto_feriado = dias_feriados * salario_diario * Decimal("0.5")
        percepciones.append({
            "codigo": "030",
            "nombre": "Feriado trabajado (recargo 50%)",
            "tipo": "percepcion",
            "naturaleza": "gravado",
            "cantidad": float(dias_feriados),
            "base_calculo": r2(salario_diario),
            "importe": r2(monto_feriado),
            "gravado": r2(monto_feriado),
            "exento": Decimal("0"),
            "base_ivss": r2(monto_feriado),
            "forma_parte_salario_normal": True,
        })
        total_percepciones += monto_feriado
        total_gravado += monto_feriado

    # ═══════════════════════════════════════════════════════
    #  2. PERCEPCIONES CON FÓRMULA CONFIGURABLE
    # ═══════════════════════════════════════════════════════

    # Actualizar contexto con lo calculado
    contexto["total_percepciones_previas"] = total_percepciones
    contexto["total_gravado_previo"] = total_gravado

    # Códigos que ya aplicamos arriba (no duplicar)
    codigos_hardcoded = ["001", "010", "011", "012", "020", "030"]

    conceptos_formula = ConceptoNomina.objects.filter(
        activo=True,
        tipo="percepcion",
        es_fijo=True,
    ).exclude(
        codigo__in=codigos_hardcoded,
    ).filter(
        models.Q(empresa__isnull=True) | models.Q(empresa=empleado.empresa)
    ).order_by("prioridad", "codigo")

    for concepto in conceptos_formula:
        if not concepto.formula:
            continue

        monto, error = evaluar_formula(concepto.formula, contexto)

        if error:
            percepciones.append({
                "codigo": concepto.codigo,
                "nombre": concepto.nombre,
                "tipo": "percepcion",
                "naturaleza": concepto.naturaleza,
                "cantidad": 1,
                "base_calculo": Decimal("0"),
                "importe": Decimal("0"),
                "gravado": Decimal("0"),
                "exento": Decimal("0"),
                "base_ivss": Decimal("0"),
                "forma_parte_salario_normal": concepto.forma_parte_salario_normal,
                "error": error,
            })
            continue

        if monto is None or monto <= 0:
            continue

        # Determinar gravado/exento
        if concepto.naturaleza == "gravado":
            gravado = monto
            exento = Decimal("0")
        elif concepto.naturaleza == "exento":
            gravado = Decimal("0")
            exento = monto
        else:  # mixto
            gravado = monto
            exento = Decimal("0")

        base_ivss = monto if concepto.afecta_ivss else Decimal("0")

        percepciones.append({
            "codigo": concepto.codigo,
            "nombre": concepto.nombre,
            "tipo": "percepcion",
            "naturaleza": concepto.naturaleza,
            "cantidad": 1,
            "base_calculo": contexto.get("salario_base", Decimal("0")),
            "importe": monto,
            "gravado": gravado,
            "exento": exento,
            "base_ivss": base_ivss,
            "forma_parte_salario_normal": concepto.forma_parte_salario_normal,
        })

        total_percepciones += monto
        total_gravado += gravado
        total_exento += exento

        # Actualizar contexto para la siguiente iteración
        contexto["total_percepciones_previas"] = total_percepciones
        contexto["total_gravado_previo"] = total_gravado

    return {
        "percepciones": percepciones,
        "total_percepciones": r2(total_percepciones),
        "total_gravado": r2(total_gravado),
        "total_exento": r2(total_exento),
        "dias_faltas": dias_faltas,
        "dias_trabajados": dias_trabajados,
        "horas_extra_diurnas": horas_extra_diurnas,
        "horas_extra_nocturnas": horas_extra_nocturnas,
        "horas_nocturnas": horas_nocturnas,
        "salario_diario": salario_diario,
        "salario_mensual": salario_mensual,
    }


# ═══════════════════════════════════════════════════════════
#  CÁLCULO DE DEDUCCIONES
# ═══════════════════════════════════════════════════════════

def calcular_deducciones(empleado, periodo, parametros, base_islr,
                          base_ivss, base_rpe):
    """
    Calcula las deducciones del empleado: IVSS, RPE, BANAVIH, ISLR.

    Returns:
        dict con lista de deducciones y totales.
    """
    deducciones = []
    total_deducciones = Decimal("0")
    dias_periodo = periodo.dias_periodo

    # ─── IVSS Obrero ─────────────────────────────────────
    resultado_ivss = calcular_ivss(
        salario_mensual=base_ivss * Decimal("30") / Decimal(str(dias_periodo)),
        salario_minimo=Decimal(str(parametros.salario_minimo)),
        dias_periodo=dias_periodo,
        tasa_obrero=Decimal(str(parametros.ivss_obrero_pct)),
        tasa_patronal=Decimal(str(parametros.ivss_patronal_pct)),
        tope_salarios=Decimal(str(parametros.ivss_tope_salarios)),
    )

    if resultado_ivss["ivss_obrero"] > 0:
        deducciones.append({
            "codigo": "050",
            "nombre": "IVSS (Seguro Social)",
            "tipo": "deduccion",
            "cantidad": 1,
            "base_calculo": resultado_ivss["base_periodo"],
            "importe": resultado_ivss["ivss_obrero"],
        })
        total_deducciones += resultado_ivss["ivss_obrero"]

    # ─── Paro Forzoso (RPE) ──────────────────────────────
    resultado_rpe = calcular_rpe(
        salario_mensual=base_rpe * Decimal("30") / Decimal(str(dias_periodo)),
        salario_minimo=Decimal(str(parametros.salario_minimo)),
        dias_periodo=dias_periodo,
        tasa_obrero=Decimal(str(parametros.rpe_obrero_pct)),
        tasa_patronal=Decimal(str(parametros.rpe_patronal_pct)),
        tope_salarios=Decimal(str(parametros.rpe_tope_salarios)),
    )

    if resultado_rpe["rpe_obrero"] > 0:
        deducciones.append({
            "codigo": "051",
            "nombre": "Paro Forzoso (RPE)",
            "tipo": "deduccion",
            "cantidad": 1,
            "base_calculo": resultado_rpe["base_periodo"],
            "importe": resultado_rpe["rpe_obrero"],
        })
        total_deducciones += resultado_rpe["rpe_obrero"]

    # ─── BANAVIH ─────────────────────────────────────────
    resultado_banavih = calcular_banavih(
        salario_mensual=base_ivss * Decimal("30") / Decimal(str(dias_periodo)),
        dias_periodo=dias_periodo,
        tasa_obrero=Decimal(str(parametros.banavih_obrero_pct)),
        tasa_patronal=Decimal(str(parametros.banavih_patronal_pct)),
    )

    if resultado_banavih["banavih_obrero"] > 0:
        deducciones.append({
            "codigo": "052",
            "nombre": "BANAVIH (Vivienda)",
            "tipo": "deduccion",
            "cantidad": 1,
            "base_calculo": resultado_banavih["base_periodo"],
            "importe": resultado_banavih["banavih_obrero"],
        })
        total_deducciones += resultado_banavih["banavih_obrero"]

    # ─── ISLR ────────────────────────────────────────────
    resultado_islr = calcular_islr_periodo(
        base_gravable_periodo=base_islr,
        tipo_periodo=periodo.tipo,
        dias_periodo=dias_periodo,
    )

    if resultado_islr["islr_periodo"] > 0:
        deducciones.append({
            "codigo": "060",
            "nombre": "ISLR",
            "tipo": "deduccion",
            "cantidad": 1,
            "base_calculo": resultado_islr["base_periodo"],
            "importe": resultado_islr["islr_periodo"],
        })
        
    # ─── Deducciones con fórmula configurable ────────────
    codigos_hardcoded = ["050", "051", "052", "060"]

    contexto_ded = construir_contexto(
        empleado, periodo, parametros,
        extras={
            "base_islr": base_islr,
            "base_ivss": base_ivss,
            "base_rpe": base_rpe,
            "base_banavih": base_ivss,
        },
    )

    conceptos_ded = ConceptoNomina.objects.filter(
        activo=True,
        tipo="deduccion",
        es_fijo=True,
    ).exclude(
        codigo__in=codigos_hardcoded,
    ).filter(
        models.Q(empresa__isnull=True) | models.Q(empresa=empleado.empresa)
    ).order_by("prioridad", "codigo")

    for concepto in conceptos_ded:
        if not concepto.formula:
            continue

        monto, error = evaluar_formula(concepto.formula, contexto_ded)

        if error or monto is None or monto <= 0:
            continue

        deducciones.append({
            "codigo": concepto.codigo,
            "nombre": concepto.nombre,
            "tipo": "deduccion",
            "cantidad": 1,
            "base_calculo": contexto_ded.get("salario_base", Decimal("0")),
            "importe": monto,
        })
        total_deducciones += monto
        
        
        total_deducciones += resultado_islr["islr_periodo"]

    return {
        "deducciones": deducciones,
        "total_deducciones": r2(total_deducciones),
        "ivss_obrero": resultado_ivss["ivss_obrero"],
        "rpe_obrero": resultado_rpe["rpe_obrero"],
        "banavih_obrero": resultado_banavih["banavih_obrero"],
        "islr": resultado_islr["islr_periodo"],
        "detalles_ivss": resultado_ivss,
        "detalles_rpe": resultado_rpe,
        "detalles_islr": resultado_islr,
    }


# ═══════════════════════════════════════════════════════════
#  CÁLCULO DE APORTES PATRONALES
# ═══════════════════════════════════════════════════════════

def calcular_aportes_patronales(empleado, periodo, parametros, base_ivss):
    """
    Calcula los aportes patronales (no afectan el neto del empleado).
    """
    aportes = []
    total_aportes = Decimal("0")
    dias_periodo = periodo.dias_periodo

    salario_mensual = base_ivss * Decimal("30") / Decimal(str(dias_periodo))

    # IVSS Patronal
    ivss = calcular_ivss(
        salario_mensual=salario_mensual,
        salario_minimo=Decimal(str(parametros.salario_minimo)),
        dias_periodo=dias_periodo,
        tasa_patronal=Decimal(str(parametros.ivss_patronal_pct)),
        tope_salarios=Decimal(str(parametros.ivss_tope_salarios)),
    )
    if ivss["ivss_patronal"] > 0:
        aportes.append({
            "codigo": "100",
            "nombre": "IVSS patronal",
            "tipo": "aporte_patronal",
            "importe": ivss["ivss_patronal"],
        })
        total_aportes += ivss["ivss_patronal"]

    # RPE Patronal
    rpe = calcular_rpe(
        salario_mensual=salario_mensual,
        salario_minimo=Decimal(str(parametros.salario_minimo)),
        dias_periodo=dias_periodo,
        tasa_patronal=Decimal(str(parametros.rpe_patronal_pct)),
        tope_salarios=Decimal(str(parametros.rpe_tope_salarios)),
    )
    if rpe["rpe_patronal"] > 0:
        aportes.append({
            "codigo": "101",
            "nombre": "Paro Forzoso patronal",
            "tipo": "aporte_patronal",
            "importe": rpe["rpe_patronal"],
        })
        total_aportes += rpe["rpe_patronal"]

    # BANAVIH Patronal
    banavih = calcular_banavih(
        salario_mensual=salario_mensual,
        dias_periodo=dias_periodo,
        tasa_patronal=Decimal(str(parametros.banavih_patronal_pct)),
    )
    if banavih["banavih_patronal"] > 0:
        aportes.append({
            "codigo": "102",
            "nombre": "BANAVIH patronal",
            "tipo": "aporte_patronal",
            "importe": banavih["banavih_patronal"],
        })
        total_aportes += banavih["banavih_patronal"]

    # INCES
    inces = calcular_inces(
        salario_mensual=salario_mensual,
        dias_periodo=dias_periodo,
        tasa_patronal=Decimal(str(parametros.inces_patronal_pct)),
    )
    if inces["inces_patronal"] > 0:
        aportes.append({
            "codigo": "103",
            "nombre": "INCES patronal",
            "tipo": "aporte_patronal",
            "importe": inces["inces_patronal"],
        })
        total_aportes += inces["inces_patronal"]

    # LOPCYMAT
    lopcymat = calcular_lopcymat(
        salario_mensual=salario_mensual,
        categoria=parametros.lopcymat_categoria,
        dias_periodo=dias_periodo,
    )
    if lopcymat["lopcymat_patronal"] > 0:
        aportes.append({
            "codigo": "104",
            "nombre": f"LOPCYMAT ({parametros.lopcymat_categoria})",
            "tipo": "aporte_patronal",
            "importe": lopcymat["lopcymat_patronal"],
        })
        total_aportes += lopcymat["lopcymat_patronal"]
        # ─── Aportes patronales con fórmula ──────────────────
    codigos_hardcoded = ["100", "101", "102", "103", "104"]

    contexto_ap = construir_contexto(
        empleado, periodo, parametros,
        extras={"base_ivss": base_ivss},
    )

    conceptos_ap = ConceptoNomina.objects.filter(
        activo=True,
        tipo="aporte_patronal",
        es_fijo=True,
    ).exclude(
        codigo__in=codigos_hardcoded,
    ).filter(
        models.Q(empresa__isnull=True) | models.Q(empresa=empleado.empresa)
    ).order_by("prioridad", "codigo")

    for concepto in conceptos_ap:
        if not concepto.formula:
            continue

        monto, error = evaluar_formula(concepto.formula, contexto_ap)

        if error or monto is None or monto <= 0:
            continue

        aportes.append({
            "codigo": concepto.codigo,
            "nombre": concepto.nombre,
            "tipo": "aporte_patronal",
            "importe": monto,
        })
        total_aportes += monto
    return {
        "aportes": aportes,
        "total_aportes": r2(total_aportes),
    }


# ═══════════════════════════════════════════════════════════
#  CÁLCULO DE NÓMINA POR EMPLEADO
# ═══════════════════════════════════════════════════════════

def calcular_nomina_empleado(empleado, periodo, parametros):
    """
    Calcula la nómina completa de un empleado en un periodo.

    Returns:
        dict con toda la información de la nómina calculada.
    """
    # Cargar incidencias del empleado en el periodo
    incidencias = list(
        IncidenciaNomina.objects.filter(
            empleado=empleado,
            periodo=periodo,
            estatus__in=("pendiente", "aprobada"),
        )
    )

    # 1. Percepciones
    result_percepciones = calcular_percepciones(
        empleado, periodo, parametros, incidencias,
    )

    # 2. Bases
    base_islr = result_percepciones["total_gravado"]
    # Base IVSS = sueldo + horas extra + bono nocturno + feriados (parte salarial)
    base_ivss = sum(
        p["base_ivss"]
        for p in result_percepciones["percepciones"]
        if p["forma_parte_salario_normal"]
    )
    base_rpe = base_ivss  # Mismo cálculo que IVSS en Venezuela

    # 3. Deducciones
    result_deducciones = calcular_deducciones(
        empleado, periodo, parametros,
        base_islr=base_islr,
        base_ivss=base_ivss,
        base_rpe=base_rpe,
    )

    # 4. Aportes patronales
    result_aportes = calcular_aportes_patronales(
        empleado, periodo, parametros, base_ivss=base_ivss,
    )

    # 5. Neto
    neto_pagar = (
        result_percepciones["total_percepciones"]
        - result_deducciones["total_deducciones"]
    )
    if neto_pagar < 0:
        neto_pagar = Decimal("0")

    costo_total = result_percepciones["total_percepciones"] + result_aportes["total_aportes"]

    return {
        "empleado": empleado,
        "periodo": periodo,
        "salario_base": result_percepciones["salario_mensual"],
        "salario_diario": result_percepciones["salario_diario"],
        "salario_normal": base_ivss,
        "dias_periodo": periodo.dias_periodo,
        "dias_trabajados": result_percepciones["dias_trabajados"],
        "dias_faltas": int(result_percepciones["dias_faltas"]),
        "horas_extra_diurnas": result_percepciones["horas_extra_diurnas"],
        "horas_extra_nocturnas": result_percepciones["horas_extra_nocturnas"],
        "horas_nocturnas": result_percepciones["horas_nocturnas"],
        "percepciones": result_percepciones["percepciones"],
        "deducciones": result_deducciones["deducciones"],
        "aportes_patronales": result_aportes["aportes"],
        "total_percepciones": result_percepciones["total_percepciones"],
        "total_deducciones": result_deducciones["total_deducciones"],
        "neto_pagar": r2(neto_pagar),
        "total_aportes_patronales": result_aportes["total_aportes"],
        "costo_total_empresa": r2(costo_total),
        "base_islr": r2(base_islr),
        "base_ivss": r2(base_ivss),
        "islr_calculado": result_deducciones["islr"],
        "ivss_obrero": result_deducciones["ivss_obrero"],
    }


# ═══════════════════════════════════════════════════════════
#  PERSISTENCIA
# ═══════════════════════════════════════════════════════════

@transaction.atomic
def calcular_periodo(periodo, usuario=None):
    """
    Calcula la nómina completa de un periodo.

    Itera sobre todos los empleados activos de la empresa y genera:
      - NominaEmpleado (cabecera)
      - NominaDetalle (líneas por concepto)

    Actualiza los totales del periodo.

    Args:
        periodo: instancia de PeriodoNomina
        usuario: User que ejecuta el cálculo

    Returns:
        dict con resumen del cálculo
    """
    if not periodo.puede_calcularse:
        raise NominaError(
            f"El periodo está en estado '{periodo.estatus}' y no se puede calcular."
        )

    # Parámetros
    parametros = obtener_parametros(periodo.empresa, periodo.anio)

    # Empleados activos de la empresa
    empleados = Empleado.objects.filter(
        empresa=periodo.empresa,
        estatus="activo",
    ).select_related("cargo", "departamento", "sede")

    if not empleados.exists():
        raise NominaError(
            f"No hay empleados activos en {periodo.empresa.razon_social}."
        )

    # Eliminar nóminas previas del periodo (si se recalcula)
    NominaEmpleado.objects.filter(periodo=periodo).delete()

    totales = {
        "total_percepciones": Decimal("0"),
        "total_deducciones": Decimal("0"),
        "total_neto": Decimal("0"),
        "total_aportes": Decimal("0"),
        "total_costo": Decimal("0"),
        "empleados_procesados": 0,
        "errores": [],
    }

    for empleado in empleados:
        try:
            resultado = calcular_nomina_empleado(empleado, periodo, parametros)

            # Crear cabecera
            nomina = NominaEmpleado.objects.create(
                periodo=periodo,
                empleado=empleado,
                salario_base=resultado["salario_base"],
                salario_diario=resultado["salario_diario"],
                salario_normal=resultado["salario_normal"],
                salario_integral=Decimal("0"),  # Se puede calcular después
                dias_periodo=resultado["dias_periodo"],
                dias_trabajados=resultado["dias_trabajados"],
                dias_faltas=resultado["dias_faltas"],
                horas_extra_diurnas=resultado["horas_extra_diurnas"],
                horas_extra_nocturnas=resultado["horas_extra_nocturnas"],
                horas_nocturnas=resultado["horas_nocturnas"],
                total_percepciones=resultado["total_percepciones"],
                total_deducciones=resultado["total_deducciones"],
                neto_pagar=resultado["neto_pagar"],
                total_aportes_patronales=resultado["total_aportes_patronales"],
                costo_total_empresa=resultado["costo_total_empresa"],
                base_islr=resultado["base_islr"],
                islr_calculado=resultado["islr_calculado"],
                base_ivss=resultado["base_ivss"],
                ivss_obrero=resultado["ivss_obrero"],
                estatus="calculado",
            )

            # Crear detalles
            orden = 0
            for item in resultado["percepciones"]:
                orden += 10
                NominaDetalle.objects.create(
                    nomina=nomina,
                    concepto=_get_concepto_por_codigo(periodo.empresa, item["codigo"]),
                    codigo_concepto=item["codigo"],
                    nombre_concepto=item["nombre"],
                    tipo=item["tipo"],
                    naturaleza=item.get("naturaleza", "gravado"),
                    cantidad=item.get("cantidad", 1),
                    base_calculo=item.get("base_calculo", 0),
                    importe=item["importe"],
                    gravado=item.get("gravado", 0),
                    exento=item.get("exento", 0),
                    base_ivss=item.get("base_ivss", 0),
                    orden=orden,
                )

            for item in resultado["deducciones"]:
                orden += 10
                NominaDetalle.objects.create(
                    nomina=nomina,
                    concepto=_get_concepto_por_codigo(periodo.empresa, item["codigo"]),
                    codigo_concepto=item["codigo"],
                    nombre_concepto=item["nombre"],
                    tipo=item["tipo"],
                    naturaleza="gravado",
                    cantidad=item.get("cantidad", 1),
                    base_calculo=item.get("base_calculo", 0),
                    importe=item["importe"],
                    orden=orden,
                )

            for item in resultado["aportes_patronales"]:
                orden += 10
                NominaDetalle.objects.create(
                    nomina=nomina,
                    concepto=_get_concepto_por_codigo(periodo.empresa, item["codigo"]),
                    codigo_concepto=item["codigo"],
                    nombre_concepto=item["nombre"],
                    tipo="aporte_patronal",
                    naturaleza="gravado",
                    cantidad=1,
                    base_calculo=0,
                    importe=item["importe"],
                    orden=orden,
                )

            # Acumular totales
            totales["total_percepciones"] += resultado["total_percepciones"]
            totales["total_deducciones"] += resultado["total_deducciones"]
            totales["total_neto"] += resultado["neto_pagar"]
            totales["total_aportes"] += resultado["total_aportes_patronales"]
            totales["total_costo"] += resultado["costo_total_empresa"]
            totales["empleados_procesados"] += 1

        except Exception as e:
            totales["errores"].append({
                "empleado": empleado.numero_empleado,
                "nombre": empleado.nombre_completo,
                "error": str(e),
            })

    # Actualizar periodo
    periodo.total_percepciones = r2(totales["total_percepciones"])
    periodo.total_deducciones = r2(totales["total_deducciones"])
    periodo.total_neto = r2(totales["total_neto"])
    periodo.total_aportes_patronales = r2(totales["total_aportes"])
    periodo.total_costo_empresa = r2(totales["total_costo"])
    periodo.empleados_procesados = totales["empleados_procesados"]
    periodo.estatus = "calculado"
    periodo.calculado_por = usuario
    periodo.calculado_at = timezone.now()
    periodo.save()

    return {
        "periodo_id": periodo.id,
        "empleados_procesados": totales["empleados_procesados"],
        "total_percepciones": periodo.total_percepciones,
        "total_deducciones": periodo.total_deducciones,
        "total_neto": periodo.total_neto,
        "total_aportes_patronales": periodo.total_aportes_patronales,
        "total_costo_empresa": periodo.total_costo_empresa,
        "errores": totales["errores"],
    }


def _get_concepto_por_codigo(empresa, codigo):
    """
    Busca un concepto por código. Crea uno temporal si no existe
    (para no romper el cálculo).
    """
    try:
        return ConceptoNomina.objects.get(codigo=codigo, empresa=empresa)
    except ConceptoNomina.DoesNotExist:
        try:
            return ConceptoNomina.objects.get(codigo=codigo, empresa__isnull=True)
        except ConceptoNomina.DoesNotExist:
            # Crear concepto genérico
            return ConceptoNomina.objects.create(
                empresa=empresa,
                codigo=codigo,
                nombre=f"Concepto {codigo}",
                tipo="percepcion",
                naturaleza="gravado",
                activo=False,
            )