"""
Reportes de nómina: agregaciones y análisis.

Todas las funciones devuelven listas de dicts listos para serializar.
"""
from datetime import date
from decimal import Decimal

from django.db.models import (
    Sum, Count, Avg, Q, F, DecimalField, ExpressionWrapper
)
from django.db.models.functions import TruncMonth, Coalesce

from ..models import (
    PeriodoNomina, NominaEmpleado, NominaDetalle,
    ConceptoNomina, Empleado, Departamento, Cargo,
)


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _decimal_field():
    """Field para sumas decimales."""
    return DecimalField(max_digits=18, decimal_places=2)


def _sum_or_zero(queryset, field):
    """Suma un campo, devolviendo 0 si es None."""
    result = queryset.aggregate(total=Sum(field))["total"]
    return result or Decimal("0")


def _periodos_queryset(empresa_id, fecha_desde=None, fecha_hasta=None, estatus=None):
    """Filtra periodos de nómina por empresa y fechas."""
    qs = PeriodoNomina.objects.filter(empresa_id=empresa_id)

    if fecha_desde:
        qs = qs.filter(fecha_pago__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_pago__lte=fecha_hasta)
    if estatus:
        if isinstance(estatus, str):
            estatus = [estatus]
        qs = qs.filter(estatus__in=estatus)
    else:
        # Por defecto, excluir cancelados
        qs = qs.exclude(estatus="cancelado")

    return qs


# ═══════════════════════════════════════════════════════════
#  1. COSTO DE NÓMINA POR DEPARTAMENTO
# ═══════════════════════════════════════════════════════════

def costo_por_departamento(empresa_id, fecha_desde=None, fecha_hasta=None,
                           estatus=None, departamento_id=None):
    """
    Agrupa los costos de nómina por departamento.

    Returns:
        lista de dicts con:
            - departamento_id, departamento_nombre
            - empleados_unicos
            - total_percepciones
            - total_deducciones
            - total_neto
            - total_aportes_patronales
            - costo_total_empresa
            - promedio_neto
    """
    periodos = _periodos_queryset(empresa_id, fecha_desde, fecha_hasta, estatus)

    qs = NominaEmpleado.objects.filter(
        periodo__in=periodos,
    ).select_related("empleado__departamento")

    if departamento_id:
        qs = qs.filter(empleado__departamento_id=departamento_id)

    rows = qs.values(
        "empleado__departamento_id",
        "empleado__departamento__nombre",
    ).annotate(
        empleados_unicos=Count("empleado_id", distinct=True),
        nominas_count=Count("id"),
        total_percepciones=Coalesce(Sum("total_percepciones"), Decimal("0"), output_field=_decimal_field()),
        total_deducciones=Coalesce(Sum("total_deducciones"), Decimal("0"), output_field=_decimal_field()),
        total_neto=Coalesce(Sum("neto_pagar"), Decimal("0"), output_field=_decimal_field()),
        total_aportes_patronales=Coalesce(Sum("total_aportes_patronales"), Decimal("0"), output_field=_decimal_field()),
        costo_total_empresa=Coalesce(Sum("costo_total_empresa"), Decimal("0"), output_field=_decimal_field()),
    ).order_by("-costo_total_empresa")

    resultado = []
    for row in rows:
        promedio = Decimal("0")
        if row["nominas_count"] > 0:
            promedio = row["total_neto"] / row["nominas_count"]

        resultado.append({
            "departamento_id": row["empleado__departamento_id"],
            "departamento_nombre": row["empleado__departamento__nombre"] or "Sin departamento",
            "empleados_unicos": row["empleados_unicos"],
            "nominas_count": row["nominas_count"],
            "total_percepciones": row["total_percepciones"],
            "total_deducciones": row["total_deducciones"],
            "total_neto": row["total_neto"],
            "total_aportes_patronales": row["total_aportes_patronales"],
            "costo_total_empresa": row["costo_total_empresa"],
            "promedio_neto": round(promedio, 2),
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  2. COSTO DE NÓMINA POR CARGO
# ═══════════════════════════════════════════════════════════

def costo_por_cargo(empresa_id, fecha_desde=None, fecha_hasta=None,
                    estatus=None, cargo_id=None):
    """
    Agrupa los costos de nómina por cargo.
    """
    periodos = _periodos_queryset(empresa_id, fecha_desde, fecha_hasta, estatus)

    qs = NominaEmpleado.objects.filter(
        periodo__in=periodos,
    ).select_related("empleado__cargo")

    if cargo_id:
        qs = qs.filter(empleado__cargo_id=cargo_id)

    rows = qs.values(
        "empleado__cargo_id",
        "empleado__cargo__nombre",
        "empleado__cargo__codigo",
    ).annotate(
        empleados_unicos=Count("empleado_id", distinct=True),
        nominas_count=Count("id"),
        total_percepciones=Coalesce(Sum("total_percepciones"), Decimal("0"), output_field=_decimal_field()),
        total_deducciones=Coalesce(Sum("total_deducciones"), Decimal("0"), output_field=_decimal_field()),
        total_neto=Coalesce(Sum("neto_pagar"), Decimal("0"), output_field=_decimal_field()),
        total_aportes_patronales=Coalesce(Sum("total_aportes_patronales"), Decimal("0"), output_field=_decimal_field()),
        costo_total_empresa=Coalesce(Sum("costo_total_empresa"), Decimal("0"), output_field=_decimal_field()),
    ).order_by("-costo_total_empresa")

    resultado = []
    for row in rows:
        resultado.append({
            "cargo_id": row["empleado__cargo_id"],
            "cargo_nombre": row["empleado__cargo__nombre"] or "Sin cargo",
            "cargo_codigo": row["empleado__cargo__codigo"] or "",
            "empleados_unicos": row["empleados_unicos"],
            "nominas_count": row["nominas_count"],
            "total_percepciones": row["total_percepciones"],
            "total_deducciones": row["total_deducciones"],
            "total_neto": row["total_neto"],
            "total_aportes_patronales": row["total_aportes_patronales"],
            "costo_total_empresa": row["costo_total_empresa"],
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  3. RETENCIONES DE ISLR
# ═══════════════════════════════════════════════════════════

def retenciones_islr(empresa_id, fecha_desde=None, fecha_hasta=None,
                     estatus=None, empleado_id=None):
    """
    Retenciones de ISLR por empleado.

    Returns:
        lista de dicts con:
            - empleado_id, numero_empleado, nombre, cedula, cargo
            - nominas_count
            - base_islr
            - islr_retenido
    """
    periodos = _periodos_queryset(empresa_id, fecha_desde, fecha_hasta, estatus)

    qs = NominaEmpleado.objects.filter(
        periodo__in=periodos,
    ).select_related("empleado", "empleado__cargo")

    if empleado_id:
        qs = qs.filter(empleado_id=empleado_id)

    rows = qs.values(
        "empleado_id",
        "empleado__numero_empleado",
        "empleado__nombre",
        "empleado__apellido_paterno",
        "empleado__apellido_materno",
        "empleado__nacionalidad",
        "empleado__cedula",
        "empleado__cargo__nombre",
    ).annotate(
        nominas_count=Count("id"),
        base_islr=Coalesce(Sum("base_islr"), Decimal("0"), output_field=_decimal_field()),
        islr_retenido=Coalesce(Sum("islr_calculado"), Decimal("0"), output_field=_decimal_field()),
    ).order_by("-islr_retenido")

    resultado = []
    for row in qs:
        nombre_completo = " ".join(filter(None, [
            row["empleado__nombre"],
            row["empleado__apellido_paterno"],
            row["empleado__apellido_materno"],
        ]))

        resultado.append({
            "empleado_id": row["empleado_id"],
            "numero_empleado": row["empleado__numero_empleado"],
            "nombre": nombre_completo,
            "cedula": f"{row['empleado__nacionalidad']}-{row['empleado__cedula']}",
            "cargo": row["empleado__cargo__nombre"] or "—",
            "nominas_count": row["nominas_count"],
            "base_islr": row["base_islr"],
            "islr_retenido": row["islr_retenido"],
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  4. APORTES A ENTES (IVSS, RPE, BANAVIH, INCES, LOPCYMAT)
# ═══════════════════════════════════════════════════════════

def aportes_a_entes(empresa_id, fecha_desde=None, fecha_hasta=None,
                    estatus=None):
    """
    Aportes obreros y patronales agrupados por concepto.

    Returns:
        dict con:
            - obreros: lista de conceptos (IVSS, RPE, BANAVIH)
            - patronales: lista de conceptos (IVSS, RPE, BANAVIH, INCES, LOPCYMAT)
            - totales
    """
    periodos = _periodos_queryset(empresa_id, fecha_desde, fecha_hasta, estatus)

    # Aportes obreros (deducciones)
    obreros_qs = NominaDetalle.objects.filter(
        nomina__periodo__in=periodos,
        tipo="deduccion",
    ).values(
        "codigo_concepto",
        "nombre_concepto",
    ).annotate(
        total=Coalesce(Sum("importe"), Decimal("0"), output_field=_decimal_field()),
        empleados_count=Count("nomina__empleado_id", distinct=True),
    ).order_by("codigo_concepto")

    # Aportes patronales
    patronales_qs = NominaDetalle.objects.filter(
        nomina__periodo__in=periodos,
        tipo="aporte_patronal",
    ).values(
        "codigo_concepto",
        "nombre_concepto",
    ).annotate(
        total=Coalesce(Sum("importe"), Decimal("0"), output_field=_decimal_field()),
        empleados_count=Count("nomina__empleado_id", distinct=True),
    ).order_by("codigo_concepto")

    obreros = list(obreros_qs)
    patronales = list(patronales_qs)

    total_obreros = sum((o["total"] for o in obreros), Decimal("0"))
    total_patronales = sum((p["total"] for p in patronales), Decimal("0"))

    return {
        "obreros": obreros,
        "patronales": patronales,
        "total_obreros": total_obreros,
        "total_patronales": total_patronales,
        "total_general": total_obreros + total_patronales,
    }


# ═══════════════════════════════════════════════════════════
#  5. RESUMEN POR PERIODO
# ═══════════════════════════════════════════════════════════

def resumen_por_periodo(empresa_id, fecha_desde=None, fecha_hasta=None,
                        estatus=None, tipo=None):
    """
    Totales de cada periodo de nómina.

    Returns:
        lista de dicts con:
            - periodo_id, tipo, numero_periodo, anio
            - fecha_inicio, fecha_fin, fecha_pago, estatus
            - empleados_procesados
            - total_percepciones, total_deducciones, total_neto
            - total_aportes_patronales, total_costo_empresa
    """
    qs = _periodos_queryset(empresa_id, fecha_desde, fecha_hasta, estatus)

    if tipo:
        qs = qs.filter(tipo=tipo)

    qs = qs.order_by("-fecha_pago")

    resultado = []
    for periodo in qs:
        resultado.append({
            "periodo_id": periodo.id,
            "tipo": periodo.tipo,
            "tipo_display": periodo.get_tipo_display(),
            "numero_periodo": periodo.numero_periodo,
            "anio": periodo.anio,
            "fecha_inicio": periodo.fecha_inicio,
            "fecha_fin": periodo.fecha_fin,
            "fecha_pago": periodo.fecha_pago,
            "estatus": periodo.estatus,
            "estatus_display": periodo.get_estatus_display(),
            "empleados_procesados": periodo.empleados_procesados,
            "total_percepciones": periodo.total_percepciones,
            "total_deducciones": periodo.total_deducciones,
            "total_neto": periodo.total_neto,
            "total_aportes_patronales": periodo.total_aportes_patronales,
            "total_costo_empresa": periodo.total_costo_empresa,
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  6. RESUMEN CONSOLIDADO
# ═══════════════════════════════════════════════════════════

def resumen_consolidado(empresa_id, fecha_desde=None, fecha_hasta=None,
                        estatus=None):
    """
    Totales generales del rango.

    Returns:
        dict con:
            - periodos_count
            - empleados_unicos
            - total_percepciones
            - total_deducciones
            - total_neto
            - total_aportes_patronales
            - total_costo_empresa
            - promedio_costo_por_empleado
            - promedio_costo_por_periodo
    """
    periodos = _periodos_queryset(empresa_id, fecha_desde, fecha_hasta, estatus)

    nominas = NominaEmpleado.objects.filter(periodo__in=periodos)

    total_percepciones = _sum_or_zero(nominas, "total_percepciones")
    total_deducciones = _sum_or_zero(nominas, "total_deducciones")
    total_neto = _sum_or_zero(nominas, "neto_pagar")
    total_aportes = _sum_or_zero(nominas, "total_aportes_patronales")
    total_costo = _sum_or_zero(nominas, "costo_total_empresa")

    empleados_unicos = nominas.values("empleado_id").distinct().count()
    periodos_count = periodos.count()

    promedio_por_empleado = Decimal("0")
    if empleados_unicos > 0:
        promedio_por_empleado = total_costo / empleados_unicos

    promedio_por_periodo = Decimal("0")
    if periodos_count > 0:
        promedio_por_periodo = total_costo / periodos_count

    return {
        "periodos_count": periodos_count,
        "empleados_unicos": empleados_unicos,
        "total_percepciones": total_percepciones,
        "total_deducciones": total_deducciones,
        "total_neto": total_neto,
        "total_aportes_patronales": total_aportes,
        "total_costo_empresa": total_costo,
        "promedio_costo_por_empleado": round(promedio_por_empleado, 2),
        "promedio_costo_por_periodo": round(promedio_por_periodo, 2),
    }


# ═══════════════════════════════════════════════════════════
#  7. EVOLUCIÓN MENSUAL
# ═══════════════════════════════════════════════════════════

def evolucion_mensual(empresa_id, meses=12, estatus=None):
    """
    Evolución mensual del costo de nómina.

    Returns:
        lista de dicts por mes con:
            - mes (YYYY-MM)
            - periodos_count
            - empleados_promedio
            - total_neto
            - total_costo_empresa
    """
    desde = date.today() - timedelta(days=meses * 31)

    periodos = PeriodoNomina.objects.filter(
        empresa_id=empresa_id,
        fecha_pago__gte=desde,
    )
    if estatus:
        if isinstance(estatus, str):
            estatus = [estatus]
        periodos = periodos.filter(estatus__in=estatus)
    else:
        periodos = periodos.exclude(estatus="cancelado")

    rows = NominaEmpleado.objects.filter(
        periodo__in=periodos,
    ).annotate(
        mes=TruncMonth("periodo__fecha_pago"),
    ).values("mes").annotate(
        periodos_count=Count("periodo_id", distinct=True),
        empleados_promedio=Count("empleado_id", distinct=True),
        total_percepciones=Coalesce(Sum("total_percepciones"), Decimal("0"), output_field=_decimal_field()),
        total_deducciones=Coalesce(Sum("total_deducciones"), Decimal("0"), output_field=_decimal_field()),
        total_neto=Coalesce(Sum("neto_pagar"), Decimal("0"), output_field=_decimal_field()),
        total_costo_empresa=Coalesce(Sum("costo_total_empresa"), Decimal("0"), output_field=_decimal_field()),
    ).order_by("mes")

    resultado = []
    for row in rows:
        resultado.append({
            "mes": row["mes"].strftime("%Y-%m") if row["mes"] else None,
            "periodos_count": row["periodos_count"],
            "empleados_promedio": row["empleados_promedio"],
            "total_percepciones": row["total_percepciones"],
            "total_deducciones": row["total_deducciones"],
            "total_neto": row["total_neto"],
            "total_costo_empresa": row["total_costo_empresa"],
        })

    return resultado


# Import necesario para `evolucion_mensual`
from datetime import timedelta  # noqa: E402