"""
Servicios puros para el Dashboard Ejecutivo.

Todas las funciones reciben `empresa_id` (opcional). Si es None, se
consideran todas las empresas (solo para superadmin).

Devuelven estructuras serializables (dicts, lists, Decimal -> float).
"""
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

from django.db.models import Sum, Count, Q, Avg, Min, Max
from django.db.models.functions import TruncMonth
from django.utils import timezone

from rrhh.models import (
    Empleado,
    Empresa,
    Departamento,
    PeriodoNomina,
    NominaEmpleado,
    SolicitudAusencia,
    SaldoVacaciones,
    TipoAusencia,
    IncidenciaNomina,
)


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _float(value):
    """Convierte Decimal a float de forma segura."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _empleados_qs(empresa_id=None):
    """Queryset base de empleados filtrado por empresa."""
    qs = Empleado.objects.all()
    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)
    return qs


def _periodos_qs(empresa_id=None):
    """Queryset base de periodos filtrado por empresa."""
    qs = PeriodoNomina.objects.all()
    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)
    return qs


def _meses_ultimos_n(n):
    """Devuelve los últimos n meses como [(anio, mes), ...] ordenados asc."""
    hoy = timezone.now().date()
    meses = []
    y, m = hoy.year, hoy.month
    for _ in range(n):
        meses.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(meses))


def _rango_mes_actual():
    """Retorna (primer_dia, ultimo_dia) del mes actual."""
    hoy = timezone.now().date()
    primer_dia = hoy.replace(day=1)
    if hoy.month == 12:
        ultimo_dia = hoy.replace(year=hoy.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        ultimo_dia = hoy.replace(month=hoy.month + 1, day=1) - timedelta(days=1)
    return primer_dia, ultimo_dia


def _rango_mes_anterior():
    """Retorna (primer_dia, ultimo_dia) del mes anterior."""
    hoy = timezone.now().date()
    if hoy.month == 1:
        y, m = hoy.year - 1, 12
    else:
        y, m = hoy.year, hoy.month - 1

    primer_dia = date(y, m, 1)
    if m == 12:
        ultimo_dia = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        ultimo_dia = date(y, m + 1, 1) - timedelta(days=1)
    return primer_dia, ultimo_dia


def _delta_pct(actual, anterior):
    """
    Calcula el delta porcentual entre dos valores.
    Retorna None si no se puede calcular (anterior = 0).
    """
    if anterior == 0:
        return None
    return round(((actual - anterior) / anterior) * 100, 2)


def _comparativa(actual, anterior):
    """Devuelve dict con actual, anterior y delta."""
    return {
        "actual": actual,
        "anterior": anterior,
        "delta_pct": _delta_pct(actual, anterior),
    }


# ═══════════════════════════════════════════════════════════
#  BLOQUE 1 — HEADCOUNT
# ═══════════════════════════════════════════════════════════

def kpis_headcount(empresa_id=None):
    """
    KPIs de headcount: total, activos, nuevos del mes, bajas del mes.
    Incluye comparativa con mes anterior para nuevos/bajas.
    """
    qs = _empleados_qs(empresa_id)
    hoy = timezone.now().date()
    primer_dia, ultimo_dia = _rango_mes_actual()
    primer_dia_ant, ultimo_dia_ant = _rango_mes_anterior()

    total = qs.count()
    activos = qs.filter(estatus="activo").count()
    licencias = qs.filter(estatus="licencia").count()
    vacaciones = qs.filter(estatus="vacaciones").count()
    bajas = qs.filter(estatus="baja").count()

    # Ingresos del mes actual
    nuevos_mes = qs.filter(
        fecha_ingreso__gte=primer_dia,
        fecha_ingreso__lte=ultimo_dia,
    ).count()

    # Ingresos del mes anterior
    nuevos_mes_ant = qs.filter(
        fecha_ingreso__gte=primer_dia_ant,
        fecha_ingreso__lte=ultimo_dia_ant,
    ).count()

    # Bajas del mes actual
    bajas_mes = qs.filter(
        fecha_egreso__gte=primer_dia,
        fecha_egreso__lte=ultimo_dia,
    ).count()

    # Bajas del mes anterior
    bajas_mes_ant = qs.filter(
        fecha_egreso__gte=primer_dia_ant,
        fecha_egreso__lte=ultimo_dia_ant,
    ).count()

    # Rotación mensual = (bajas_mes / total) * 100
    rotacion_pct = (bajas_mes / total * 100) if total > 0 else 0
    total_ant = total - nuevos_mes + bajas_mes  # aproximación: total mes anterior
    rotacion_pct_ant = (bajas_mes_ant / total_ant * 100) if total_ant > 0 else 0

    # Distribución por estatus (para gráfico)
    por_estatus = list(
        qs.values("estatus")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    return {
        "total": total,
        "activos": activos,
        "licencias": licencias,
        "vacaciones": vacaciones,
        "bajas": bajas,

        # Comparativas mes actual vs anterior
        "nuevos_mes": nuevos_mes,
        "nuevos_mes_anterior": nuevos_mes_ant,
        "nuevos_mes_delta_pct": _delta_pct(nuevos_mes, nuevos_mes_ant),

        "bajas_mes": bajas_mes,
        "bajas_mes_anterior": bajas_mes_ant,
        "bajas_mes_delta_pct": _delta_pct(bajas_mes, bajas_mes_ant),

        "rotacion_pct": round(rotacion_pct, 2),
        "rotacion_pct_anterior": round(rotacion_pct_ant, 2),
        "rotacion_pct_delta": round(rotacion_pct - rotacion_pct_ant, 2),

        "por_estatus": por_estatus,
    }


def kpis_headcount_por_departamento(empresa_id=None, top=10):
    """
    Headcount activo agrupado por departamento.
    """
    qs = (
        _empleados_qs(empresa_id)
        .filter(estatus="activo")
        .values("departamento__id", "departamento__nombre", "departamento__codigo")
        .annotate(total=Count("id"))
        .order_by("-total")[:top]
    )
    return [
        {
            "departamento_id": row["departamento__id"],
            "departamento": row["departamento__nombre"] or "Sin departamento",
            "codigo": row["departamento__codigo"] or "—",
            "total": row["total"],
        }
        for row in qs
    ]


def kpis_headcount_por_cargo(empresa_id=None, top=10):
    """
    Headcount activo agrupado por cargo.
    """
    qs = (
        _empleados_qs(empresa_id)
        .filter(estatus="activo")
        .values("cargo__id", "cargo__nombre", "cargo__codigo")
        .annotate(total=Count("id"))
        .order_by("-total")[:top]
    )
    return [
        {
            "cargo_id": row["cargo__id"],
            "cargo": row["cargo__nombre"] or "Sin cargo",
            "codigo": row["cargo__codigo"] or "—",
            "total": row["total"],
        }
        for row in qs
    ]


# ═══════════════════════════════════════════════════════════
#  BLOQUE 2 — NÓMINA
# ═══════════════════════════════════════════════════════════

def kpis_nomina_ultimo_periodo(empresa_id=None):
    """
    Datos del último periodo aprobado/pagado/cerrado.
    Incluye comparativa con el periodo anterior.
    """
    qs = _periodos_qs(empresa_id).filter(
        estatus__in=["aprobado", "pagado", "cerrado"]
    ).order_by("-fecha_pago")

    periodo = qs.first()

    if not periodo:
        # Fallback: cualquier periodo
        periodo = _periodos_qs(empresa_id).order_by("-fecha_pago").first()

    if not periodo:
        return {
            "periodo": None,
            "total_percepciones": 0,
            "total_deducciones": 0,
            "total_neto": 0,
            "total_aportes_patronales": 0,
            "total_costo_empresa": 0,
            "empleados_procesados": 0,
            "comparativas": {},
        }

    # Buscar el anterior (excluyendo el actual)
    periodo_ant = qs.exclude(id=periodo.id).first()

    comparativas = {}
    if periodo_ant:
        comparativas = {
            "total_percepciones_delta_pct": _delta_pct(
                _float(periodo.total_percepciones),
                _float(periodo_ant.total_percepciones),
            ),
            "total_deducciones_delta_pct": _delta_pct(
                _float(periodo.total_deducciones),
                _float(periodo_ant.total_deducciones),
            ),
            "total_neto_delta_pct": _delta_pct(
                _float(periodo.total_neto),
                _float(periodo_ant.total_neto),
            ),
            "total_costo_empresa_delta_pct": _delta_pct(
                _float(periodo.total_costo_empresa),
                _float(periodo_ant.total_costo_empresa),
            ),
            "periodo_anterior_label": (
                f"{periodo_ant.get_tipo_display()} #{periodo_ant.numero_periodo}"
            ),
        }

    return {
        "periodo": {
            "id": periodo.id,
            "tipo": periodo.tipo,
            "tipo_display": periodo.get_tipo_display(),
            "numero_periodo": periodo.numero_periodo,
            "anio": periodo.anio,
            "fecha_inicio": periodo.fecha_inicio.isoformat(),
            "fecha_fin": periodo.fecha_fin.isoformat(),
            "fecha_pago": periodo.fecha_pago.isoformat(),
            "estatus": periodo.estatus,
            "estatus_display": periodo.get_estatus_display(),
        },
        "total_percepciones": _float(periodo.total_percepciones),
        "total_deducciones": _float(periodo.total_deducciones),
        "total_neto": _float(periodo.total_neto),
        "total_aportes_patronales": _float(periodo.total_aportes_patronales),
        "total_costo_empresa": _float(periodo.total_costo_empresa),
        "empleados_procesados": periodo.empleados_procesados,
        "comparativas": comparativas,
    }


def kpis_nomina_evolucion(empresa_id=None, meses=12):
    """
    Evolución mensual del costo de nómina (últimos N meses).

    Retorna lista de:
        { mes: "2026-01", label: "Ene 2026",
          total_neto, total_costo_empresa, empleados }
    """
    meses = max(1, min(int(meses), 36))  # entre 1 y 36

    meses_lista = _meses_ultimos_n(meses)
    primer_mes = meses_lista[0]
    fecha_desde = date(primer_mes[0], primer_mes[1], 1)

    qs = (
        _periodos_qs(empresa_id)
        .filter(
            fecha_pago__gte=fecha_desde,
            estatus__in=["aprobado", "pagado", "cerrado"],
        )
        .annotate(mes=TruncMonth("fecha_pago"))
        .values("mes")
        .annotate(
            total_neto=Sum("total_neto"),
            total_costo_empresa=Sum("total_costo_empresa"),
            total_aportes_patronales=Sum("total_aportes_patronales"),
            empleados=Sum("empleados_procesados"),
        )
        .order_by("mes")
    )

    # Indexar por (anio, mes)
    por_mes = {}
    for row in qs:
        if row["mes"]:
            por_mes[(row["mes"].year, row["mes"].month)] = row

    MESES_ES = [
        "", "Ene", "Feb", "Mar", "Abr", "May", "Jun",
        "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
    ]

    resultado = []
    for (y, m) in meses_lista:
        row = por_mes.get((y, m))
        resultado.append({
            "mes": f"{y:04d}-{m:02d}",
            "label": f"{MESES_ES[m]} {y}",
            "total_neto": _float(row["total_neto"]) if row else 0.0,
            "total_costo_empresa": _float(row["total_costo_empresa"]) if row else 0.0,
            "total_aportes_patronales": _float(row["total_aportes_patronales"]) if row else 0.0,
            "empleados": row["empleados"] if row else 0,
        })

    return resultado


def kpis_nomina_por_departamento(empresa_id=None, periodo_id=None, top=10):
    """
    Costo de nómina por departamento.
    Usa el último periodo aprobado/pagado/cerrado si no se especifica.
    """
    if not periodo_id:
        periodo = (
            _periodos_qs(empresa_id)
            .filter(estatus__in=["aprobado", "pagado", "cerrado"])
            .order_by("-fecha_pago")
            .first()
        )
        if not periodo:
            periodo = _periodos_qs(empresa_id).order_by("-fecha_pago").first()
    else:
        periodo = PeriodoNomina.objects.filter(id=periodo_id).first()

    if not periodo:
        return {"periodo": None, "items": []}

    qs = (
        NominaEmpleado.objects
        .filter(periodo=periodo)
        .values(
            "empleado__departamento__id",
            "empleado__departamento__nombre",
            "empleado__departamento__codigo",
        )
        .annotate(
            total_neto=Sum("neto_pagar"),
            total_costo=Sum("costo_total_empresa"),
            empleados=Count("id"),
        )
        .order_by("-total_costo")[:top]
    )

    return {
        "periodo": {
            "id": periodo.id,
            "label": f"{periodo.get_tipo_display()} #{periodo.numero_periodo} ({periodo.fecha_inicio} - {periodo.fecha_fin})",
        },
        "items": [
            {
                "departamento_id": row["empleado__departamento__id"],
                "departamento": row["empleado__departamento__nombre"] or "Sin departamento",
                "codigo": row["empleado__departamento__codigo"] or "—",
                "total_neto": _float(row["total_neto"]),
                "total_costo": _float(row["total_costo"]),
                "empleados": row["empleados"],
            }
            for row in qs
        ],
    }


# ═══════════════════════════════════════════════════════════
#  BLOQUE 3 — AUSENCIAS
# ═══════════════════════════════════════════════════════════

def kpis_ausencias_resumen(empresa_id=None):
    """
    Resumen de ausencias: pendientes, ausentes hoy, por tipo.
    """
    hoy = timezone.now().date()

    qs_solicitudes = SolicitudAusencia.objects.all()
    if empresa_id:
        qs_solicitudes = qs_solicitudes.filter(empleado__empresa_id=empresa_id)

    pendientes = qs_solicitudes.filter(estatus="pendiente").count()
    aprobadas = qs_solicitudes.filter(estatus="aprobada").count()
    en_disfrute = qs_solicitudes.filter(
        estatus__in=["aprobada", "en_disfrute"],
        fecha_inicio__lte=hoy,
        fecha_fin__gte=hoy,
    ).count()

    # Distribución por tipo (últimos 12 meses)
    hace_12_meses = hoy - timedelta(days=365)
    por_tipo = list(
        qs_solicitudes
        .filter(fecha_solicitud__date__gte=hace_12_meses)
        .values("tipo__nombre", "tipo__codigo", "tipo__categoria")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    return {
        "pendientes": pendientes,
        "aprobadas": aprobadas,
        "en_disfrute_hoy": en_disfrute,
        "por_tipo": [
            {
                "tipo": row["tipo__nombre"],
                "codigo": row["tipo__codigo"],
                "categoria": row["tipo__categoria"],
                "total": row["total"],
            }
            for row in por_tipo
        ],
    }


def kpis_saldos_vacaciones(empresa_id=None, anio=None, top=10):
    """
    Top N empleados con más días pendientes de vacaciones.
    """
    if not anio:
        anio = timezone.now().year

    qs = (
        SaldoVacaciones.objects
        .filter(anio=anio)
        .select_related("empleado")
    )
    if empresa_id:
        qs = qs.filter(empleado__empresa_id=empresa_id)

    items = []
    for saldo in qs:
        dias = saldo.dias_pendientes
        if dias > 0:
            items.append({
                "empleado_id": saldo.empleado_id,
                "empleado": saldo.empleado.nombre_completo,
                "numero_empleado": saldo.empleado.numero_empleado,
                "dias_pendientes": _float(dias),
                "anio": saldo.anio,
            })

    items.sort(key=lambda x: x["dias_pendientes"], reverse=True)
    return {
        "anio": anio,
        "total_empleados_con_saldo": len(items),
        "items": items[:top],
    }


# ═══════════════════════════════════════════════════════════
#  BLOQUE 4 — ALERTAS
# ═══════════════════════════════════════════════════════════

def kpis_alertas(empresa_id=None):
    """
    Alertas operativas para RRHH.
    """
    qs_emp = _empleados_qs(empresa_id)

    # Empleados sin contrato definido
    sin_contrato = qs_emp.filter(tipo_contrato="").count()

    # Empleados sin cuenta bancaria
    sin_cuenta = qs_emp.filter(
        Q(cuenta_bancaria__isnull=True) | Q(cuenta_bancaria="")
    ).count()

    # Empleados sin departamento
    sin_departamento = qs_emp.filter(departamento__isnull=True).count()

    # Empleados sin cargo
    sin_cargo = qs_emp.filter(cargo__isnull=True).count()

    # Periodos abiertos o calculados sin cerrar
    periodos_abiertos = _periodos_qs(empresa_id).filter(
        estatus__in=["abierto", "calculado", "aprobado", "pagado"]
    ).count()

    # Solicitudes pendientes de aprobación
    qs_sol = SolicitudAusencia.objects.filter(estatus="pendiente")
    if empresa_id:
        qs_sol = qs_sol.filter(empleado__empresa_id=empresa_id)
    solicitudes_pendientes = qs_sol.count()

    # Incidencias pendientes
    qs_inc = IncidenciaNomina.objects.filter(estatus="pendiente")
    if empresa_id:
        qs_inc = qs_inc.filter(empleado__empresa_id=empresa_id)
    incidencias_pendientes = qs_inc.count()

    alertas = []
    if sin_contrato > 0:
        alertas.append({
            "nivel": "warning",
            "codigo": "sin_contrato",
            "titulo": "Empleados sin tipo de contrato",
            "total": sin_contrato,
            "descripcion": f"{sin_contrato} empleado(s) no tienen tipo de contrato definido.",
        })
    if sin_cuenta > 0:
        alertas.append({
            "nivel": "warning",
            "codigo": "sin_cuenta_bancaria",
            "titulo": "Empleados sin cuenta bancaria",
            "total": sin_cuenta,
            "descripcion": f"{sin_cuenta} empleado(s) no tienen cuenta bancaria registrada.",
        })
    if sin_departamento > 0:
        alertas.append({
            "nivel": "info",
            "codigo": "sin_departamento",
            "titulo": "Empleados sin departamento",
            "total": sin_departamento,
            "descripcion": f"{sin_departamento} empleado(s) no están asignados a un departamento.",
        })
    if sin_cargo > 0:
        alertas.append({
            "nivel": "info",
            "codigo": "sin_cargo",
            "titulo": "Empleados sin cargo",
            "total": sin_cargo,
            "descripcion": f"{sin_cargo} empleado(s) no tienen cargo asignado.",
        })
    if periodos_abiertos > 0:
        alertas.append({
            "nivel": "warning",
            "codigo": "periodos_abiertos",
            "titulo": "Periodos de nómina sin cerrar",
            "total": periodos_abiertos,
            "descripcion": f"{periodos_abiertos} periodo(s) siguen abiertos o sin cerrar.",
        })
    if solicitudes_pendientes > 0:
        alertas.append({
            "nivel": "warning",
            "codigo": "solicitudes_pendientes",
            "titulo": "Solicitudes de ausencia pendientes",
            "total": solicitudes_pendientes,
            "descripcion": f"{solicitudes_pendientes} solicitud(es) esperan aprobación.",
        })
    if incidencias_pendientes > 0:
        alertas.append({
            "nivel": "warning",
            "codigo": "incidencias_pendientes",
            "titulo": "Incidencias de nómina pendientes",
            "total": incidencias_pendientes,
            "descripcion": f"{incidencias_pendientes} incidencia(s) esperan aprobación.",
        })

    return {
        "total": len(alertas),
        "items": alertas,
    }


# ═══════════════════════════════════════════════════════════
#  BLOQUE 5 — ACTIVIDAD RECIENTE (auditoría)
# ═══════════════════════════════════════════════════════════

def kpis_actividad_reciente(empresa_id=None, limit=10):
    """
    Últimos cambios registrados en auditoría.
    """
    try:
        from rrhh.auditoria.models import Auditoria
    except ImportError:
        return {"items": [], "total": 0, "error": "Módulo de auditoría no disponible"}

    qs = Auditoria.objects.all().order_by("-fecha")
    if empresa_id:
        qs = qs.filter(Q(empresa_id=empresa_id) | Q(empresa_id__isnull=True))

    qs = qs[:limit]

    items = []
    for a in qs:
        # Intentar obtener el nombre de la tabla legible
        tabla_display = a.tabla.replace("rrhh_", "").replace("_", " ").title()

        items.append({
            "id": a.id,
            "fecha": a.fecha.isoformat() if hasattr(a, "fecha") else None,
            "usuario": (
                a.usuario.get_full_name() or a.usuario.username
                if hasattr(a, "usuario") and a.usuario else "Sistema"
            ),
            "accion": getattr(a, "accion", ""),
            "accion_display": a.get_accion_display() if hasattr(a, "get_accion_display") else getattr(a, "accion", ""),
            "tabla": a.tabla,
            "tabla_display": tabla_display,
            "registro_id": a.registro_id,
            "registro_repr": getattr(a, "registro_repr", "") or "",
            "descripcion": getattr(a, "descripcion", "") or "",
        })

    return {
        "total": len(items),
        "items": items,
    }


# ═══════════════════════════════════════════════════════════
#  BLOQUE 6 — PRÓXIMOS CUMPLEAÑOS / ANIVERSARIOS
# ═══════════════════════════════════════════════════════════

def kpis_proximos_eventos(empresa_id=None, dias=30):
    """
    Cumpleaños y aniversarios laborales en los próximos N días.
    """
    hoy = timezone.now().date()
    limite = hoy + timedelta(days=dias)

    qs = _empleados_qs(empresa_id).filter(estatus="activo")

    cumpleanios = []
    aniversarios = []

    for emp in qs:
        if emp.fecha_nacimiento:
            try:
                cumple_este_anio = emp.fecha_nacimiento.replace(year=hoy.year)
            except ValueError:
                cumple_este_anio = emp.fecha_nacimiento.replace(year=hoy.year, day=28)

            if cumple_este_anio < hoy:
                try:
                    cumple_este_anio = emp.fecha_nacimiento.replace(year=hoy.year + 1)
                except ValueError:
                    cumple_este_anio = emp.fecha_nacimiento.replace(year=hoy.year + 1, day=28)

            if hoy <= cumple_este_anio <= limite:
                cumpleanios.append({
                    "empleado_id": emp.id,
                    "empleado": emp.nombre_completo,
                    "fecha": cumple_este_anio.isoformat(),
                    "dias_faltantes": (cumple_este_anio - hoy).days,
                })

        if emp.fecha_ingreso:
            try:
                aniv_este_anio = emp.fecha_ingreso.replace(year=hoy.year)
            except ValueError:
                aniv_este_anio = emp.fecha_ingreso.replace(year=hoy.year, day=28)

            if aniv_este_anio < hoy:
                try:
                    aniv_este_anio = emp.fecha_ingreso.replace(year=hoy.year + 1)
                except ValueError:
                    aniv_este_anio = emp.fecha_ingreso.replace(year=hoy.year + 1, day=28)

            if hoy <= aniv_este_anio <= limite:
                anios = aniv_este_anio.year - emp.fecha_ingreso.year
                aniversarios.append({
                    "empleado_id": emp.id,
                    "empleado": emp.nombre_completo,
                    "fecha": aniv_este_anio.isoformat(),
                    "anios": anios,
                    "dias_faltantes": (aniv_este_anio - hoy).days,
                })

    cumpleanios.sort(key=lambda x: x["dias_faltantes"])
    aniversarios.sort(key=lambda x: x["dias_faltantes"])

    return {
        "dias_ventana": dias,
        "cumpleanios": cumpleanios,
        "aniversarios": aniversarios,
    }


# ═══════════════════════════════════════════════════════════
#  ORQUESTADOR
# ═══════════════════════════════════════════════════════════

def dashboard_completo(empresa_id=None, meses=12):
    """
    Devuelve el payload completo del dashboard.

    Args:
        empresa_id: ID de empresa (None = todas)
        meses: Número de meses para la evolución de nómina (default 12)
    """
    return {
        "generado_at": timezone.now().isoformat(),
        "empresa_id": empresa_id,
        "meses_evolucion": meses,
        "headcount": kpis_headcount(empresa_id),
        "headcount_por_departamento": kpis_headcount_por_departamento(empresa_id),
        "headcount_por_cargo": kpis_headcount_por_cargo(empresa_id),
        "nomina": {
            "ultimo_periodo": kpis_nomina_ultimo_periodo(empresa_id),
            "evolucion": kpis_nomina_evolucion(empresa_id, meses=meses),
            "por_departamento": kpis_nomina_por_departamento(empresa_id),
        },
        "ausencias": {
            "resumen": kpis_ausencias_resumen(empresa_id),
            "saldos_vacaciones": kpis_saldos_vacaciones(empresa_id),
        },
        "alertas": kpis_alertas(empresa_id),
        "actividad_reciente": kpis_actividad_reciente(empresa_id, limit=10),
        "proximos_eventos": kpis_proximos_eventos(empresa_id, dias=30),
    }