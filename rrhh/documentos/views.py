"""
Vistas HTML para emisión de documentos formales.
"""

from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from rrhh.decorators import empleado_autenticado, solo_rrhh
from rrhh.models import Empleado
from .models import DocumentoEmitido
from .services import registrar_documento, registrar_descarga
from .generadores.constancia_trabajo import generar_constancia_pdf
from .generadores.planilla_arc import generar_arc_pdf


# ═══════════════════════════════════════════════════════════
# HELPERS DE PERMISOS
# ═══════════════════════════════════════════════════════════

def _puede_emitir(user, empleado):
    """
    Verifica si el usuario puede emitir documentos para este empleado.

    - superadmin/admin/rrhh: sí, siempre
    - manager: solo si el empleado es su subordinado directo
    - empleado: solo si es su propio empleado (vía CuentaEmpleado o Perfil)
    """
    if user.is_superuser:
        return True

    perfil = getattr(user, "perfil", None)
    if not perfil:
        return False

    # RRHH / admin
    if perfil.rol in ("superadmin", "admin", "rrhh"):
        return True

    # Manager: subordinado directo
    if perfil.rol == "manager":
        if perfil.empleado and empleado.jefe_id == perfil.empleado.id:
            return True
        return False

    # Empleado: es su propio empleado
    if perfil.rol == "empleado":
        if perfil.empleado_id == empleado.id:
            return True
        # O tiene CuentaEmpleado
        cuenta = getattr(user, "cuenta_empleado", None)
        if cuenta and cuenta.empleado_id == empleado.id:
            return True
        return False

    return False


def _empleado_visible(user, empleado_id):
    """Devuelve el empleado si el usuario puede verlo, o 404."""
    empleado = get_object_or_404(
        Empleado.objects.select_related("empresa", "cargo"),
        pk=empleado_id,
    )
    if not _puede_emitir(user, empleado):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("No tenés permiso para emitir documentos de este empleado.")
    return empleado


# ═══════════════════════════════════════════════════════════
# CONSTANCIA DE TRABAJO
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def constancia_form(request, empleado_id):
    """
    GET:  Muestra el formulario de emisión de constancia.
    POST: Registra y genera el PDF.
    """
    empleado = _empleado_visible(request.user, empleado_id)
    empresa = empleado.empresa

    if request.method == "POST":
        con_salario = request.POST.get("con_salario") == "on"
        destinatario = request.POST.get("destinatario", "").strip() or "A quien pueda interesar"
        ciudad = request.POST.get("ciudad", "").strip() or (empresa.ciudad or "")
        fecha_emision_str = request.POST.get("fecha_emision", "").strip()

        # Parsear fecha
        if fecha_emision_str:
            try:
                fecha_emision = date.fromisoformat(fecha_emision_str)
            except ValueError:
                fecha_emision = date.today()
        else:
            fecha_emision = date.today()

        # Registrar
        parametros = {
            "con_salario": con_salario,
            "destinatario": destinatario,
            "ciudad": ciudad,
            "fecha_emision": fecha_emision.isoformat(),
        }
        documento = registrar_documento(
            tipo="constancia_trabajo",
            empleado=empleado,
            usuario=request.user,
            parametros=parametros,
        )

        messages.success(
            request,
            f"Constancia emitida: {documento.numero_control}. Descargando PDF…"
        )
        return redirect("rrhh:documento_descargar", documento_id=documento.id)

    # GET: mostrar formulario
    context = {
        "empleado": empleado,
        "empresa": empresa,
        "hoy": date.today(),
    }
    return render(request, "documentos/constancia_form.html", context)


# ═══════════════════════════════════════════════════════════
# PLANILLA ARC
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def arc_form(request, empleado_id):
    """
    GET:  Muestra el formulario de emisión de ARC.
    POST: Registra y genera el PDF.
    """
    empleado = _empleado_visible(request.user, empleado_id)
    empresa = empleado.empresa

    if request.method == "POST":
        anio_fiscal_str = request.POST.get("anio_fiscal", "").strip()
        cargo_filtro = request.POST.get("cargo_filtro", "").strip() or None

        try:
            anio_fiscal = int(anio_fiscal_str)
        except (ValueError, TypeError):
            anio_fiscal = date.today().year

        parametros = {
            "anio_fiscal": anio_fiscal,
            "cargo_filtro": cargo_filtro,
        }
        documento = registrar_documento(
            tipo="arc",
            empleado=empleado,
            usuario=request.user,
            parametros=parametros,
        )

        messages.success(
            request,
            f"Planilla ARC emitida: {documento.numero_control}. Descargando PDF…"
        )
        return redirect("rrhh:documento_descargar", documento_id=documento.id)

    # GET: mostrar formulario
    anio_actual = date.today().year
    anios_disponibles = list(range(anio_actual, anio_actual - 5, -1))

    context = {
        "empleado": empleado,
        "empresa": empresa,
        "anios_disponibles": anios_disponibles,
        "anio_actual": anio_actual,
    }
    return render(request, "documentos/arc_form.html", context)


# ═══════════════════════════════════════════════════════════
# DESCARGA
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def documento_descargar(request, documento_id):
    """
    Regenera el PDF y lo devuelve como descarga.
    """
    documento = get_object_or_404(
        DocumentoEmitido.objects.select_related("empleado", "empresa"),
        pk=documento_id,
    )

    # Verificar permiso
    if not _puede_emitir(request.user, documento.empleado):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("No tenés permiso para descargar este documento.")

    # Generar PDF según tipo
    if documento.tipo == "constancia_trabajo":
        pdf_bytes = generar_constancia_pdf(documento)
        filename = f"constancia_{documento.numero_control}_{documento.empleado.numero_empleado}.pdf"
    elif documento.tipo == "arc":
        pdf_bytes = generar_arc_pdf(documento)
        anio = documento.parametros.get("anio_fiscal", documento.anio)
        filename = f"ARC_{anio}_{documento.empleado.numero_empleado}.pdf"
    else:
        messages.error(request, "Tipo de documento desconocido.")
        return redirect("rrhh:documento_lista")

    # Registrar descarga
    registrar_descarga(documento)

    # Devolver
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ═══════════════════════════════════════════════════════════
# LISTADO
# ═══════════════════════════════════════════════════════════

@solo_rrhh
def documento_lista(request):
    """Listado paginado de documentos emitidos."""
    qs = DocumentoEmitido.objects.select_related(
        "empleado", "empresa", "emitido_por"
    ).order_by("-emitido_at")

    # Filtros
    tipo = request.GET.get("tipo", "").strip()
    empleado_id = request.GET.get("empleado", "").strip()
    anio = request.GET.get("anio", "").strip()

    if tipo:
        qs = qs.filter(tipo=tipo)
    if empleado_id and empleado_id.isdigit():
        qs = qs.filter(empleado_id=int(empleado_id))
    if anio and anio.isdigit():
        qs = qs.filter(anio=int(anio))

    # KPIs
    total = qs.count()
    total_constancias = qs.filter(tipo="constancia_trabajo").count()
    total_arc = qs.filter(tipo="arc").count()

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_obj": page_obj,
        "total": total,
        "total_constancias": total_constancias,
        "total_arc": total_arc,
        "tipos": DocumentoEmitido.TIPO_CHOICES,
        "filtros": {
            "tipo": tipo,
            "empleado": empleado_id,
            "anio": anio,
        },
    }
    return render(request, "documentos/documento_lista.html", context)