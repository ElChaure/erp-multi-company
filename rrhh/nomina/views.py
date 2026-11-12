"""
Vistas HTML del módulo de Nómina.

Vistas:
    - periodo_lista         → Lista de periodos con filtros
    - periodo_detalle       → Detalle con acciones y nóminas por empleado
    - periodo_calcular      → POST para calcular
    - periodo_aprobar       → POST para aprobar
    - periodo_cerrar        → POST para cerrar
"""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from rrhh.decorators import empleado_autenticado, solo_rrhh
from rrhh.models import (
    PeriodoNomina,
    NominaEmpleado,
    Empresa,
    Empleado,
)

from .engine import calcular_periodo, NominaError


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _periodos_queryset(user):
    """
    Devuelve los periodos visibles para el usuario.
    - superadmin: todos
    - otros: solo los de su empresa
    """
    qs = PeriodoNomina.objects.select_related("empresa").all()

    if user.is_superuser:
        return qs

    if hasattr(user, "perfil") and user.perfil.tiene_acceso_global:
        return qs

    if hasattr(user, "perfil") and user.perfil.empresa:
        return qs.filter(empresa=user.perfil.empresa)

    return qs.none()


def _puede_gestionar(user):
    """Solo RRHH y superiores pueden calcular/aprobar/cerrar."""
    if user.is_superuser:
        return True
    perfil = getattr(user, "perfil", None)
    if not perfil:
        return False
    return perfil.rol in ("superadmin", "admin", "rrhh")


# ═══════════════════════════════════════════════════════════
#  LISTA
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def periodo_lista(request):
    """
    Listado de periodos de nómina con filtros:
    - año
    - tipo
    - estatus
    - empresa (solo superadmin)
    - búsqueda por número
    """
    qs = _periodos_queryset(request.user)

    # Filtros
    anio = request.GET.get("anio", "").strip()
    tipo = request.GET.get("tipo", "").strip()
    estatus = request.GET.get("estatus", "").strip()
    empresa_id = request.GET.get("empresa", "").strip()
    q = request.GET.get("q", "").strip()

    if anio:
        try:
            qs = qs.filter(anio=int(anio))
        except (ValueError, TypeError):
            pass

    if tipo:
        qs = qs.filter(tipo=tipo)

    if estatus:
        qs = qs.filter(estatus=estatus)

    if empresa_id and (request.user.is_superuser or request.user.perfil.tiene_acceso_global):
        try:
            qs = qs.filter(empresa_id=int(empresa_id))
        except (ValueError, TypeError):
            pass

    if q:
        qs = qs.filter(
            Q(numero_periodo__icontains=q)
            | Q(empresa__razon_social__icontains=q)
            | Q(empresa__nombre_comercial__icontains=q)
        )

    qs = qs.order_by("-anio", "-numero_periodo")

    # Paginación
    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Datos para los selects
    empresas = Empresa.objects.filter(activa=True).order_by("razon_social") \
        if (request.user.is_superuser or request.user.perfil.tiene_acceso_global) \
        else Empresa.objects.none()

    # Años disponibles (para el dropdown)
    anios_qs = _periodos_queryset(request.user).values_list("anio", flat=True).distinct().order_by("-anio")
    anios_disponibles = sorted(set(anios_qs), reverse=True)

    context = {
        "page_obj": page_obj,
        "total": qs.count(),
        "filtros": {
            "anio": anio,
            "tipo": tipo,
            "estatus": estatus,
            "empresa": empresa_id,
            "q": q,
        },
        "tipos": PeriodoNomina.TIPO_CHOICES,
        "estatus_choices": PeriodoNomina.ESTATUS_CHOICES,
        "empresas": empresas,
        "anios_disponibles": anios_disponibles,
        "puede_gestionar": _puede_gestionar(request.user),
    }
    return render(request, "nomina/periodo_lista.html", context)


# ═══════════════════════════════════════════════════════════
#  DETALLE
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def periodo_detalle(request, pk):
    """
    Detalle de un periodo con:
    - Totales generales
    - Lista de nóminas por empleado
    - Botones de acción (calcular, aprobar, cerrar)
    """
    periodo = get_object_or_404(
        _periodos_queryset(request.user).select_related("empresa"),
        pk=pk,
    )

    # Nóminas del periodo
    nominas = (
        NominaEmpleado.objects
        .filter(periodo=periodo)
        .select_related("empleado", "empleado__cargo", "empleado__departamento")
        .order_by("empleado__apellido_paterno", "empleado__nombre")
    )

    context = {
        "periodo": periodo,
        "nominas": nominas,
        "total_nominas": nominas.count(),
        "puede_gestionar": _puede_gestionar(request.user),
        # Flags de acción
        "puede_calcular": periodo.estatus in ("abierto", "calculado"),
        "puede_aprobar": periodo.estatus == "calculado",
        "puede_cerrar": periodo.estatus in ("aprobado", "pagado"),
    }
    return render(request, "nomina/periodo_detalle.html", context)


# ═══════════════════════════════════════════════════════════
#  ACCIONES (POST)
# ═══════════════════════════════════════════════════════════

@solo_rrhh
@require_POST
def periodo_calcular(request, pk):
    """Calcula el periodo. Sobrescribe nóminas previas."""
    periodo = get_object_or_404(
        _periodos_queryset(request.user),
        pk=pk,
    )

    if not periodo.puede_calcularse:
        messages.error(
            request,
            f"No se puede calcular un periodo en estado "
            f"'{periodo.get_estatus_display()}'.",
        )
        return redirect("rrhh:nomina_periodo_detalle", pk=periodo.pk)

    try:
        resultado = calcular_periodo(periodo, usuario=request.user)
        errores = resultado.get("errores", [])

        if errores:
            messages.warning(
                request,
                f"Periodo calculado con {len(errores)} advertencia(s). "
                f"Revisa el detalle.",
            )
        else:
            messages.success(
                request,
                f"Periodo calculado correctamente. "
                f"{resultado['empleados_procesados']} empleado(s) procesado(s).",
            )

    except NominaError as e:
        messages.error(request, f"Error al calcular: {e}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error inesperado: {e}")

    return redirect("rrhh:nomina_periodo_detalle", pk=periodo.pk)


@solo_rrhh
@require_POST
def periodo_aprobar(request, pk):
    """Aprueba un periodo calculado."""
    periodo = get_object_or_404(
        _periodos_queryset(request.user),
        pk=pk,
    )

    if periodo.estatus != "calculado":
        messages.error(
            request,
            f"Solo se pueden aprobar periodos calculados. "
            f"Estado actual: '{periodo.get_estatus_display()}'.",
        )
        return redirect("rrhh:nomina_periodo_detalle", pk=periodo.pk)

    periodo.estatus = "aprobado"
    periodo.aprobado_por = request.user
    periodo.aprobado_at = timezone.now()
    periodo.save(update_fields=["estatus", "aprobado_por", "aprobado_at", "updated_at"])

    messages.success(request, "Periodo aprobado correctamente.")
    return redirect("rrhh:nomina_periodo_detalle", pk=periodo.pk)


@solo_rrhh
@require_POST
def periodo_cerrar(request, pk):
    """Cierra un periodo. Ya no se puede modificar."""
    periodo = get_object_or_404(
        _periodos_queryset(request.user),
        pk=pk,
    )

    if not periodo.puede_cerrarse:
        messages.error(
            request,
            f"No se puede cerrar un periodo en estado "
            f"'{periodo.get_estatus_display()}'.",
        )
        return redirect("rrhh:nomina_periodo_detalle", pk=periodo.pk)

    periodo.estatus = "cerrado"
    periodo.cerrado_por = request.user
    periodo.cerrado_at = timezone.now()
    periodo.save(update_fields=["estatus", "cerrado_por", "cerrado_at", "updated_at"])

    messages.success(
        request,
        "Periodo cerrado. Ya no se puede modificar.",
    )
    return redirect("rrhh:nomina_periodo_detalle", pk=periodo.pk)
    
# ═══════════════════════════════════════════════════════════
#  DESCARGA DE ARCHIVOS TXT POR BANCO
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def periodo_generar_txt(request, pk, codigo_banco):
    """
    Genera y descarga el archivo TXT de pago para un banco específico.
    """
    from django.http import HttpResponse

    from .bancos.factory import get_generador
    from .bancos.base import GeneradorNoDisponible

    periodo = get_object_or_404(
        _periodos_queryset(request.user).select_related("empresa"),
        pk=pk,
    )

    if not _puede_gestionar(request.user):
        messages.error(request, "No tienes permisos para generar archivos de pago.")
        return redirect("rrhh:nomina_periodo_detalle", pk=periodo.pk)

    if periodo.estatus not in ("aprobado", "pagado", "cerrado"):
        messages.error(
            request,
            f"Solo se pueden generar archivos de pago para periodos aprobados. "
            f"Estado actual: '{periodo.get_estatus_display()}'.",
        )
        return redirect("rrhh:nomina_periodo_detalle", pk=periodo.pk)

    try:
        generador = get_generador(
            codigo_banco=codigo_banco,
            periodo=periodo,
            empresa=periodo.empresa,
        )
        contenido = generador.generar()
    except GeneradorNoDisponible as e:
        messages.error(request, str(e))
        return redirect("rrhh:nomina_periodo_detalle", pk=periodo.pk)
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("rrhh:nomina_periodo_detalle", pk=periodo.pk)
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error al generar el archivo: {e}")
        return redirect("rrhh:nomina_periodo_detalle", pk=periodo.pk)

    # Nombre del archivo
    filename = (
        f"NOMINA_{codigo_banco}_{periodo.anio}_"
        f"{periodo.tipo}_{periodo.numero_periodo}.txt"
    )

    response = HttpResponse(
        contenido,
        content_type="text/plain; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ═══════════════════════════════════════════════════════════
#  API JSON — BANCOS POR PERIODO
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def periodo_bancos_api(request, pk):
    """
    Devuelve la lista de bancos con nóminas en el periodo.
    Usado por el detalle para poblar la sección de archivos de pago.
    """
    from django.http import JsonResponse
    from .bancos.services import nominas_agrupadas_por_banco

    periodo = get_object_or_404(
        _periodos_queryset(request.user),
        pk=pk,
    )

    resultado = nominas_agrupadas_por_banco(periodo)

    # Serializar Decimal a float/str
    bancos = []
    for b in resultado["bancos"]:
        bancos.append({
            "codigo": b["codigo"],
            "nombre": b["nombre"],
            "total": float(b["total"]),
            "cantidad": b["cantidad"],
            "generador_disponible": b["generador_disponible"],
        })

    return JsonResponse({
        "bancos": bancos,
        "sin_banco": resultado["sin_banco"],
    })

    