"""
Vistas HTML del módulo de Vacaciones.

Vistas:
    - vacaciones_lista              → Listado con KPIs
    - vacaciones_detalle            → Detalle del empleado
    - vacaciones_vencimientos       → Días por vencer
    - vacaciones_colectivas_lista   → Listado de colectivas
    - vacaciones_colectiva_nueva    → Crear colectiva
    - vacaciones_colectiva_detalle  → Detalle de colectiva
    - vacaciones_ajustar            → POST: ajuste manual
    - vacaciones_recalcular         → POST: recalcular saldo
    - procesar_vencimientos_view    → POST: procesar todos los vencidos
    - aplicar_colectiva_view        → POST: aplicar colectiva
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Avg, Min
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from rrhh.decorators import empleado_autenticado, solo_rrhh
from rrhh.models import (
    Empleado,
    Empresa,
    Sede,
    Departamento,
    SaldoVacaciones,
    MovimientoSaldoVacaciones,
    TipoAusencia,
    VacacionColectiva,
    SolicitudAusencia,
)

from .vacaciones_engine import (
    dias_por_vencer,
    dias_habiles_entre,
    calcular_saldo_anual,
)
from .vacaciones_services import (
    obtener_configuracion,
    generar_saldo_anual,
    recalcular_saldo,
    aplicar_vacacion_colectiva,
)


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _empleados_queryset(user):
    """Empleados visibles para el usuario."""
    qs = Empleado.objects.select_related(
        "empresa", "cargo", "departamento", "sede"
    )
    if user.is_superuser:
        return qs
    if hasattr(user, "perfil") and user.perfil.tiene_acceso_global:
        return qs
    if hasattr(user, "perfil") and user.perfil.empresa:
        return qs.filter(empresa=user.perfil.empresa)
    return qs.none()


def _saldos_queryset(user):
    """Saldos de vacaciones visibles para el usuario."""
    qs = SaldoVacaciones.objects.select_related(
        "empleado", "empleado__empresa", "empleado__cargo",
        "empleado__departamento",
    )
    if user.is_superuser:
        return qs
    if hasattr(user, "perfil") and user.perfil.tiene_acceso_global:
        return qs
    if hasattr(user, "perfil") and user.perfil.empresa:
        return qs.filter(empleado__empresa=user.perfil.empresa)
    return qs.none()


# ═══════════════════════════════════════════════════════════
#  LISTADO
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def vacaciones_lista(request):
    """
    Listado de saldos de vacaciones con KPIs.

    Filtros:
        - q: búsqueda por nombre/cédula/número de empleado
        - empresa: (solo superadmin)
        - anio: año del saldo
        - estado: 'con_saldo' / 'sin_saldo' / 'por_vencer'
        - departamento
    """
    hoy = date.today()
    anio_default = hoy.year

    # Parámetros
    q = request.GET.get("q", "").strip()
    empresa_id = request.GET.get("empresa", "").strip()
    anio = request.GET.get("anio", "").strip() or str(anio_default)
    estado = request.GET.get("estado", "").strip()
    departamento_id = request.GET.get("departamento", "").strip()
    por_vencer_dias = request.GET.get("por_vencer_dias", "60").strip()

    try:
        anio_int = int(anio)
    except (ValueError, TypeError):
        anio_int = anio_default

    # QuerySet base
    qs = _saldos_queryset(request.user).filter(anio=anio_int)

    # Filtros
    if q:
        qs = qs.filter(
            Q(empleado__nombre__icontains=q)
            | Q(empleado__apellido_paterno__icontains=q)
            | Q(empleado__apellido_materno__icontains=q)
            | Q(empleado__numero_empleado__icontains=q)
            | Q(empleado__cedula__icontains=q)
        )

    if empresa_id and (request.user.is_superuser
                       or request.user.perfil.tiene_acceso_global):
        try:
            qs = qs.filter(empleado__empresa_id=int(empresa_id))
        except (ValueError, TypeError):
            pass

    if departamento_id:
        try:
            qs = qs.filter(empleado__departamento_id=int(departamento_id))
        except (ValueError, TypeError):
            pass

    if estado == "por_vencer":
        try:
            dias = int(por_vencer_dias)
        except (ValueError, TypeError):
            dias = 60
        fecha_limite = hoy + timedelta(days=dias)
        qs = qs.filter(
            fecha_limite_uso__gte=hoy,
            fecha_limite_uso__lte=fecha_limite,
        )

    qs = qs.order_by(
        "empleado__apellido_paterno",
        "empleado__nombre",
    )

    # KPIs (sobre todo el queryset filtrado, antes de paginar)
    kpis = {
        "total_saldos": qs.count(),
        "total_pendientes": Decimal("0"),
        "con_saldo": 0,
        "por_vencer": 0,
        "sin_prestacion": 0,
    }

    # Cálculos en Python (por el @property dias_pendientes)
    for saldo in qs:
        dias = saldo.dias_pendientes
        if dias > 0:
            kpis["con_saldo"] += 1
            kpis["total_pendientes"] += dias

        info_venc = dias_por_vencer(saldo, dias_aviso=60)
        if info_venc["esta_por_vencer"] and dias > 0:
            kpis["por_vencer"] += 1

    # Paginación
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    # Datos para filtros
    if request.user.is_superuser or request.user.perfil.tiene_acceso_global:
        empresas = Empresa.objects.filter(activa=True).order_by("razon_social")
    else:
        empresas = Empresa.objects.none()

    departamentos = Departamento.objects.filter(activo=True).order_by("nombre")
    if request.user.perfil.empresa:
        departamentos = departamentos.filter(empresa=request.user.perfil.empresa)

    anios_disponibles = sorted(
        _saldos_queryset(request.user).values_list("anio", flat=True).distinct(),
        reverse=True,
    ) or [hoy.year]

    context = {
        "page_obj": page_obj,
        "total": qs.count(),
        "kpis": kpis,
        "anios_disponibles": anios_disponibles,
        "empresas": empresas,
        "departamentos": departamentos,
        "filtros": {
            "q": q,
            "empresa": empresa_id,
            "anio": anio,
            "estado": estado,
            "departamento": departamento_id,
            "por_vencer_dias": por_vencer_dias,
        },
        "hoy": hoy,
    }
    return render(request, "ausencias/vacaciones_lista.html", context)


# ═══════════════════════════════════════════════════════════
#  DETALLE
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def vacaciones_detalle(request, empleado_id):
    """
    Detalle de las vacaciones de un empleado: saldo actual,
    histórico de movimientos, ajustes.
    """
    empleado = get_object_or_404(
        _empleados_queryset(request.user),
        pk=empleado_id,
    )

    # Filtro de año
    anio_str = request.GET.get("anio", "").strip()
    anio = int(anio_str) if anio_str.isdigit() else date.today().year

    # Saldo del año
    saldo = SaldoVacaciones.objects.filter(
        empleado=empleado, anio=anio,
    ).first()

    # Años disponibles
    anios_disponibles = list(
        SaldoVacaciones.objects.filter(empleado=empleado)
        .values_list("anio", flat=True)
        .distinct()
        .order_by("-anio")
    )
    if anio not in anios_disponibles:
        anios_disponibles.insert(0, anio)

    # Histórico de movimientos
    movimientos = []
    if saldo:
        movimientos = (
            MovimientoSaldoVacaciones.objects.filter(saldo=saldo)
            .select_related("usuario", "solicitud")
            .order_by("-created_at")
        )

    paginator = Paginator(movimientos, 20)
    page_mov = paginator.get_page(request.GET.get("page_mov", 1))

    # Información de vencimiento
    info_venc = dias_por_vencer(saldo, dias_aviso=60) if saldo else None

    # Configuración de la empresa
    config = obtener_configuracion(empleado.empresa)

    # Solicitudes relacionadas
    solicitudes = (
        SolicitudAusencia.objects.filter(empleado=empleado)
        .select_related("tipo", "aprobador")
        .order_by("-fecha_solicitud")[:10]
    )

    context = {
        "empleado": empleado,
        "saldo": saldo,
        "anio": anio,
        "anios_disponibles": anios_disponibles,
        "page_mov": page_mov,
        "info_venc": info_venc,
        "config": config,
        "solicitudes": solicitudes,
        "hoy": date.today(),
    }
    return render(request, "ausencias/vacaciones_detalle.html", context)


# ═══════════════════════════════════════════════════════════
#  VENCIMIENTOS
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def vacaciones_vencimientos(request):
    """
    Vista de días por vencer (con filtro de días).

    Muestra los saldos que vencen en los próximos N días,
    ordenados por urgencia.
    """
    hoy = date.today()
    dias_aviso = request.GET.get("dias", "60").strip()
    try:
        dias_aviso_int = int(dias_aviso)
    except (ValueError, TypeError):
        dias_aviso_int = 60

    fecha_limite = hoy + timedelta(days=dias_aviso_int)

    # Saldos por vencer
    saldos = (
        _saldos_queryset(request.user)
        .filter(
            fecha_limite_uso__gte=hoy,
            fecha_limite_uso__lte=fecha_limite,
        )
        .order_by("fecha_limite_uso")
    )

    # Filtrar los que tienen días pendientes > 0
    items = []
    for saldo in saldos:
        dias = saldo.dias_pendientes
        if dias > 0:
            info = dias_por_vencer(saldo, dias_aviso=dias_aviso_int)
            items.append({
                "saldo": saldo,
                "empleado": saldo.empleado,
                "dias_pendientes": dias,
                "fecha_vencimiento": saldo.fecha_limite_uso,
                "dias_restantes": (saldo.fecha_limite_uso - hoy).days,
            })

    # Ya vencidos (informativo)
    vencidos = (
        _saldos_queryset(request.user)
        .filter(fecha_limite_uso__lt=hoy)
        .order_by("-fecha_limite_uso")
    )
    items_vencidos = []
    for saldo in vencidos:
        dias = saldo.dias_pendientes
        if dias > 0:
            items_vencidos.append({
                "saldo": saldo,
                "empleado": saldo.empleado,
                "dias_pendientes": dias,
                "fecha_vencimiento": saldo.fecha_limite_uso,
                "dias_vencidos": (hoy - saldo.fecha_limite_uso).days,
            })

    # KPIs
    total_por_vencer = sum(i["dias_pendientes"] for i in items)
    total_vencido = sum(i["dias_pendientes"] for i in items_vencidos)

    context = {
        "items": items,
        "items_vencidos": items_vencidos,
        "dias_aviso": dias_aviso_int,
        "hoy": hoy,
        "kpis": {
            "cantidad_por_vencer": len(items),
            "total_dias_por_vencer": total_por_vencer,
            "cantidad_vencidos": len(items_vencidos),
            "total_dias_vencidos": total_vencido,
        },
    }
    return render(request, "ausencias/vacaciones_vencimientos.html", context)


# ═══════════════════════════════════════════════════════════
#  VACACIONES COLECTIVAS
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def vacaciones_colectivas_lista(request):
    """Listado de vacaciones colectivas."""
    qs = VacacionColectiva.objects.select_related(
        "empresa", "sede", "departamento", "tipo_ausencia"
    ).annotate(
        num_solicitudes=Count("solicitudes"),
    )

    # Filtro por empresa para no-superadmin
    if not (request.user.is_superuser or request.user.perfil.tiene_acceso_global):
        if request.user.perfil.empresa:
            qs = qs.filter(empresa=request.user.perfil.empresa)

    # Filtros
    estatus = request.GET.get("estatus", "").strip()
    anio = request.GET.get("anio", "").strip()

    if estatus:
        qs = qs.filter(estatus=estatus)
    if anio:
        try:
            qs = qs.filter(fecha_inicio__year=int(anio))
        except (ValueError, TypeError):
            pass

    qs = qs.order_by("-fecha_inicio")

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    anios_disponibles = sorted(
        VacacionColectiva.objects.values_list("fecha_inicio__year", flat=True)
        .distinct(),
        reverse=True,
    )

    context = {
        "page_obj": page_obj,
        "total": qs.count(),
        "anios_disponibles": anios_disponibles,
        "filtros": {
            "estatus": estatus,
            "anio": anio,
        },
    }
    return render(request, "ausencias/vacaciones_colectivas_lista.html", context)


@empleado_autenticado
def vacaciones_colectiva_nueva(request):
    """
    Formulario para crear una nueva vacación colectiva.
    """
    if request.method == "POST":
        # Recolectar datos
        empresa_id = request.POST.get("empresa")
        nombre = request.POST.get("nombre", "").strip()
        alcance = request.POST.get("alcance", "empresa")
        sede_id = request.POST.get("sede")
        departamento_id = request.POST.get("departamento")
        fecha_inicio_str = request.POST.get("fecha_inicio")
        fecha_fin_str = request.POST.get("fecha_fin")
        observaciones = request.POST.get("observaciones", "").strip()

        # Validaciones básicas
        errores = []
        if not empresa_id:
            errores.append("Debes seleccionar una empresa.")
        if not nombre:
            errores.append("El nombre es obligatorio.")
        if not fecha_inicio_str or not fecha_fin_str:
            errores.append("Las fechas son obligatorias.")

        fecha_inicio = fecha_fin = None
        if fecha_inicio_str and fecha_fin_str:
            try:
                fecha_inicio = date.fromisoformat(fecha_inicio_str)
                fecha_fin = date.fromisoformat(fecha_fin_str)
                if fecha_inicio > fecha_fin:
                    errores.append("La fecha de inicio debe ser anterior a la de fin.")
            except ValueError:
                errores.append("Formato de fecha inválido.")

        if errores:
            for err in errores:
                messages.error(request, err)
        else:
            # Validar empresa
            try:
                empresa = Empresa.objects.get(pk=empresa_id)
            except Empresa.DoesNotExist:
                messages.error(request, "Empresa no encontrada.")
                return redirect("rrhh:vacaciones_colectivas_lista")

            # Crear
            vacacion = VacacionColectiva.objects.create(
                empresa=empresa,
                nombre=nombre,
                alcance=alcance,
                sede_id=sede_id if sede_id else None,
                departamento_id=departamento_id if departamento_id else None,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                dias_habiles=dias_habiles_entre(fecha_inicio, fecha_fin),
                observaciones=observaciones,
                created_by=request.user,
                estatus="borrador",
            )

            messages.success(
                request,
                f"Vacación colectiva '{nombre}' creada. "
                f"Está en borrador; revisá y aplicá cuando estés listo."
            )
            return redirect(
                "rrhh:vacaciones_colectiva_detalle", vacacion_id=vacacion.id
            )

    # GET: mostrar formulario
    if request.user.is_superuser or request.user.perfil.tiene_acceso_global:
        empresas = Empresa.objects.filter(activa=True).order_by("razon_social")
    else:
        empresas = Empresa.objects.filter(id=request.user.perfil.empresa_id)

    sedes = Sede.objects.filter(activa=True).order_by("nombre")
    departamentos = Departamento.objects.filter(activo=True).order_by("nombre")

    context = {
        "empresas": empresas,
        "sedes": sedes,
        "departamentos": departamentos,
    }
    return render(request, "ausencias/vacaciones_colectiva_nueva.html", context)


@empleado_autenticado
def vacaciones_colectiva_detalle(request, vacacion_id):
    """
    Detalle de una vacación colectiva: datos, solicitudes generadas.
    """
    vacacion = get_object_or_404(
        VacacionColectiva.objects.select_related(
            "empresa", "sede", "departamento", "tipo_ausencia"
        ),
        pk=vacacion_id,
    )

    # Permisos
    if not (request.user.is_superuser or request.user.perfil.tiene_acceso_global):
        if request.user.perfil.empresa_id != vacacion.empresa_id:
            messages.error(request, "No tienes permiso para ver esta colectiva.")
            return redirect("rrhh:vacaciones_colectivas_lista")

    # Solicitudes generadas (a través de la relación M2M inversa del campo
    # que definimos con `related_name="vacaciones_colectivas"` en TipoAusencia,
    # pero como no pusimos FK directa en SolicitudAusencia, hacemos match
    # por las fechas y el estatus)
    solicitudes = SolicitudAusencia.objects.filter(
        empleado__empresa=vacacion.empresa,
        fecha_inicio=vacacion.fecha_inicio,
        fecha_fin=vacacion.fecha_fin,
        tipo__categoria="vacaciones",
    ).select_related("empleado", "empleado__cargo", "tipo").order_by(
        "empleado__apellido_paterno"
    )

    # Empleados en el alcance
    empleados_alcance = vacacion._empleados_queryset()

    context = {
        "vacacion": vacacion,
        "solicitudes": solicitudes,
        "total_solicitudes": solicitudes.count(),
        "total_empleados_alcance": empleados_alcance.count(),
    }
    return render(
        request, "ausencias/vacaciones_colectiva_detalle.html", context
    )


# ═══════════════════════════════════════════════════════════
#  ACCIONES POST
# ═══════════════════════════════════════════════════════════

@solo_rrhh
@require_POST
def vacaciones_ajustar(request, empleado_id):
    """
    Ajuste manual del saldo de vacaciones de un empleado.

    Acepta:
        - anio
        - dias (positivo o negativo)
        - motivo (obligatorio)
        - observaciones
    """
    empleado = get_object_or_404(
        _empleados_queryset(request.user),
        pk=empleado_id,
    )

    anio_str = request.POST.get("anio", "").strip()
    dias_str = request.POST.get("dias", "").strip()
    motivo = request.POST.get("motivo", "").strip()

    try:
        anio = int(anio_str)
    except (ValueError, TypeError):
        messages.error(request, "Año inválido.")
        return redirect("rrhh:vacaciones_detalle", empleado_id=empleado.id)

    try:
        dias = Decimal(dias_str)
    except (InvalidOperation, ValueError, TypeError):
        messages.error(request, "Días inválidos.")
        return redirect("rrhh:vacaciones_detalle", empleado_id=empleado.id)

    if not motivo:
        messages.error(request, "El motivo es obligatorio para un ajuste.")
        return redirect("rrhh:vacaciones_detalle", empleado_id=empleado.id)

    if dias == 0:
        messages.warning(request, "El ajuste es 0, no se hizo nada.")
        return redirect("rrhh:vacaciones_detalle", empleado_id=empleado.id)

    # Buscar o crear saldo
    saldo, created = SaldoVacaciones.objects.get_or_create(
        empleado=empleado,
        anio=anio,
        defaults={
            "dias_derecho": Decimal("0"),
            "dias_tomados": Decimal("0"),
            "dias_pagados": Decimal("0"),
            "dias_ajuste": Decimal("0"),
        },
    )

    # Aplicar ajuste
    saldo_anterior = saldo.dias_pendientes
    saldo.dias_ajuste += dias
    saldo.save(update_fields=["dias_ajuste", "updated_at"])

    # Registrar movimiento
    MovimientoSaldoVacaciones.objects.create(
        saldo=saldo,
        tipo="ajuste",
        dias=dias,
        saldo_anterior=saldo_anterior,
        saldo_nuevo=saldo.dias_pendientes,
        motivo=motivo,
        usuario=request.user,
    )

    messages.success(
        request,
        f"Ajuste aplicado: {dias:+} días. "
        f"Saldo pendiente ahora: {saldo.dias_pendientes}."
    )
    return redirect(
        f"{request.META.get('HTTP_REFERER', '/rrhh/vacaciones/' + str(empleado.id) + '/')}"
    )


@solo_rrhh
@require_POST
def vacaciones_recalcular(request, empleado_id):
    """Recalcula los días de derecho del saldo del empleado."""
    empleado = get_object_or_404(
        _empleados_queryset(request.user),
        pk=empleado_id,
    )

    anio_str = request.POST.get("anio", "").strip()
    try:
        anio = int(anio_str)
    except (ValueError, TypeError):
        anio = date.today().year

    saldo = SaldoVacaciones.objects.filter(
        empleado=empleado, anio=anio,
    ).first()

    if not saldo:
        # Crear
        saldo = generar_saldo_anual(empleado, anio, usuario=request.user)
        messages.success(
            request,
            f"Saldo {anio} creado: {saldo.dias_derecho} días de derecho."
        )
    else:
        recalcular_saldo(saldo, usuario=request.user)
        messages.success(
            request,
            f"Saldo {anio} recalculado: {saldo.dias_derecho} días de derecho."
        )

    return redirect("rrhh:vacaciones_detalle", empleado_id=empleado.id)


@solo_rrhh
@require_POST
def procesar_vencimientos_view(request):
    """Procesa los vencimientos de días no disfrutados."""
    from .vacaciones_services import procesar_vencimientos

    # Determinar empresa
    empresa_id = request.POST.get("empresa_id")
    if empresa_id:
        try:
            empresa = Empresa.objects.get(pk=empresa_id)
        except Empresa.DoesNotExist:
            messages.error(request, "Empresa no encontrada.")
            return redirect("rrhh:vacaciones_vencimientos")
    else:
        empresa = request.user.perfil.empresa

    if not empresa:
        messages.error(
            request,
            "No se pudo determinar la empresa para procesar vencimientos."
        )
        return redirect("rrhh:vacaciones_vencimientos")

    resultado = procesar_vencimientos(empresa, usuario=request.user)

    messages.success(
        request,
        f"Vencimientos procesados: {resultado['procesados']} saldo(s). "
        f"Total días vencidos: {resultado['total_dias_vencidos']}."
    )
    return redirect("rrhh:vacaciones_vencimientos")


@solo_rrhh
@require_POST
def aplicar_colectiva_view(request, vacacion_id):
    """Aplica una vacación colectiva."""
    vacacion = get_object_or_404(VacacionColectiva, pk=vacacion_id)

    if vacacion.estatus != "borrador":
        messages.warning(
            request,
            f"Solo se pueden aplicar vacaciones en borrador. "
            f"Esta está en '{vacacion.get_estatus_display()}'."
        )
        return redirect(
            "rrhh:vacaciones_colectiva_detalle", vacacion_id=vacacion.id
        )

    try:
        resultado = aplicar_vacacion_colectiva(vacacion, usuario=request.user)
        messages.success(
            request,
            f"Vacación colectiva aplicada: "
            f"{resultado['solicitudes_creadas']} solicitud(es) creada(s). "
            f"{len(resultado['errores'])} error(es)."
        )

        if resultado["errores"]:
            for err in resultado["errores"][:5]:
                messages.warning(
                    request,
                    f"  {err['empleado']}: {err['error']}"
                )
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error al aplicar: {e}")

    return redirect(
        "rrhh:vacaciones_colectiva_detalle", vacacion_id=vacacion.id
    )