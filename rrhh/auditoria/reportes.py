"""
Reportes del módulo de auditoría.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Count, Q

from .models import Auditoria


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _filtrar(qs, empresa_id=None, usuario_id=None, tabla=None, accion=None,
             fecha_desde=None, fecha_hasta=None, search=None):
    """Aplica filtros comunes al queryset."""
    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)
    if usuario_id:
        qs = qs.filter(usuario_id=usuario_id)
    if tabla:
        qs = qs.filter(tabla=tabla)
    if accion:
        if isinstance(accion, str):
            accion = [accion]
        qs = qs.filter(accion__in=accion)
    if fecha_desde:
        qs = qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        # Incluir todo el día
        qs = qs.filter(fecha__lte=datetime.combine(fecha_hasta, datetime.max.time()))
    if search:
        qs = qs.filter(
            Q(descripcion__icontains=search) |
            Q(registro_repr__icontains=search) |
            Q(tabla__icontains=search) |
            Q(usuario__username__icontains=search)
        )
    return qs


def _serializar_fila(aud):
    """Convierte una auditoría a dict para reportes."""
    return {
        "id": aud.id,
        "fecha": aud.fecha,
        "usuario": aud.usuario.username if aud.usuario else "—",
        "usuario_nombre": (
            aud.usuario.get_full_name() or aud.usuario.username
            if aud.usuario else "—"
        ),
        "accion": aud.accion,
        "accion_display": aud.get_accion_display(),
        "tabla": aud.tabla,
        "registro_id": aud.registro_id,
        "registro_repr": aud.registro_repr,
        "descripcion": aud.descripcion,
        "campos_modificados": aud.campos_modificados,
        "ip": str(aud.ip) if aud.ip else "",
        "url": aud.url,
        "metodo_http": aud.metodo_http,
    }


# ═══════════════════════════════════════════════════════════
#  1. LOG DE AUDITORÍA (con filtros)
# ═══════════════════════════════════════════════════════════

def reporte_auditoria(empresa_id=None, usuario_id=None, tabla=None,
                       accion=None, fecha_desde=None, fecha_hasta=None,
                       search=None, limite=5000):
    """
    Listado completo de auditorías con filtros.

    Returns:
        lista de dicts con cada entrada de auditoría.
    """
    qs = Auditoria.objects.select_related("usuario").all()
    qs = _filtrar(
        qs,
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        tabla=tabla,
        accion=accion,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        search=search,
    )
    qs = qs.order_by("-fecha")[:limite]
    return [_serializar_fila(aud) for aud in qs]


# ═══════════════════════════════════════════════════════════
#  2. RESUMEN POR USUARIO
# ═══════════════════════════════════════════════════════════

def reporte_por_usuario(empresa_id=None, fecha_desde=None, fecha_hasta=None):
    """
    Resumen de actividad por usuario.

    Returns:
        lista de dicts con:
            - usuario_id, usuario, nombre_completo
            - total_acciones
            - creaciones, actualizaciones, eliminaciones, logins
            - ultima_actividad
    """
    qs = Auditoria.objects.all()
    qs = _filtrar(
        qs,
        empresa_id=empresa_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    qs = qs.values(
        "usuario_id",
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
    ).annotate(
        total_acciones=Count("id"),
        creaciones=Count("id", filter=Q(accion="create")),
        actualizaciones=Count("id", filter=Q(accion="update")),
        eliminaciones=Count("id", filter=Q(accion="delete")),
        logins=Count("id", filter=Q(accion="login")),
    ).order_by("-total_acciones")

    resultado = []
    for row in qs:
        # Última actividad
        ultima = Auditoria.objects.filter(
            usuario_id=row["usuario_id"]
        ).order_by("-fecha").values_list("fecha", flat=True).first()

        nombre = f"{row['usuario__first_name']} {row['usuario__last_name']}".strip()
        resultado.append({
            "usuario_id": row["usuario_id"],
            "usuario": row["usuario__username"] or "—",
            "nombre_completo": nombre or row["usuario__username"] or "—",
            "total_acciones": row["total_acciones"],
            "creaciones": row["creaciones"],
            "actualizaciones": row["actualizaciones"],
            "eliminaciones": row["eliminaciones"],
            "logins": row["logins"],
            "ultima_actividad": ultima,
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  3. RESUMEN POR TABLA
# ═══════════════════════════════════════════════════════════

def reporte_por_tabla(empresa_id=None, fecha_desde=None, fecha_hasta=None):
    """
    Resumen de cambios por tabla.
    """
    qs = Auditoria.objects.all()
    qs = _filtrar(
        qs,
        empresa_id=empresa_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    qs = qs.values("tabla").annotate(
        total=Count("id"),
        creaciones=Count("id", filter=Q(accion="create")),
        actualizaciones=Count("id", filter=Q(accion="update")),
        eliminaciones=Count("id", filter=Q(accion="delete")),
    ).order_by("-total")

    return [
        {
            "tabla": row["tabla"],
            "total": row["total"],
            "creaciones": row["creaciones"],
            "actualizaciones": row["actualizaciones"],
            "eliminaciones": row["eliminaciones"],
        }
        for row in qs
    ]


# ═══════════════════════════════════════════════════════════
#  4. RESUMEN POR ACCIÓN
# ═══════════════════════════════════════════════════════════

def reporte_por_accion(empresa_id=None, fecha_desde=None, fecha_hasta=None):
    """Resumen de auditorías por tipo de acción."""
    qs = Auditoria.objects.all()
    qs = _filtrar(
        qs,
        empresa_id=empresa_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    qs = qs.values("accion").annotate(total=Count("id")).order_by("-total")

    return [
        {
            "accion": row["accion"],
            "accion_display": dict(Auditoria._meta.get_field("accion").choices).get(
                row["accion"], row["accion"]
            ),
            "total": row["total"],
        }
        for row in qs
    ]


# ═══════════════════════════════════════════════════════════
#  5. ACTIVIDAD DIARIA
# ═══════════════════════════════════════════════════════════

def reporte_actividad_diaria(empresa_id=None, dias=30):
    """
    Actividad diaria de los últimos N días.
    """
    desde = date.today() - timedelta(days=dias)
    qs = Auditoria.objects.filter(fecha__date__gte=desde)
    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)

    qs = qs.extra(
        select={"dia": "DATE(fecha)"}
    ).values("dia").annotate(total=Count("id")).order_by("dia")

    return [
        {
            "dia": row["dia"],
            "total": row["total"],
        }
        for row in qs
    ]


# ═══════════════════════════════════════════════════════════
#  6. CONSOLIDADO
# ═══════════════════════════════════════════════════════════

def reporte_consolidado(empresa_id=None, fecha_desde=None, fecha_hasta=None):
    """Resumen general de la auditoría."""
    qs = Auditoria.objects.all()
    qs = _filtrar(
        qs,
        empresa_id=empresa_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    return {
        "total_registros": qs.count(),
        "total_usuarios": qs.values("usuario_id").distinct().count(),
        "total_tablas": qs.values("tabla").distinct().count(),
        "creaciones": qs.filter(accion="create").count(),
        "actualizaciones": qs.filter(accion="update").count(),
        "eliminaciones": qs.filter(accion="delete").count(),
        "logins": qs.filter(accion="login").count(),
        "logins_fallidos": qs.filter(accion="login_failed").count(),
    }