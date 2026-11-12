"""
Reportes del módulo de ausencias.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum, Q, Avg
from django.db.models.functions import ExtractYear

from ..models import (
    SaldoVacaciones, SolicitudAusencia, TipoAusencia, Empleado,
)


# ═══════════════════════════════════════════════════════════
#  1. SALDOS DE VACACIONES
# ═══════════════════════════════════════════════════════════

def reporte_saldos_vacaciones(empresa_id, anio=None, departamento_id=None,
                                empleado_id=None, solo_con_saldo=False):
    """
    Reporte de saldos de vacaciones por empleado.

    Returns:
        lista de dicts con:
            - empleado_id, numero, nombre, cedula, departamento, cargo
            - anio, dias_derecho, dias_tomados, dias_pagados, dias_ajuste
            - dias_pendientes
    """
    if anio is None:
        anio = date.today().year

    qs = SaldoVacaciones.objects.filter(
        empleado__empresa_id=empresa_id,
        empleado__estatus="activo",
        anio=anio,
    ).select_related(
        "empleado", "empleado__departamento", "empleado__cargo",
    )

    if departamento_id:
        qs = qs.filter(empleado__departamento_id=departamento_id)
    if empleado_id:
        qs = qs.filter(empleado_id=empleado_id)

    qs = qs.order_by(
        "empleado__departamento__nombre",
        "empleado__apellido_paterno",
        "empleado__nombre",
    )

    resultado = []
    for saldo in qs:
        if solo_con_saldo and saldo.dias_pendientes <= 0:
            continue

        resultado.append({
            "empleado_id": saldo.empleado.id,
            "numero_empleado": saldo.empleado.numero_empleado,
            "nombre": saldo.empleado.nombre_completo,
            "cedula": saldo.empleado.cedula_completa,
            "departamento": saldo.empleado.departamento.nombre if saldo.empleado.departamento else "",
            "cargo": saldo.empleado.cargo.nombre if saldo.empleado.cargo else "",
            "fecha_ingreso": saldo.empleado.fecha_ingreso,
            "anio": saldo.anio,
            "dias_derecho": saldo.dias_derecho,
            "dias_tomados": saldo.dias_tomados,
            "dias_pagados": saldo.dias_pagados,
            "dias_ajuste": saldo.dias_ajuste,
            "dias_pendientes": saldo.dias_pendientes,
            "fecha_limite_uso": saldo.fecha_limite_uso,
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  2. SOLICITUDES POR RANGO
# ═══════════════════════════════════════════════════════════

def reporte_solicitudes(empresa_id, fecha_desde=None, fecha_hasta=None,
                        estatus=None, tipo_id=None, empleado_id=None,
                        departamento_id=None):
    """
    Reporte de solicitudes de ausencia en un rango de fechas.
    """
    qs = SolicitudAusencia.objects.filter(
        empleado__empresa_id=empresa_id,
    ).select_related(
        "empleado", "empleado__departamento", "empleado__cargo",
        "tipo", "aprobador",
    )

    if fecha_desde:
        qs = qs.filter(fecha_fin__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_inicio__lte=fecha_hasta)
    if estatus:
        if isinstance(estatus, str):
            estatus = [estatus]
        qs = qs.filter(estatus__in=estatus)
    if tipo_id:
        qs = qs.filter(tipo_id=tipo_id)
    if empleado_id:
        qs = qs.filter(empleado_id=empleado_id)
    if departamento_id:
        qs = qs.filter(empleado__departamento_id=departamento_id)

    qs = qs.order_by("-fecha_inicio")

    resultado = []
    for sol in qs:
        resultado.append({
            "id": sol.id,
            "empleado_id": sol.empleado.id,
            "numero_empleado": sol.empleado.numero_empleado,
            "nombre": sol.empleado.nombre_completo,
            "cedula": sol.empleado.cedula_completa,
            "departamento": sol.empleado.departamento.nombre if sol.empleado.departamento else "",
            "cargo": sol.empleado.cargo.nombre if sol.empleado.cargo else "",
            "tipo": sol.tipo.nombre,
            "categoria": sol.tipo.categoria,
            "fecha_inicio": sol.fecha_inicio,
            "fecha_fin": sol.fecha_fin,
            "dias_solicitados": sol.dias_solicitados,
            "dias_calendario": sol.dias_calendario,
            "estatus": sol.estatus,
            "estatus_display": sol.get_estatus_display(),
            "aprobador": sol.aprobador.nombre_completo if sol.aprobador else "",
            "fecha_solicitud": sol.fecha_solicitud,
            "fecha_resolucion": sol.fecha_resolucion,
            "motivo": sol.motivo,
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  3. PRÓXIMAS VACACIONES (o ausencias programadas)
# ═══════════════════════════════════════════════════════════

def reporte_proximas_ausencias(empresa_id, dias_adelante=30,
                                departamento_id=None):
    """
    Ausencias aprobadas en los próximos N días.
    """
    hoy = date.today()
    limite = hoy + timedelta(days=dias_adelante)

    qs = SolicitudAusencia.objects.filter(
        empleado__empresa_id=empresa_id,
        estatus__in=["aprobada", "en_disfrute"],
        fecha_inicio__lte=limite,
        fecha_fin__gte=hoy,
    ).select_related(
        "empleado", "empleado__departamento", "empleado__cargo", "tipo",
    )

    if departamento_id:
        qs = qs.filter(empleado__departamento_id=departamento_id)

    qs = qs.order_by("fecha_inicio")

    resultado = []
    for sol in qs:
        resultado.append({
            "id": sol.id,
            "empleado_id": sol.empleado.id,
            "numero_empleado": sol.empleado.numero_empleado,
            "nombre": sol.empleado.nombre_completo,
            "departamento": sol.empleado.departamento.nombre if sol.empleado.departamento else "",
            "cargo": sol.empleado.cargo.nombre if sol.empleado.cargo else "",
            "tipo": sol.tipo.nombre,
            "categoria": sol.tipo.categoria,
            "fecha_inicio": sol.fecha_inicio,
            "fecha_fin": sol.fecha_fin,
            "fecha_reincorporacion": sol.fecha_reincorporacion,
            "dias_solicitados": sol.dias_solicitados,
            "estatus": sol.estatus,
            "dias_hasta_inicio": (sol.fecha_inicio - hoy).days,
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  4. RESUMEN POR DEPARTAMENTO
# ═══════════════════════════════════════════════════════════

def reporte_ausencias_por_departamento(empresa_id, fecha_desde=None,
                                        fecha_hasta=None, anio=None):
    """
    Resumen de ausencias agrupadas por departamento.

    Returns:
        lista de dicts con:
            - departamento_id, departamento_nombre
            - empleados_unicos
            - solicitudes_count
            - dias_totales
            - dias_promedio
    """
    if anio and not fecha_desde:
        fecha_desde = date(anio, 1, 1)
    if anio and not fecha_hasta:
        fecha_hasta = date(anio, 12, 31)

    qs = SolicitudAusencia.objects.filter(
        empleado__empresa_id=empresa_id,
        estatus="aprobada",
    )

    if fecha_desde:
        qs = qs.filter(fecha_inicio__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_inicio__lte=fecha_hasta)

    qs = qs.values(
        "empleado__departamento_id",
        "empleado__departamento__nombre",
    ).annotate(
        empleados_unicos=Count("empleado_id", distinct=True),
        solicitudes_count=Count("id"),
        dias_totales=Sum("dias_solicitados"),
        dias_promedio=Avg("dias_solicitados"),
    ).order_by("-dias_totales")

    resultado = []
    for row in qs:
        resultado.append({
            "departamento_id": row["empleado__departamento_id"],
            "departamento_nombre": row["empleado__departamento__nombre"] or "Sin departamento",
            "empleados_unicos": row["empleados_unicos"],
            "solicitudes_count": row["solicitudes_count"],
            "dias_totales": row["dias_totales"] or Decimal("0"),
            "dias_promedio": round(row["dias_promedio"] or Decimal("0"), 2),
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  5. RESUMEN POR TIPO DE AUSENCIA
# ═══════════════════════════════════════════════════════════

def reporte_ausencias_por_tipo(empresa_id, fecha_desde=None, fecha_hasta=None,
                                 anio=None):
    """
    Resumen de ausencias agrupadas por tipo.
    """
    if anio and not fecha_desde:
        fecha_desde = date(anio, 1, 1)
    if anio and not fecha_hasta:
        fecha_hasta = date(anio, 12, 31)

    qs = SolicitudAusencia.objects.filter(
        empleado__empresa_id=empresa_id,
        estatus="aprobada",
    )

    if fecha_desde:
        qs = qs.filter(fecha_inicio__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_inicio__lte=fecha_hasta)

    qs = qs.values(
        "tipo_id",
        "tipo__nombre",
        "tipo__categoria",
    ).annotate(
        empleados_unicos=Count("empleado_id", distinct=True),
        solicitudes_count=Count("id"),
        dias_totales=Sum("dias_solicitados"),
        dias_promedio=Avg("dias_solicitados"),
    ).order_by("-dias_totales")

    resultado = []
    for row in qs:
        resultado.append({
            "tipo_id": row["tipo_id"],
            "tipo_nombre": row["tipo__nombre"],
            "categoria": row["tipo__categoria"],
            "empleados_unicos": row["empleados_unicos"],
            "solicitudes_count": row["solicitudes_count"],
            "dias_totales": row["dias_totales"] or Decimal("0"),
            "dias_promedio": round(row["dias_promedio"] or Decimal("0"), 2),
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  6. RESUMEN CONSOLIDADO
# ═══════════════════════════════════════════════════════════

def reporte_consolidado(empresa_id, anio=None):
    """
    Resumen general de ausencias en un año.
    """
    if anio is None:
        anio = date.today().year

    fecha_desde = date(anio, 1, 1)
    fecha_hasta = date(anio, 12, 31)

    solicitudes = SolicitudAusencia.objects.filter(
        empleado__empresa_id=empresa_id,
        fecha_inicio__gte=fecha_desde,
        fecha_inicio__lte=fecha_hasta,
    )

    total = solicitudes.count()
    aprobadas = solicitudes.filter(estatus="aprobada").count()
    rechazadas = solicitudes.filter(estatus="rechazada").count()
    pendientes = solicitudes.filter(estatus="pendiente").count()

    dias_aprobados = solicitudes.filter(estatus="aprobada").aggregate(
        total=Sum("dias_solicitados")
    )["total"] or Decimal("0")

    empleados_con_ausencia = solicitudes.filter(
        estatus="aprobada"
    ).values("empleado_id").distinct().count()

    saldos = SaldoVacaciones.objects.filter(
        empleado__empresa_id=empresa_id,
        anio=anio,
    )

    dias_pendientes_total = sum(
        (s.dias_pendientes for s in saldos), Decimal("0"),
    )

    return {
        "anio": anio,
        "total_solicitudes": total,
        "solicitudes_aprobadas": aprobadas,
        "solicitudes_rechazadas": rechazadas,
        "solicitudes_pendientes": pendientes,
        "dias_aprobados": dias_aprobados,
        "empleados_con_ausencia": empleados_con_ausencia,
        "empleados_con_saldo": saldos.count(),
        "dias_pendientes_total": dias_pendientes_total,
    }