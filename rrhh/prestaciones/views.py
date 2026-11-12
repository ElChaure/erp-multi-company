"""
Vistas HTML del módulo de Prestaciones Sociales.

Vistas:
    - prestacion_lista         → Listado con KPIs y filtros
    - prestacion_detalle       → Detalle del empleado con histórico
    - prestacion_calculadora   → Simulador de liquidación
    - prestacion_liquidar      → POST: procesa la liquidación real
    - prestacion_recalcular    → POST: recalcula saldos del empleado
"""
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Avg, Max
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from rrhh.decorators import empleado_autenticado, solo_rrhh
from rrhh.models import Empleado, ParametroNomina

from .engine import calcular_prestaciones, calcular_retroactivo
from .models import (
    ConfiguracionPrestaciones,
    PrestacionSocial,
    DepositoPrestacion,
    CalculoRetroactivo,
)
from .services import (
    obtener_configuracion,
    obtener_prestacion,
    recalcular_prestacion,
    registrar_calculo_retroactivo,
)


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _empleados_queryset(user):
    """
    Devuelve el queryset de empleados visibles para el usuario.

    - superadmin / acceso global: todos
    - otros: solo los de su empresa
    """
    qs = Empleado.objects.select_related(
        "empresa", "cargo", "departamento", "banco"
    )
    if user.is_superuser:
        return qs
    if hasattr(user, "perfil") and user.perfil.tiene_acceso_global:
        return qs
    if hasattr(user, "perfil") and user.perfil.empresa:
        return qs.filter(empresa=user.perfil.empresa)
    return qs.none()


def _puede_gestionar(user):
    """Solo RRHH y superiores pueden recalcular/liquidar."""
    if user.is_superuser:
        return True
    perfil = getattr(user, "perfil", None)
    if not perfil:
        return False
    return perfil.rol in ("superadmin", "admin", "rrhh")


def _parametros_de(empleado, anio=None):
    """Busca los ParametroNomina para el empleado/empresa/año."""
    if anio is None:
        anio = date.today().year
    return ParametroNomina.objects.filter(
        empresa=empleado.empresa,
        anio=anio,
        activo=True,
    ).first()


# ═══════════════════════════════════════════════════════════
#  LISTA
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def prestacion_lista(request):
    """
    Listado de prestaciones sociales por empleado.

    Filtros:
        - q: búsqueda por nombre/cédula/número de empleado
        - empresa: (solo superadmin)
        - estatus: activa / liquidada / suspendida / sin_prestacion
        - antiguedad_min: años mínimos de servicio
    """
    qs = _empleados_queryset(request.user).filter(estatus="activo")

    # Filtros
    q = request.GET.get("q", "").strip()
    empresa_id = request.GET.get("empresa", "").strip()
    estatus = request.GET.get("estatus", "").strip()
    antiguedad_min = request.GET.get("antiguedad_min", "").strip()

    if q:
        qs = qs.filter(
            Q(nombre__icontains=q)
            | Q(apellido_paterno__icontains=q)
            | Q(apellido_materno__icontains=q)
            | Q(numero_empleado__icontains=q)
            | Q(cedula__icontains=q)
        )

    if empresa_id and (request.user.is_superuser
                       or request.user.perfil.tiene_acceso_global):
        try:
            qs = qs.filter(empresa_id=int(empresa_id))
        except (ValueError, TypeError):
            pass

    if antiguedad_min:
        try:
            anios = int(antiguedad_min)
            fecha_limite = date.today().replace(
                year=date.today().year - anios
            )
            qs = qs.filter(fecha_ingreso__lte=fecha_limite)
        except (ValueError, TypeError):
            pass

    # Anotar si tiene prestación
    qs = qs.annotate(
        tiene_prestacion=Count("prestacion_social"),
    )

    if estatus == "sin_prestacion":
        qs = qs.filter(tiene_prestacion=0)
    elif estatus in ("activa", "liquidada", "suspendida"):
        qs = qs.filter(prestacion_social__estatus=estatus)

    qs = qs.order_by("apellido_paterno", "nombre")

    # KPIs
    prestaciones_qs = PrestacionSocial.objects.filter(
        empleado__in=qs.values("id")
    ) if False else PrestacionSocial.objects.all()

    # Filtro por empresa para los KPIs
    if not (request.user.is_superuser or request.user.perfil.tiene_acceso_global):
        prestaciones_qs = prestaciones_qs.filter(
            empleado__empresa=request.user.perfil.empresa
        )

    total_prestaciones = prestaciones_qs.count()
    total_saldo_ves = prestaciones_qs.aggregate(
        total=Sum("saldo_total_ves")
    )["total"] or Decimal("0")
    total_saldo_usd = prestaciones_qs.aggregate(
        total=Sum("saldo_total_usd")
    )["total"] or Decimal("0")
    promedio_ves = prestaciones_qs.aggregate(
        prom=Avg("saldo_total_ves")
    )["prom"] or Decimal("0")
    activas = prestaciones_qs.filter(estatus="activa").count()
    liquidadas = prestaciones_qs.filter(estatus="liquidada").count()

    # Empleados sin prestación (para la card de alerta)
    sin_prestacion = qs.filter(tiene_prestacion=0).count()

    # Top 5 por saldo
    top_5 = (
        prestaciones_qs
        .select_related("empleado")
        .order_by("-saldo_total_ves")[:5]
    )

    # Paginación
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_obj": page_obj,
        "total": qs.count(),
        "filtros": {
            "q": q,
            "empresa": empresa_id,
            "estatus": estatus,
            "antiguedad_min": antiguedad_min,
        },
        "kpis": {
            "total_prestaciones": total_prestaciones,
            "total_saldo_ves": total_saldo_ves,
            "total_saldo_usd": total_saldo_usd,
            "promedio_ves": promedio_ves,
            "activas": activas,
            "liquidadas": liquidadas,
            "sin_prestacion": sin_prestacion,
        },
        "top_5": top_5,
        "puede_gestionar": _puede_gestionar(request.user),
    }
    return render(request, "prestaciones/prestacion_lista.html", context)


# ═══════════════════════════════════════════════════════════
#  DETALLE
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def prestacion_detalle(request, empleado_id):
    """
    Detalle de las prestaciones de un empleado.

    Muestra:
        - 4 KPIs: saldo garantía, intereses, retroactivo, método actual
        - Comparación Art. 142.d (garantía vs retroactivo)
        - Histórico de depósitos (paginado)
        - Últimos cálculos retroactivos registrados
    """
    empleado = get_object_or_404(
        _empleados_queryset(request.user),
        pk=empleado_id,
    )

    # Obtener o crear prestación (lazy)
    prestacion = obtener_prestacion(empleado)

    # Cálculo actual (en vivo, para tener garantía vs retroactivo actualizado)
    parametros = _parametros_de(empleado)
    try:
        calculo = calcular_prestaciones(empleado, parametros=parametros)
    except Exception as e:
        calculo = None
        messages.warning(
            request,
            f"No se pudo calcular el comparativo: {e}"
        )

    # Histórico de depósitos paginado
    depositos_qs = (
        prestacion.depositos
        .order_by("-anio", "-trimestre")
    )
    paginator_dep = Paginator(depositos_qs, 12)
    page_dep = paginator_dep.get_page(request.GET.get("page_dep", 1))

    # Últimos cálculos retroactivos
    calculos_retro = prestacion.calculos_retroactivos.all()[:5]

    context = {
        "empleado": empleado,
        "prestacion": prestacion,
        "calculo": calculo,
        "page_dep": page_dep,
        "calculos_retro": calculos_retro,
        "puede_gestionar": _puede_gestionar(request.user),
        "anios_servicio": prestacion.anios_servicio,
    }
    return render(request, "prestaciones/prestacion_detalle.html", context)


# ═══════════════════════════════════════════════════════════
#  CALCULADORA (SIMULADOR)
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def prestacion_calculadora(request, empleado_id):
    """
    Simulador de liquidación.

    Permite elegir:
        - fecha de corte (default hoy)
        - modo (auto / garantia / retroactivo)

    Muestra en vivo el resultado de ambos métodos y el seleccionado.
    """
    empleado = get_object_or_404(
        _empleados_queryset(request.user),
        pk=empleado_id,
    )

    fecha_corte_str = request.GET.get("fecha_corte", "").strip()
    modo = request.GET.get("modo", "").strip() or None

    # Parsear fecha
    if fecha_corte_str:
        try:
            fecha_corte = date.fromisoformat(fecha_corte_str)
        except ValueError:
            fecha_corte = date.today()
            messages.warning(
                request,
                f"Fecha inválida: {fecha_corte_str}. Se usó la fecha actual."
            )
    else:
        fecha_corte = date.today()

    # Calcular
    parametros = _parametros_de(empleado, anio=fecha_corte.year)
    try:
        calculo = calcular_prestaciones(
            empleado,
            fecha_corte=fecha_corte,
            parametros=parametros,
            modo=modo,
        )
    except Exception as e:
        calculo = None
        messages.error(request, f"Error al calcular: {e}")

    context = {
        "empleado": empleado,
        "calculo": calculo,
        "fecha_corte": fecha_corte,
        "modo": modo or "auto",
        "puede_gestionar": _puede_gestionar(request.user),
    }
    return render(request, "prestaciones/prestacion_calculadora.html", context)


# ═══════════════════════════════════════════════════════════
#  ACCIONES (POST)
# ═══════════════════════════════════════════════════════════

@solo_rrhh
@require_POST
def prestacion_recalcular(request, empleado_id):
    """
    Recalcula los saldos de la prestación del empleado.

    - Regenera los depósitos trimestrales existentes
    - Recalcula el saldo acumulado
    - Actualiza el último retroactivo
    """
    empleado = get_object_or_404(
        _empleados_queryset(request.user),
        pk=empleado_id,
    )

    parametros = _parametros_de(empleado)
    try:
        prestacion = recalcular_prestacion(empleado, parametros)
        messages.success(
            request,
            f"Prestación recalculada. "
            f"Saldo actual: Bs. {prestacion.saldo_total_ves:,.2f}."
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error al recalcular: {e}")

    return redirect("rrhh:prestacion_detalle", empleado_id=empleado.id)


@solo_rrhh
@require_POST
def prestacion_liquidar(request, empleado_id):
    """
    Procesa la liquidación REAL de las prestaciones del empleado.

    Acciones:
        1. Calcula garantía + retroactivo
        2. Aplica Art. 142.d (el mayor)
        3. Registra un CalculoRetroactivo (snapshot)
        4. Marca PrestacionSocial.estatus = "liquidada"
        5. Actualiza Empleado.estatus = "baja" y fecha_egreso
    """
    empleado = get_object_or_404(
        _empleados_queryset(request.user),
        pk=empleado_id,
    )

    if empleado.prestacion_social.estatus == "liquidada":
        messages.warning(
            request,
            "Este empleado ya tiene sus prestaciones liquidadas."
        )
        return redirect("rrhh:prestacion_detalle", empleado_id=empleado.id)

    # Fecha de egreso (del form o de hoy)
    fecha_egreso_str = request.POST.get("fecha_egreso", "").strip()
    if fecha_egreso_str:
        try:
            fecha_egreso = date.fromisoformat(fecha_egreso_str)
        except ValueError:
            fecha_egreso = date.today()
    else:
        fecha_egreso = empleado.fecha_egreso or date.today()

    try:
        calculo = calcular_prestaciones(empleado, fecha_corte=fecha_egreso)
        prestacion = obtener_prestacion(empleado)

        # Snapshot
        registro = registrar_calculo_retroactivo(empleado, fecha_egreso)

        # Actualizar prestación
        prestacion.estatus = "liquidada"
        prestacion.fecha_liquidacion = fecha_egreso
        prestacion.monto_liquidacion_ves = calculo["monto_final_ves"]
        prestacion.ultimo_metodo_aplicado = calculo["metodo_seleccionado"]
        prestacion.save()

        # Actualizar empleado
        if empleado.estatus != "baja":
            empleado.estatus = "baja"
        if not empleado.fecha_egreso:
            empleado.fecha_egreso = fecha_egreso
        empleado.save(update_fields=["estatus", "fecha_egreso", "updated_at"])

        messages.success(
            request,
            f"Liquidación procesada. "
            f"Método: {calculo['metodo_seleccionado'].upper()}. "
            f"Monto: Bs. {calculo['monto_final_ves']:,.2f}."
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error al liquidar: {e}")

    return redirect("rrhh:prestacion_detalle", empleado_id=empleado.id)