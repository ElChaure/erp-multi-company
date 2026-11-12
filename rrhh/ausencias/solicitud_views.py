"""
Vistas HTML para el flujo de solicitudes de vacaciones.

Vistas:
    - solicitud_lista      → Bandeja de aprobaciones (RRHH/manager)
    - solicitud_detalle    → Ver + aprobar/rechazar
    - solicitud_nueva      → Formulario del empleado
    - solicitud_mis        → Mis solicitudes (empleado)
    - solicitud_aprobar    → POST: aprobar
    - solicitud_rechazar   → POST: rechazar
    - solicitud_cancelar   → POST: cancelar
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from rrhh.decorators import empleado_autenticado, solo_manager, solo_rrhh
from rrhh.models import (
    Empleado,
    Empresa,
    TipoAusencia,
    SaldoVacaciones,
    SolicitudAusencia,
)

from .vacaciones_engine import dias_habiles_entre
from .vacaciones_services import obtener_configuracion
from .services import (
    validar_solicitud,
    aprobar_solicitud,
    rechazar_solicitud,
    cancelar_solicitud,
)


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _empleado_del_usuario(user):
    """Devuelve el Empleado vinculado al usuario, o None."""
    perfil = getattr(user, "perfil", None)
    if not perfil:
        return None
    return getattr(perfil, "empleado", None)


def _es_aprobador(user):
    """¿El usuario puede aprobar solicitudes?"""
    if user.is_superuser:
        return True
    perfil = getattr(user, "perfil", None)
    if not perfil:
        return False
    return perfil.rol in ("superadmin", "admin", "rrhh", "manager")


def _solicitudes_para_aprobar(user):
    """
    Devuelve el queryset de solicitudes que el usuario puede aprobar.

    - superadmin / admin / rrhh: todas las de su empresa (o todas si global)
    - manager: solo las de sus subordinados directos
    """
    qs = SolicitudAusencia.objects.select_related(
        "empleado", "empleado__cargo", "empleado__departamento",
        "tipo", "aprobador",
    )

    if user.is_superuser:
        return qs

    perfil = getattr(user, "perfil", None)
    if not perfil:
        return qs.none()

    # RRHH / admin: toda su empresa
    if perfil.rol in ("superadmin", "admin", "rrhh"):
        if perfil.empresa_id:
            return qs.filter(empleado__empresa_id=perfil.empresa_id)
        return qs

    # Manager: solo sus subordinados directos
    if perfil.rol == "manager":
        empleado = _empleado_del_usuario(user)
        if empleado:
            return qs.filter(empleado__jefe_id=empleado.id)
        # Si no tiene ficha de empleado, no ve nada
        return qs.none()

    return qs.none()


def _solicitudes_del_empleado(user):
    """Solicitudes del empleado logueado."""
    empleado = _empleado_del_usuario(user)
    if not empleado:
        return SolicitudAusencia.objects.none()
    return SolicitudAusencia.objects.filter(empleado=empleado)


# ═══════════════════════════════════════════════════════════
#  BANDEJA DE APROBACIONES
# ═══════════════════════════════════════════════════════════

@solo_manager
def solicitud_lista(request):
    """
    Bandeja de solicitudes pendientes de aprobación.

    Filtros:
        - estatus (pendiente por defecto)
        - tipo
        - q (búsqueda por empleado)
    """
    qs = _solicitudes_para_aprobar(request.user)

    # Filtros
    estatus = request.GET.get("estatus", "pendiente").strip()
    tipo_id = request.GET.get("tipo", "").strip()
    q = request.GET.get("q", "").strip()

    if estatus:
        qs = qs.filter(estatus=estatus)

    if tipo_id:
        try:
            qs = qs.filter(tipo_id=int(tipo_id))
        except (ValueError, TypeError):
            pass

    if q:
        qs = qs.filter(
            Q(empleado__nombre__icontains=q)
            | Q(empleado__apellido_paterno__icontains=q)
            | Q(empleado__numero_empleado__icontains=q)
        )

    qs = qs.order_by("-fecha_solicitud")

    # KPIs
    kpis = {
        "pendientes": qs.filter(estatus="pendiente").count(),
        "aprobadas": qs.filter(estatus="aprobada").count(),
        "rechazadas": qs.filter(estatus="rechazada").count(),
        "total": qs.count(),
    }

    # Paginación
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    # Tipos para el filtro
    tipos = TipoAusencia.objects.filter(activo=True).order_by("categoria", "nombre")
    if request.user.perfil.empresa_id:
        tipos = tipos.filter(
            Q(empresa_id=request.user.perfil.empresa_id) | Q(empresa__isnull=True)
        )

    context = {
        "page_obj": page_obj,
        "total": qs.count(),
        "kpis": kpis,
        "tipos": tipos,
        "filtros": {
            "estatus": estatus,
            "tipo": tipo_id,
            "q": q,
        },
    }
    return render(request, "ausencias/solicitud_lista.html", context)


# ═══════════════════════════════════════════════════════════
#  DETALLE
# ═══════════════════════════════════════════════════════════

@solo_manager
def solicitud_detalle(request, solicitud_id):
    """
    Detalle de una solicitud. Permite aprobar o rechazar si está pendiente.
    """
    # El queryset filtra por permisos: solo ve las que puede aprobar
    qs = _solicitudes_para_aprobar(request.user)

    # Pero también permitimos ver las propias
    empleado = _empleado_del_usuario(request.user)
    if empleado:
        qs = qs | SolicitudAusencia.objects.filter(empleado=empleado)

    solicitud = get_object_or_404(qs.distinct(), pk=solicitud_id)

    # Info adicional para el aprobador
    puede_aprobar = (
        solicitud.estatus == "pendiente"
        and _es_aprobador(request.user)
    )

    # Saldo actual del empleado (para mostrar contexto)
    saldo = SaldoVacaciones.objects.filter(
        empleado=solicitud.empleado,
        anio=solicitud.fecha_inicio.year,
    ).first()

    context = {
        "solicitud": solicitud,
        "puede_aprobar": puede_aprobar,
        "saldo": saldo,
    }
    return render(request, "ausencias/solicitud_detalle.html", context)


# ═══════════════════════════════════════════════════════════
#  FORMULARIO (EMPLEADO)
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def solicitud_nueva(request):
    """
    Formulario para que el empleado solicite vacaciones.

    GET: mostrar formulario
    POST: validar y crear solicitud
    """
    empleado = _empleado_del_usuario(request.user)

    # Sin ficha de empleado → no puede solicitar
    if not empleado:
        messages.error(
            request,
            "Tu usuario no está vinculado a una ficha de empleado. "
            "Contactá a RRHH para que vinculen tu usuario."
        )
        return redirect("rrhh:mi_portal")

    # Verificar que exista un TipoAusencia de vacaciones
    tipo_vacaciones = TipoAusencia.objects.filter(
        Q(empresa=empleado.empresa) | Q(empresa__isnull=True),
        categoria="vacaciones",
        activo=True,
    ).first()

    if not tipo_vacaciones:
        messages.error(
            request,
            "No hay un tipo de ausencia de vacaciones configurado. "
            "Contactá a RRHH."
        )
        return redirect("rrhh:mi_portal")

    # Configuración de vacaciones de la empresa
    config = obtener_configuracion(empleado.empresa)
    dias_antelacion = config.dias_antelacion_solicitud

    # Fechas sugeridas (default: hoy + antelación)
    fecha_minima = date.today() + timedelta(days=dias_antelacion)

    if request.method == "POST":
        fecha_inicio_str = request.POST.get("fecha_inicio", "").strip()
        fecha_fin_str = request.POST.get("fecha_fin", "").strip()
        motivo = request.POST.get("motivo", "").strip()
        dias_solicitados_str = request.POST.get("dias_solicitados", "").strip()

        errores = []

        # Parsear fechas
        try:
            fecha_inicio = date.fromisoformat(fecha_inicio_str)
            fecha_fin = date.fromisoformat(fecha_fin_str)
        except (ValueError, TypeError):
            errores.append("Las fechas son obligatorias y deben tener formato válido.")
            fecha_inicio = fecha_fin = None

        # Motivo
        if not motivo:
            errores.append("El motivo es obligatorio.")

        if fecha_inicio and fecha_fin:
            # Calcular días hábiles
            dias_habiles = dias_habiles_entre(fecha_inicio, fecha_fin)

            if dias_habiles <= 0:
                errores.append("El rango no contiene días hábiles.")

            # Máximo de días hábiles por solicitud (LOTTT: 15 días continuos si es colectiva,
            # pero individual no tiene un tope estricto más allá del saldo)
            # Aquí validamos contra el saldo disponible en el servicio

            # Validar con el servicio
            try:
                validar_solicitud(
                    empleado=empleado,
                    tipo=tipo_vacaciones,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    dias_solicitados=dias_habiles,
                )
            except ValidationError as e:
                for err in e.messages:
                    errores.append(err)

        if errores:
            for err in errores:
                messages.error(request, err)
        else:
            # Crear la solicitud
            solicitud = SolicitudAusencia.objects.create(
                empleado=empleado,
                tipo=tipo_vacaciones,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                dias_solicitados=Decimal(str(dias_habiles)),
                dias_calendario=(fecha_fin - fecha_inicio).days + 1,
                motivo=motivo,
                estatus="pendiente",
            )

            # Notificar al aprobador (mensaje interno)
            messages.success(
                request,
                f"Solicitud enviada. Días hábiles: {dias_habiles}. "
                f"Esperá la aprobación de tu jefe o RRHH."
            )

            # Redirigir a "mis solicitudes"
            return redirect("rrhh:solicitud_mis")

    # GET: mostrar formulario
    # Saldo actual
    saldo = SaldoVacaciones.objects.filter(
        empleado=empleado,
        anio=date.today().year,
    ).first()

    context = {
        "empleado": empleado,
        "tipo_vacaciones": tipo_vacaciones,
        "config": config,
        "fecha_minima": fecha_minima,
        "saldo": saldo,
        "hoy": date.today(),
    }
    return render(request, "ausencias/solicitud_form.html", context)


# ═══════════════════════════════════════════════════════════
#  MIS SOLICITUDES (EMPLEADO)
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def solicitud_mis(request):
    """
    Listado de las solicitudes del empleado logueado.
    """
    empleado = _empleado_del_usuario(request.user)

    if not empleado:
        messages.error(
            request,
            "Tu usuario no está vinculado a una ficha de empleado."
        )
        return redirect("rrhh:mi_portal")

    qs = SolicitudAusencia.objects.filter(
        empleado=empleado,
    ).select_related("tipo", "aprobador").order_by("-fecha_solicitud")

    # Filtro por estatus
    estatus = request.GET.get("estatus", "").strip()
    if estatus:
        qs = qs.filter(estatus=estatus)

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    # KPIs
    kpis = {
        "pendientes": qs.filter(estatus="pendiente").count(),
        "aprobadas": qs.filter(estatus="aprobada").count(),
        "rechazadas": qs.filter(estatus="rechazada").count(),
    }

    context = {
        "page_obj": page_obj,
        "empleado": empleado,
        "kpis": kpis,
        "filtros": {"estatus": estatus},
    }
    return render(request, "ausencias/solicitud_mis.html", context)


# ═══════════════════════════════════════════════════════════
#  ACCIONES POST
# ═══════════════════════════════════════════════════════════

@solo_manager
@require_POST
def solicitud_aprobar(request, solicitud_id):
    """Aprueba una solicitud pendiente."""
    qs = _solicitudes_para_aprobar(request.user)
    solicitud = get_object_or_404(qs, pk=solicitud_id)

    if solicitud.estatus != "pendiente":
        messages.warning(
            request,
            f"La solicitud ya está en estado '{solicitud.get_estatus_display()}'."
        )
        return redirect("rrhh:solicitud_detalle", solicitud_id=solicitud.id)

    comentario = request.POST.get("comentario", "").strip()

    # Obtener el Empleado del aprobador (o None si es admin sin ficha)
    empleado_aprobador = _empleado_del_usuario(request.user)

    try:
        aprobar_solicitud(solicitud, empleado_aprobador, comentario)
        messages.success(
            request,
            f"Solicitud aprobada. Se descontaron "
            f"{solicitud.dias_solicitados} días del saldo."
        )
    except ValidationError as e:
        for err in e.messages:
            messages.error(request, err)
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error al aprobar: {e}")

    return redirect("rrhh:solicitud_detalle", solicitud_id=solicitud.id)


@solo_manager
@require_POST
def solicitud_rechazar(request, solicitud_id):
    """Rechaza una solicitud pendiente."""
    qs = _solicitudes_para_aprobar(request.user)
    solicitud = get_object_or_404(qs, pk=solicitud_id)

    if solicitud.estatus != "pendiente":
        messages.warning(
            request,
            f"La solicitud ya está en estado '{solicitud.get_estatus_display()}'."
        )
        return redirect("rrhh:solicitud_detalle", solicitud_id=solicitud.id)

    comentario = request.POST.get("comentario", "").strip()

    if not comentario:
        messages.error(
            request,
            "Es obligatorio indicar el motivo del rechazo."
        )
        return redirect("rrhh:solicitud_detalle", solicitud_id=solicitud.id)

    empleado_aprobador = _empleado_del_usuario(request.user)

    try:
        rechazar_solicitud(solicitud, empleado_aprobador, comentario)
        messages.success(request, "Solicitud rechazada.")
    except ValidationError as e:
        for err in e.messages:
            messages.error(request, err)

    return redirect("rrhh:solicitud_detalle", solicitud_id=solicitud.id)


@empleado_autenticado
@require_POST
def solicitud_cancelar(request, solicitud_id):
    """
    Cancela una solicitud. Puede hacerlo el empleado dueño o un aprobador.
    Si estaba aprobada, devuelve los días.
    """
    # Buscar la solicitud entre las que el usuario puede ver
    qs_aprobables = _solicitudes_para_aprobar(request.user)
    qs_propias = _solicitudes_del_empleado(request.user)
    solicitud = get_object_or_404(
        (qs_aprobables | qs_propias).distinct(),
        pk=solicitud_id,
    )

    if not solicitud.puede_cancelar:
        messages.error(
            request,
            f"No se puede cancelar una solicitud en estado "
            f"'{solicitud.get_estatus_display()}'."
        )
        return redirect("rrhh:solicitud_detalle", solicitud_id=solicitud.id)

    motivo = request.POST.get("motivo", "").strip() or "Cancelada por el usuario"

    try:
        cancelar_solicitud(solicitud, usuario=request.user, motivo=motivo)
        messages.success(
            request,
            "Solicitud cancelada. "
            + (
                "Se devolvieron los días al saldo."
                if solicitud.estatus in ("aprobada", "en_disfrute") and solicitud.tipo.afecta_saldo_vacaciones
                else ""
            )
        )
    except ValidationError as e:
        for err in e.messages:
            messages.error(request, err)

    # Redirigir según el rol
    if _es_aprobador(request.user) and request.user.perfil.rol != "empleado":
        return redirect("rrhh:solicitud_detalle", solicitud_id=solicitud.id)
    return redirect("rrhh:solicitud_mis")