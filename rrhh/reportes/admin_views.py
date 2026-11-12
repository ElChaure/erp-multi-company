"""
Vistas de reportes dentro del admin de Django.

Permiten ver, filtrar y descargar reportes en PDF/Excel desde /admin/reportes/.
"""
from datetime import datetime
from datetime import date
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render

from ..models import Empresa
from ..auditoria.models import Auditoria

from . import maestros_reportes, nomina_reportes
from ..ausencias import reportes as reportes_ausencias
from ..auditoria import reportes as reportes_auditoria
from .exportadores.excel import generar_excel
from .exportadores.pdf import generar_pdf
from .exportadores.columnas import (
    COLUMNAS_EMPRESAS, COLUMNAS_SEDES, COLUMNAS_DEPARTAMENTOS,
    COLUMNAS_CARGOS, COLUMNAS_EMPLEADOS, COLUMNAS_CONCEPTOS,
    COLUMNAS_PARAMETROS, COLUMNAS_INCIDENCIAS,
    COLUMNAS_COSTO_DEPARTAMENTO, COLUMNAS_COSTO_CARGO,
    COLUMNAS_RETENCIONES_ISLR, COLUMNAS_APORTES_ENTES,
    COLUMNAS_RESUMEN_PERIODOS,
    COLUMNAS_SALDOS_VACACIONES,
    COLUMNAS_SOLICITUDES_AUSENCIA,
    COLUMNAS_PROXIMAS_AUSENCIAS,
    COLUMNAS_AUSENCIAS_DEPARTAMENTO,
    COLUMNAS_AUSENCIAS_TIPO,
    COLUMNAS_AUDITORIA,
    COLUMNAS_AUDITORIA_USUARIO,
    COLUMNAS_AUDITORIA_TABLA,
    COLUMNAS_AUDITORIA_ACCION,
    COLUMNAS_AUDITORIA_DIARIA,
)


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _get_empresa(request):
    """Obtiene la empresa del usuario o la primera si es superadmin."""
    user = request.user

    if hasattr(user, "perfil") and user.perfil.empresa:
        return user.perfil.empresa

    if user.is_superuser:
        # Superadmin: puede elegir empresa
        empresa_id = request.GET.get("empresa_id")
        if empresa_id:
            return Empresa.objects.filter(id=empresa_id).first()
        return Empresa.objects.first()

    return None


def _get_int(request, key, default=None):
    """Lee un int del GET."""
    val = request.GET.get(key)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _get_bool(request, key):
    """Lee un bool del GET."""
    val = request.GET.get(key)
    if val is None or val == "":
        return None
    return val.lower() in ("true", "1", "yes", "si", "sí")


def _descargar_excel(titulo, columnas, datos, metadata=None):
    """Genera la descarga de Excel."""
    archivo = generar_excel(titulo, columnas, datos, metadata=metadata)
    response = HttpResponse(
        archivo,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    filename = f"{titulo.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _descargar_pdf(titulo, columnas, datos, empresa=None, metadata=None, orientacion="portrait"):
    """Genera la descarga de PDF."""
    archivo = generar_pdf(
        titulo=titulo,
        columnas=columnas,
        datos=datos,
        empresa=empresa,
        metadata=metadata,
        orientacion=orientacion,
    )
    response = HttpResponse(archivo, content_type="application/pdf")
    filename = f"{titulo.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response


def _metadata_para_pdf(request, empresa):
    """Construye metadata para mostrar en el PDF."""
    meta = {}
    if empresa:
        meta["Empresa"] = empresa.razon_social
    for key, value in request.GET.items():
        if key in ("formato", "empresa_id") or not value:
            continue
        label = key.replace("_", " ").title()
        meta[label] = value
    meta["Generado"] = datetime.now().strftime("%d/%m/%Y %H:%M")
    return meta


# ═══════════════════════════════════════════════════════════
#  ÍNDICE
# ═══════════════════════════════════════════════════════════

@staff_member_required
def reportes_index(request):
    """Página principal de reportes."""
    return render(request, "admin/reportes_index.html")


# ═══════════════════════════════════════════════════════════
#  MAESTROS
# ═══════════════════════════════════════════════════════════

@staff_member_required
def reporte_empresas(request):
    empresa_actual = _get_empresa(request)
    tipo = request.GET.get("tipo") or None
    activa = _get_bool(request, "activa")

    datos = maestros_reportes.reporte_empresas(
        tipo=tipo,
        activa=activa,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Empresas", COLUMNAS_EMPRESAS, datos, meta)
        return _descargar_pdf("Empresas", COLUMNAS_EMPRESAS, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Empresas",
        "descripcion": "Listado maestro de empresas",
        "columnas": COLUMNAS_EMPRESAS,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "tipo": tipo,
            "activa": activa,
        },
        "url_actual": "/admin/reportes/empresas/",
    })


@staff_member_required
def reporte_sedes(request):
    empresa_actual = _get_empresa(request)
    sede_id = _get_int(request, "sede_id")
    tipo = request.GET.get("tipo") or None
    activa = _get_bool(request, "activa")

    datos = maestros_reportes.reporte_sedes(
        empresa_id=empresa_actual.id if empresa_actual else _get_int(request, "empresa_id"),
        tipo=tipo,
        activa=activa,
        sede_id=sede_id,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Sedes", COLUMNAS_SEDES, datos, meta)
        return _descargar_pdf("Sedes", COLUMNAS_SEDES, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Sedes",
        "descripcion": "Listado maestro de sedes",
        "columnas": COLUMNAS_SEDES,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "sede_id": sede_id,
            "tipo": tipo,
            "activa": activa,
        },
        "url_actual": "/admin/reportes/sedes/",
    })


@staff_member_required
def reporte_departamentos(request):
    empresa_actual = _get_empresa(request)
    activo = _get_bool(request, "activo")

    datos = maestros_reportes.reporte_departamentos(
        empresa_id=empresa_actual.id if empresa_actual else _get_int(request, "empresa_id"),
        activo=activo,
        padre_id=_get_int(request, "padre_id"),
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Departamentos", COLUMNAS_DEPARTAMENTOS, datos, meta)
        return _descargar_pdf("Departamentos", COLUMNAS_DEPARTAMENTOS, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Departamentos",
        "descripcion": "Listado maestro de departamentos",
        "columnas": COLUMNAS_DEPARTAMENTOS,
        "datos": datos,
        "total": len(datos),
        "filtros": {"activo": activo},
        "url_actual": "/admin/reportes/departamentos/",
    })


@staff_member_required
def reporte_cargos(request):
    empresa_actual = _get_empresa(request)
    activo = _get_bool(request, "activo")

    datos = maestros_reportes.reporte_cargos(
        activo=activo,
        cargo_id=_get_int(request, "cargo_id"),
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Cargos", COLUMNAS_CARGOS, datos, meta)
        return _descargar_pdf("Cargos", COLUMNAS_CARGOS, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Cargos",
        "descripcion": "Listado maestro de cargos",
        "columnas": COLUMNAS_CARGOS,
        "datos": datos,
        "total": len(datos),
        "filtros": {"activo": activo},
        "url_actual": "/admin/reportes/cargos/",
    })


@staff_member_required
def reporte_empleados(request):
    empresa_actual = _get_empresa(request)

    # Filtros
    estatus_raw = request.GET.get("estatus") or None
    estatus = estatus_raw.split(",") if estatus_raw else None

    datos = maestros_reportes.reporte_empleados(
        empresa_id=empresa_actual.id if empresa_actual else _get_int(request, "empresa_id"),
        estatus=estatus,
        departamento_id=_get_int(request, "departamento_id"),
        cargo_id=_get_int(request, "cargo_id"),
        sede_id=_get_int(request, "sede_id"),
        nacionalidad=request.GET.get("nacionalidad") or None,
        tipo_contrato=request.GET.get("tipo_contrato") or None,
        empleado_id=_get_int(request, "empleado_id"),
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Empleados", COLUMNAS_EMPLEADOS, datos, meta)
        return _descargar_pdf("Empleados", COLUMNAS_EMPLEADOS, datos, empresa_actual, meta,
                              orientacion="landscape")

    # Para los filtros de UI
    from ..models import Departamento, Cargo, Sede
    return render(request, "admin/reporte_base.html", {
        "titulo": "Empleados",
        "descripcion": "Listado maestro de empleados",
        "columnas": COLUMNAS_EMPLEADOS,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "estatus": estatus_raw,
            "departamento_id": _get_int(request, "departamento_id"),
            "cargo_id": _get_int(request, "cargo_id"),
            "sede_id": _get_int(request, "sede_id"),
            "nacionalidad": request.GET.get("nacionalidad") or "",
            "tipo_contrato": request.GET.get("tipo_contrato") or "",
        },
        "departamentos": Departamento.objects.filter(activo=True).order_by("nombre"),
        "cargos": Cargo.objects.filter(activo=True).order_by("nombre"),
        "sedes": Sede.objects.filter(activa=True).order_by("nombre"),
        "url_actual": "/admin/reportes/empleados/",
        "orientacion": "landscape",
    })


@staff_member_required
def reporte_conceptos(request):
    empresa_actual = _get_empresa(request)
    activo = _get_bool(request, "activo")

    datos = maestros_reportes.reporte_conceptos(
        empresa_id=empresa_actual.id if empresa_actual else None,
        tipo=request.GET.get("tipo") or None,
        activo=activo,
        naturaleza=request.GET.get("naturaleza") or None,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Conceptos de Nómina", COLUMNAS_CONCEPTOS, datos, meta)
        return _descargar_pdf("Conceptos de Nómina", COLUMNAS_CONCEPTOS, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Conceptos de Nómina",
        "descripcion": "Listado maestro de conceptos",
        "columnas": COLUMNAS_CONCEPTOS,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "tipo": request.GET.get("tipo") or "",
            "naturaleza": request.GET.get("naturaleza") or "",
            "activo": activo,
        },
        "url_actual": "/admin/reportes/conceptos/",
    })


@staff_member_required
def reporte_parametros(request):
    empresa_actual = _get_empresa(request)
    activo = _get_bool(request, "activo")

    datos = maestros_reportes.reporte_parametros(
        empresa_id=empresa_actual.id if empresa_actual else None,
        anio=_get_int(request, "anio"),
        activo=activo,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Parámetros de Nómina", COLUMNAS_PARAMETROS, datos, meta)
        return _descargar_pdf("Parámetros de Nómina", COLUMNAS_PARAMETROS, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Parámetros de Nómina",
        "descripcion": "Configuración por empresa y año",
        "columnas": COLUMNAS_PARAMETROS,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "anio": _get_int(request, "anio"),
            "activo": activo,
        },
        "url_actual": "/admin/reportes/parametros/",
        "orientacion": "landscape",
    })


@staff_member_required
def reporte_incidencias(request):
    empresa_actual = _get_empresa(request)
    tipo_raw = request.GET.get("tipo") or None
    tipo = tipo_raw.split(",") if tipo_raw else None
    estatus_raw = request.GET.get("estatus") or None
    estatus = estatus_raw.split(",") if estatus_raw else None

    fecha_desde = request.GET.get("fecha_desde") or None
    fecha_hasta = request.GET.get("fecha_hasta") or None

    from datetime import datetime as dt
    if fecha_desde:
        try:
            fecha_desde = dt.strptime(fecha_desde, "%Y-%m-%d").date()
        except ValueError:
            fecha_desde = None
    if fecha_hasta:
        try:
            fecha_hasta = dt.strptime(fecha_hasta, "%Y-%m-%d").date()
        except ValueError:
            fecha_hasta = None

    datos = maestros_reportes.reporte_incidencias(
        empresa_id=empresa_actual.id if empresa_actual else None,
        tipo=tipo,
        estatus=estatus,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Incidencias", COLUMNAS_INCIDENCIAS, datos, meta)
        return _descargar_pdf("Incidencias", COLUMNAS_INCIDENCIAS, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Incidencias",
        "descripcion": "Registro de incidencias de nómina",
        "columnas": COLUMNAS_INCIDENCIAS,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "tipo": tipo_raw or "",
            "estatus": estatus_raw or "",
            "fecha_desde": fecha_desde.isoformat() if fecha_desde else "",
            "fecha_hasta": fecha_hasta.isoformat() if fecha_hasta else "",
        },
        "url_actual": "/admin/reportes/incidencias/",
        "orientacion": "landscape",
    })


# ═══════════════════════════════════════════════════════════
#  NÓMINA
# ═══════════════════════════════════════════════════════════

@staff_member_required
def reporte_costo_departamento(request):
    empresa_actual = _get_empresa(request)

    datos = nomina_reportes.costo_por_departamento(
        empresa_id=empresa_actual.id if empresa_actual else _get_int(request, "empresa_id"),
        fecha_desde=_parse_fecha(request.GET.get("fecha_desde")),
        fecha_hasta=_parse_fecha(request.GET.get("fecha_hasta")),
        estatus=request.GET.get("estatus") or None,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Costo por Departamento", COLUMNAS_COSTO_DEPARTAMENTO, datos, meta)
        return _descargar_pdf("Costo por Departamento", COLUMNAS_COSTO_DEPARTAMENTO, datos, empresa_actual, meta,
                              orientacion="landscape")

    return render(request, "admin/reporte_base.html", {
        "titulo": "Costo por Departamento",
        "descripcion": "Costos de nómina agrupados por departamento",
        "columnas": COLUMNAS_COSTO_DEPARTAMENTO,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "fecha_desde": request.GET.get("fecha_desde") or "",
            "fecha_hasta": request.GET.get("fecha_hasta") or "",
            "estatus": request.GET.get("estatus") or "",
        },
        "url_actual": "/admin/reportes/nomina/costo-departamento/",
        "orientacion": "landscape",
    })


@staff_member_required
def reporte_costo_cargo(request):
    empresa_actual = _get_empresa(request)

    datos = nomina_reportes.costo_por_cargo(
        empresa_id=empresa_actual.id if empresa_actual else _get_int(request, "empresa_id"),
        fecha_desde=_parse_fecha(request.GET.get("fecha_desde")),
        fecha_hasta=_parse_fecha(request.GET.get("fecha_hasta")),
        estatus=request.GET.get("estatus") or None,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Costo por Cargo", COLUMNAS_COSTO_CARGO, datos, meta)
        return _descargar_pdf("Costo por Cargo", COLUMNAS_COSTO_CARGO, datos, empresa_actual, meta,
                              orientacion="landscape")

    return render(request, "admin/reporte_base.html", {
        "titulo": "Costo por Cargo",
        "descripcion": "Costos de nómina agrupados por cargo",
        "columnas": COLUMNAS_COSTO_CARGO,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "fecha_desde": request.GET.get("fecha_desde") or "",
            "fecha_hasta": request.GET.get("fecha_hasta") or "",
            "estatus": request.GET.get("estatus") or "",
        },
        "url_actual": "/admin/reportes/nomina/costo-cargo/",
        "orientacion": "landscape",
    })


@staff_member_required
def reporte_retenciones_islr(request):
    empresa_actual = _get_empresa(request)

    datos = nomina_reportes.retenciones_islr(
        empresa_id=empresa_actual.id if empresa_actual else _get_int(request, "empresa_id"),
        fecha_desde=_parse_fecha(request.GET.get("fecha_desde")),
        fecha_hasta=_parse_fecha(request.GET.get("fecha_hasta")),
        estatus=request.GET.get("estatus") or None,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Retenciones ISLR", COLUMNAS_RETENCIONES_ISLR, datos, meta)
        return _descargar_pdf("Retenciones ISLR", COLUMNAS_RETENCIONES_ISLR, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Retenciones ISLR",
        "descripcion": "Retenciones de ISLR por empleado",
        "columnas": COLUMNAS_RETENCIONES_ISLR,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "fecha_desde": request.GET.get("fecha_desde") or "",
            "fecha_hasta": request.GET.get("fecha_hasta") or "",
            "estatus": request.GET.get("estatus") or "",
        },
        "url_actual": "/admin/reportes/nomina/retenciones-islr/",
    })


@staff_member_required
def reporte_aportes_entes(request):
    empresa_actual = _get_empresa(request)

    resultado = nomina_reportes.aportes_a_entes(
        empresa_id=empresa_actual.id if empresa_actual else _get_int(request, "empresa_id"),
        fecha_desde=_parse_fecha(request.GET.get("fecha_desde")),
        fecha_hasta=_parse_fecha(request.GET.get("fecha_hasta")),
        estatus=request.GET.get("estatus") or None,
    )

    datos = resultado["obreros"] + resultado["patronales"]

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total obreros"] = f"Bs. {resultado['total_obreros']:,.2f}"
        meta["Total patronales"] = f"Bs. {resultado['total_patronales']:,.2f}"
        if formato == "xlsx":
            return _descargar_excel("Aportes a Entes", COLUMNAS_APORTES_ENTES, datos, meta)
        return _descargar_pdf("Aportes a Entes", COLUMNAS_APORTES_ENTES, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Aportes a Entes",
        "descripcion": "Aportes obreros y patronales (IVSS, RPE, BANAVIH, INCES, LOPCYMAT)",
        "columnas": COLUMNAS_APORTES_ENTES,
        "datos": datos,
        "total": len(datos),
        "extra": {
            "Total obreros": f"Bs. {resultado['total_obreros']:,.2f}",
            "Total patronales": f"Bs. {resultado['total_patronales']:,.2f}",
            "Total general": f"Bs. {resultado['total_general']:,.2f}",
        },
        "filtros": {
            "fecha_desde": request.GET.get("fecha_desde") or "",
            "fecha_hasta": request.GET.get("fecha_hasta") or "",
            "estatus": request.GET.get("estatus") or "",
        },
        "url_actual": "/admin/reportes/nomina/aportes-entes/",
    })


@staff_member_required
def reporte_resumen_periodos(request):
    empresa_actual = _get_empresa(request)

    datos = nomina_reportes.resumen_por_periodo(
        empresa_id=empresa_actual.id if empresa_actual else _get_int(request, "empresa_id"),
        fecha_desde=_parse_fecha(request.GET.get("fecha_desde")),
        fecha_hasta=_parse_fecha(request.GET.get("fecha_hasta")),
        estatus=request.GET.get("estatus") or None,
        tipo=request.GET.get("tipo") or None,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Resumen de Periodos", COLUMNAS_RESUMEN_PERIODOS, datos, meta)
        return _descargar_pdf("Resumen de Periodos", COLUMNAS_RESUMEN_PERIODOS, datos, empresa_actual, meta,
                              orientacion="landscape")

    return render(request, "admin/reporte_base.html", {
        "titulo": "Resumen de Periodos",
        "descripcion": "Totales por periodo de nómina",
        "columnas": COLUMNAS_RESUMEN_PERIODOS,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "fecha_desde": request.GET.get("fecha_desde") or "",
            "fecha_hasta": request.GET.get("fecha_hasta") or "",
            "estatus": request.GET.get("estatus") or "",
            "tipo": request.GET.get("tipo") or "",
        },
        "url_actual": "/admin/reportes/nomina/resumen-periodos/",
        "orientacion": "landscape",
    })

# ═══════════════════════════════════════════════════════════
#  AUSENCIAS
# ═══════════════════════════════════════════════════════════

@staff_member_required
def reporte_saldos_vacaciones(request):
    empresa_actual = _get_empresa(request)
    anio = _get_int(request, "anio") or date.today().year

    datos = reportes_ausencias.reporte_saldos_vacaciones(
        empresa_id=empresa_actual.id if empresa_actual else None,
        anio=anio,
        departamento_id=_get_int(request, "departamento_id"),
        solo_con_saldo=_get_bool(request, "solo_con_saldo") or False,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Saldos de Vacaciones", COLUMNAS_SALDOS_VACACIONES, datos, meta)
        return _descargar_pdf("Saldos de Vacaciones", COLUMNAS_SALDOS_VACACIONES, datos, empresa_actual, meta,
                              orientacion="landscape")

    from ..models import Departamento
    return render(request, "admin/reporte_base.html", {
        "titulo": "Saldos de Vacaciones",
        "descripcion": f"Año {anio}",
        "columnas": COLUMNAS_SALDOS_VACACIONES,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "anio": anio,
            "departamento_id": _get_int(request, "departamento_id"),
            "solo_con_saldo": _get_bool(request, "solo_con_saldo"),
        },
        "departamentos": Departamento.objects.filter(
            empresa=empresa_actual, activo=True,
        ).order_by("nombre") if empresa_actual else [],
        "url_actual": "/admin/reportes/ausencias/saldos/",
        "orientacion": "landscape",
    })


@staff_member_required
def reporte_solicitudes_ausencia(request):
    empresa_actual = _get_empresa(request)

    fecha_desde = _parse_fecha(request.GET.get("fecha_desde"))
    fecha_hasta = _parse_fecha(request.GET.get("fecha_hasta"))

    estatus_raw = request.GET.get("estatus") or None
    estatus = estatus_raw.split(",") if estatus_raw else None

    datos = reportes_ausencias.reporte_solicitudes(
        empresa_id=empresa_actual.id if empresa_actual else None,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estatus=estatus,
        tipo_id=_get_int(request, "tipo_id"),
        departamento_id=_get_int(request, "departamento_id"),
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Solicitudes de Ausencia", COLUMNAS_SOLICITUDES_AUSENCIA, datos, meta)
        return _descargar_pdf("Solicitudes de Ausencia", COLUMNAS_SOLICITUDES_AUSENCIA, datos, empresa_actual, meta,
                              orientacion="landscape")

    from ..models import Departamento, TipoAusencia
    return render(request, "admin/reporte_base.html", {
        "titulo": "Solicitudes de Ausencia",
        "descripcion": "Listado de solicitudes en el rango seleccionado",
        "columnas": COLUMNAS_SOLICITUDES_AUSENCIA,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "fecha_desde": request.GET.get("fecha_desde") or "",
            "fecha_hasta": request.GET.get("fecha_hasta") or "",
            "estatus": estatus_raw or "",
            "tipo_id": _get_int(request, "tipo_id"),
            "departamento_id": _get_int(request, "departamento_id"),
        },
        "departamentos": Departamento.objects.filter(
            empresa=empresa_actual, activo=True,
        ).order_by("nombre") if empresa_actual else [],
        "tipos_ausencia": TipoAusencia.objects.filter(
            empresa=empresa_actual, activo=True,
        ).order_by("nombre") if empresa_actual else [],
        "url_actual": "/admin/reportes/ausencias/solicitudes/",
        "orientacion": "landscape",
    })


@staff_member_required
def reporte_proximas_ausencias(request):
    empresa_actual = _get_empresa(request)
    dias_adelante = _get_int(request, "dias_adelante") or 30

    datos = reportes_ausencias.reporte_proximas_ausencias(
        empresa_id=empresa_actual.id if empresa_actual else None,
        dias_adelante=dias_adelante,
        departamento_id=_get_int(request, "departamento_id"),
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Próximas Ausencias", COLUMNAS_PROXIMAS_AUSENCIAS, datos, meta)
        return _descargar_pdf("Próximas Ausencias", COLUMNAS_PROXIMAS_AUSENCIAS, datos, empresa_actual, meta)

    from ..models import Departamento
    return render(request, "admin/reporte_base.html", {
        "titulo": "Próximas Ausencias",
        "descripcion": f"Ausencias programadas en los próximos {dias_adelante} días",
        "columnas": COLUMNAS_PROXIMAS_AUSENCIAS,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "dias_adelante": dias_adelante,
            "departamento_id": _get_int(request, "departamento_id"),
        },
        "departamentos": Departamento.objects.filter(
            empresa=empresa_actual, activo=True,
        ).order_by("nombre") if empresa_actual else [],
        "url_actual": "/admin/reportes/ausencias/proximas/",
    })


@staff_member_required
def reporte_ausencias_departamento(request):
    empresa_actual = _get_empresa(request)
    anio = _get_int(request, "anio") or date.today().year

    datos = reportes_ausencias.reporte_ausencias_por_departamento(
        empresa_id=empresa_actual.id if empresa_actual else None,
        anio=anio,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Ausencias por Departamento", COLUMNAS_AUSENCIAS_DEPARTAMENTO, datos, meta)
        return _descargar_pdf("Ausencias por Departamento", COLUMNAS_AUSENCIAS_DEPARTAMENTO, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Ausencias por Departamento",
        "descripcion": f"Año {anio}",
        "columnas": COLUMNAS_AUSENCIAS_DEPARTAMENTO,
        "datos": datos,
        "total": len(datos),
        "filtros": {"anio": anio},
        "url_actual": "/admin/reportes/ausencias/departamento/",
    })


@staff_member_required
def reporte_ausencias_tipo(request):
    empresa_actual = _get_empresa(request)
    anio = _get_int(request, "anio") or date.today().year

    datos = reportes_ausencias.reporte_ausencias_por_tipo(
        empresa_id=empresa_actual.id if empresa_actual else None,
        anio=anio,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Ausencias por Tipo", COLUMNAS_AUSENCIAS_TIPO, datos, meta)
        return _descargar_pdf("Ausencias por Tipo", COLUMNAS_AUSENCIAS_TIPO, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Ausencias por Tipo",
        "descripcion": f"Año {anio}",
        "columnas": COLUMNAS_AUSENCIAS_TIPO,
        "datos": datos,
        "total": len(datos),
        "filtros": {"anio": anio},
        "url_actual": "/admin/reportes/ausencias/tipo/",
    })


# ═══════════════════════════════════════════════════════════
#  HELPERS (reutilizados)
# ═══════════════════════════════════════════════════════════

def _parse_fecha(valor):
    """Convierte string YYYY-MM-DD a date."""
    if not valor:
        return None
    from datetime import datetime as dt
    try:
        return dt.strptime(valor, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
        


# ═══════════════════════════════════════════════════════════
#  AUDITORÍA
# ═══════════════════════════════════════════════════════════

@staff_member_required
def reporte_auditoria(request):
    empresa_actual = _get_empresa(request)

    fecha_desde = _parse_fecha(request.GET.get("fecha_desde"))
    fecha_hasta = _parse_fecha(request.GET.get("fecha_hasta"))

    datos = reportes_auditoria.reporte_auditoria(
        empresa_id=empresa_actual.id if empresa_actual else _get_int(request, "empresa_id"),
        usuario_id=_get_int(request, "usuario_id"),
        tabla=request.GET.get("tabla") or None,
        accion=request.GET.get("accion") or None,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        search=request.GET.get("search") or None,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Auditoría", COLUMNAS_AUDITORIA, datos, meta)
        return _descargar_pdf("Auditoría", COLUMNAS_AUDITORIA, datos, empresa_actual, meta,
                              orientacion="landscape")

    from django.contrib.auth.models import User
    return render(request, "admin/reporte_base.html", {
        "titulo": "Auditoría del Sistema",
        "descripcion": "Historial de cambios, accesos y acciones",
        "columnas": COLUMNAS_AUDITORIA,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "fecha_desde": request.GET.get("fecha_desde") or "",
            "fecha_hasta": request.GET.get("fecha_hasta") or "",
            "accion": request.GET.get("accion") or "",
            "tabla": request.GET.get("tabla") or "",
            "search": request.GET.get("search") or "",
            "usuario_id": _get_int(request, "usuario_id"),
        },
        "usuarios_auditoria": User.objects.filter(is_active=True).order_by("username")[:100],
        "acciones_auditoria": Auditoria._meta.get_field("accion").choices,
        "tablas_auditoria": Auditoria.objects.values_list("tabla", flat=True).distinct().order_by("tabla"),
        "url_actual": "/admin/reportes/auditoria/",
        "orientacion": "landscape",
    })


@staff_member_required
def reporte_auditoria_por_usuario(request):
    empresa_actual = _get_empresa(request)

    fecha_desde = _parse_fecha(request.GET.get("fecha_desde"))
    fecha_hasta = _parse_fecha(request.GET.get("fecha_hasta"))

    datos = reportes_auditoria.reporte_por_usuario(
        empresa_id=empresa_actual.id if empresa_actual else None,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Auditoría por Usuario", COLUMNAS_AUDITORIA_USUARIO, datos, meta)
        return _descargar_pdf("Auditoría por Usuario", COLUMNAS_AUDITORIA_USUARIO, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Auditoría por Usuario",
        "descripcion": "Resumen de actividad por usuario",
        "columnas": COLUMNAS_AUDITORIA_USUARIO,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "fecha_desde": request.GET.get("fecha_desde") or "",
            "fecha_hasta": request.GET.get("fecha_hasta") or "",
        },
        "url_actual": "/admin/reportes/auditoria/por-usuario/",
    })


@staff_member_required
def reporte_auditoria_por_tabla(request):
    empresa_actual = _get_empresa(request)

    fecha_desde = _parse_fecha(request.GET.get("fecha_desde"))
    fecha_hasta = _parse_fecha(request.GET.get("fecha_hasta"))

    datos = reportes_auditoria.reporte_por_tabla(
        empresa_id=empresa_actual.id if empresa_actual else None,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Auditoría por Tabla", COLUMNAS_AUDITORIA_TABLA, datos, meta)
        return _descargar_pdf("Auditoría por Tabla", COLUMNAS_AUDITORIA_TABLA, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Auditoría por Tabla",
        "descripcion": "Resumen de cambios por tabla",
        "columnas": COLUMNAS_AUDITORIA_TABLA,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "fecha_desde": request.GET.get("fecha_desde") or "",
            "fecha_hasta": request.GET.get("fecha_hasta") or "",
        },
        "url_actual": "/admin/reportes/auditoria/por-tabla/",
    })


@staff_member_required
def reporte_auditoria_por_accion(request):
    empresa_actual = _get_empresa(request)

    fecha_desde = _parse_fecha(request.GET.get("fecha_desde"))
    fecha_hasta = _parse_fecha(request.GET.get("fecha_hasta"))

    datos = reportes_auditoria.reporte_por_accion(
        empresa_id=empresa_actual.id if empresa_actual else None,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Auditoría por Acción", COLUMNAS_AUDITORIA_ACCION, datos, meta)
        return _descargar_pdf("Auditoría por Acción", COLUMNAS_AUDITORIA_ACCION, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Auditoría por Acción",
        "descripcion": "Resumen de acciones realizadas",
        "columnas": COLUMNAS_AUDITORIA_ACCION,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "fecha_desde": request.GET.get("fecha_desde") or "",
            "fecha_hasta": request.GET.get("fecha_hasta") or "",
        },
        "url_actual": "/admin/reportes/auditoria/por-accion/",
    })


@staff_member_required
def reporte_auditoria_diaria(request):
    empresa_actual = _get_empresa(request)
    dias = _get_int(request, "dias") or 30

    datos = reportes_auditoria.reporte_actividad_diaria(
        empresa_id=empresa_actual.id if empresa_actual else None,
        dias=dias,
    )

    formato = request.GET.get("formato")
    if formato in ("pdf", "xlsx"):
        meta = _metadata_para_pdf(request, empresa_actual)
        meta["Total"] = len(datos)
        if formato == "xlsx":
            return _descargar_excel("Actividad Diaria", COLUMNAS_AUDITORIA_DIARIA, datos, meta)
        return _descargar_pdf("Actividad Diaria", COLUMNAS_AUDITORIA_DIARIA, datos, empresa_actual, meta)

    return render(request, "admin/reporte_base.html", {
        "titulo": "Actividad Diaria",
        "descripcion": f"Acciones en los últimos {dias} días",
        "columnas": COLUMNAS_AUDITORIA_DIARIA,
        "datos": datos,
        "total": len(datos),
        "filtros": {
            "dias": dias,
        },
        "url_actual": "/admin/reportes/auditoria/diaria/",
    })
    