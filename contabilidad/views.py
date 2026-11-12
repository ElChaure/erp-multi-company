# contabilidad/views.py
from datetime import date
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from rrhh.models import Empresa
from rrhh.decorators import solo_rrhh

from .models import (
    ComprobanteBorrador, ComprobanteBorradorLinea,
    Asiento, AsientoLinea, PlanCuenta, CentroCosto, PeriodoContable,
    ConfiguracionCIF, CentroCostoCIF,
    ConfiguracionIVA, FacturaFiscal, FacturaFiscalLinea,
)
from .services import (
    contabilizar_asiento,
    calcular_cif_por_centro,
    generar_libro_compras,
    generar_libro_ventas,
    generar_txt_libro,
    validar_factura_para_libro,
)
from .constants import DRIVER_CIF_CHOICES, METODO_CIF_CHOICES, DRIVER_LABELS


def _empresas_visibles(user):
    """Empresas que el usuario puede ver."""
    if user.is_superuser:
        return Empresa.objects.filter(activa=True)
    perfil = getattr(user, "perfil", None)
    if perfil and perfil.empresa:
        return Empresa.objects.filter(id=perfil.empresa_id)
    return Empresa.objects.none()


def _empresa_activa(request):
    """Devuelve la empresa sobre la que se está trabajando."""
    empresas = _empresas_visibles(request.user)
    if not empresas.exists():
        return None
    empresa_id = request.session.get("contabilidad_empresa_id")
    if empresa_id:
        empresa = empresas.filter(id=empresa_id).first()
        if empresa:
            return empresa
    empresa = empresas.first()
    request.session["contabilidad_empresa_id"] = empresa.id
    return empresa


# =====================================================================
#  COMPROBANTES
# =====================================================================

@solo_rrhh
def comprobante_lista(request):
    """Listado de comprobantes borradores con KPIs."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    qs = ComprobanteBorrador.objects.filter(empresa=empresa).select_related("periodo", "asiento_generado")

    estado = request.GET.get("estado", "").strip()
    q = request.GET.get("q", "").strip()
    if estado:
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(concepto__icontains=q))

    kpis = {
        "borradores": qs.filter(estado="borrador").count(),
        "pendientes": qs.filter(estado="pendiente").count(),
        "contabilizados": qs.filter(estado="contabilizado").count(),
        "total": qs.count(),
    }

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    context = {
        "empresa": empresa,
        "page_obj": page_obj,
        "kpis": kpis,
        "filtros": {"estado": estado, "q": q},
    }
    return render(request, "contabilidad/comprobante_lista.html", context)


@solo_rrhh
def comprobante_nuevo(request):
    """Formulario para crear un nuevo comprobante borrador con líneas dinámicas."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    periodos = PeriodoContable.objects.filter(ejercicio__empresa=empresa, estado="abierto").order_by("-anio", "-mes")
    cuentas = PlanCuenta.objects.filter(empresa=empresa, activa=True, es_agrupadora=False).order_by("codigo")
    centros = CentroCosto.objects.filter(empresa=empresa, activo=True).order_by("codigo")

    if request.method == "POST":
        periodo_id = request.POST.get("periodo")
        fecha_str = request.POST.get("fecha", "").strip()
        concepto = request.POST.get("concepto", "").strip()

        errores = []
        if not periodo_id:
            errores.append("Debe seleccionar un período.")
        if not concepto:
            errores.append("El concepto es obligatorio.")
        try:
            periodo = PeriodoContable.objects.get(id=periodo_id, ejercicio__empresa=empresa)
        except PeriodoContable.DoesNotExist:
            errores.append("Período inválido.")

        lineas_data = []
        i = 0
        while f"linea_cuenta_{i}" in request.POST:
            cuenta_id = request.POST.get(f"linea_cuenta_{i}", "").strip()
            centro_id = request.POST.get(f"linea_centro_{i}", "").strip() or None
            debito_str = request.POST.get(f"linea_debito_{i}", "0").strip() or "0"
            credito_str = request.POST.get(f"linea_credito_{i}", "0").strip() or "0"
            desc = request.POST.get(f"linea_desc_{i}", "").strip()

            if cuenta_id and (Decimal(debito_str) > 0 or Decimal(credito_str) > 0):
                try:
                    lineas_data.append({
                        "cuenta_id": int(cuenta_id),
                        "centro_costo_id": int(centro_id) if centro_id else None,
                        "debito": Decimal(debito_str),
                        "credito": Decimal(credito_str),
                        "descripcion": desc,
                    })
                except (ValueError, InvalidOperation):
                    errores.append(f"Error en la línea {i+1}.")
            i += 1

        if len(lineas_data) < 2:
            errores.append("Debe haber al menos 2 líneas con movimiento.")

        total_d = sum(l["debito"] for l in lineas_data)
        total_c = sum(l["credito"] for l in lineas_data)
        if abs(total_d - total_c) >= Decimal("0.005"):
            errores.append(f"El comprobante no cuadra. Diferencia: {total_d - total_c}")

        if errores:
            for e in errores:
                messages.error(request, e)
        else:
            ultimo = ComprobanteBorrador.objects.filter(empresa=empresa).order_by("-id").first()
            siguiente = (int(ultimo.numero.split("-")[1]) + 1) if ultimo and "-" in ultimo.numero else 1
            numero = f"BOR-{siguiente:06d}"

            with transaction.atomic():
                comp = ComprobanteBorrador.objects.create(
                    empresa=empresa,
                    periodo=periodo,
                    fecha=fecha_str or date.today(),
                    numero=numero,
                    concepto=concepto,
                    creado_por=request.user,
                )
                for idx, l in enumerate(lineas_data):
                    ComprobanteBorradorLinea.objects.create(
                        comprobante=comp,
                        cuenta_id=l["cuenta_id"],
                        centro_costo_id=l["centro_costo_id"],
                        debito=l["debito"],
                        credito=l["credito"],
                        descripcion=l["descripcion"],
                        orden=idx,
                    )
                comp.recalcular_totales()

            messages.success(request, f"Comprobante {numero} creado como borrador.")
            return redirect("contabilidad:comprobante_detalle", comprobante_id=comp.id)

    context = {
        "empresa": empresa,
        "periodos": periodos,
        "cuentas": cuentas,
        "centros": centros,
        "hoy": date.today(),
    }
    return render(request, "contabilidad/comprobante_nuevo.html", context)


@solo_rrhh
def comprobante_detalle(request, comprobante_id):
    """Detalle del comprobante con opción de contabilizar."""
    empresa = _empresa_activa(request)
    comp = get_object_or_404(ComprobanteBorrador, pk=comprobante_id, empresa=empresa)
    return render(request, "contabilidad/comprobante_detalle.html", {"comprobante": comp, "empresa": empresa})


@solo_rrhh
@require_POST
def comprobante_contabilizar(request, comprobante_id):
    """Contabiliza un comprobante borrador: lo mueve a la tabla final Asiento."""
    empresa = _empresa_activa(request)
    comp = get_object_or_404(ComprobanteBorrador, pk=comprobante_id, empresa=empresa)

    if comp.estado == "contabilizado":
        messages.warning(request, "Este comprobante ya fue contabilizado.")
        return redirect("contabilidad:comprobante_detalle", comprobante_id=comp.id)

    if not comp.cuadra:
        messages.error(request, "El comprobante no cuadra y no puede contabilizarse.")
        return redirect("contabilidad:comprobante_detalle", comprobante_id=comp.id)

    if comp.periodo.estado != "abierto":
        messages.error(request, "El período contable está cerrado.")
        return redirect("contabilidad:comprobante_detalle", comprobante_id=comp.id)

    try:
        lineas_data = [
            {
                "cuenta_id": l.cuenta_id,
                "centro_costo_id": l.centro_costo_id,
                "debito": l.debito,
                "credito": l.credito,
                "descripcion": l.descripcion,
            }
            for l in comp.lineas.all()
        ]
        asiento = contabilizar_asiento(
            empresa=comp.empresa,
            periodo=comp.periodo,
            fecha=comp.fecha,
            concepto=comp.concepto,
            lineas_data=lineas_data,
            usuario=request.user,
            origen_modulo="comprobante_borrador",
            origen_id=str(comp.id),
        )
        comp.estado = "contabilizado"
        comp.asiento_generado = asiento
        comp.save(update_fields=["estado", "asiento_generado", "actualizado_at"])
        messages.success(request, f"Comprobante contabilizado. Asiento N° {asiento.numero}.")
    except Exception as e:
        messages.error(request, f"Error al contabilizar: {e}")

    return redirect("contabilidad:comprobante_detalle", comprobante_id=comp.id)


# =====================================================================
#  LIBROS Y ESTADOS FINANCIEROS
# =====================================================================

@solo_rrhh
def libro_diario(request):
    """Listado de asientos contabilizados (libro diario oficial)."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    qs = Asiento.objects.filter(empresa=empresa, estado="contabilizado").select_related("periodo")

    anio = request.GET.get("anio", "")
    mes = request.GET.get("mes", "")
    q = request.GET.get("q", "").strip()
    if anio:
        qs = qs.filter(periodo__anio=anio)
    if mes:
        qs = qs.filter(periodo__mes=mes)
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(concepto__icontains=q))

    qs = qs.order_by("-fecha", "-numero")

    totales = qs.aggregate(total_d=Sum("total_debito"), total_c=Sum("total_credito"))

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    context = {
        "empresa": empresa,
        "page_obj": page_obj,
        "kpis": {
            "total_debito": totales["total_d"] or 0,
            "total_credito": totales["total_c"] or 0,
            "cantidad": qs.count(),
        },
        "filtros": {"anio": anio, "mes": mes, "q": q},
    }
    return render(request, "contabilidad/libro_diario.html", context)


@solo_rrhh
def libro_mayor(request):
    """Libro Mayor: movimientos detallados de una cuenta específica."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    cuentas = PlanCuenta.objects.filter(empresa=empresa, activa=True, es_agrupadora=False).order_by("codigo")
    cuenta_id = request.GET.get("cuenta", "").strip()
    anio = request.GET.get("anio", "").strip()
    mes = request.GET.get("mes", "").strip()

    cuenta = None
    movimientos = []
    saldo_inicial = Decimal("0")
    saldo_acumulado = Decimal("0")
    total_debito = Decimal("0")
    total_credito = Decimal("0")

    if cuenta_id:
        try:
            cuenta = PlanCuenta.objects.get(id=cuenta_id, empresa=empresa)
        except PlanCuenta.DoesNotExist:
            messages.error(request, "Cuenta inválida.")
            return redirect("contabilidad:libro_mayor")

        qs = AsientoLinea.objects.filter(
            asiento__empresa=empresa,
            asiento__estado="contabilizado",
            cuenta=cuenta,
        ).select_related("asiento", "asiento__periodo", "centro_costo").order_by("asiento__fecha", "asiento__numero")

        if anio:
            qs = qs.filter(asiento__periodo__anio=anio)
        if mes:
            qs = qs.filter(asiento__periodo__mes=mes)

        if anio and mes:
            anteriores = AsientoLinea.objects.filter(
                asiento__empresa=empresa,
                asiento__estado="contabilizado",
                cuenta=cuenta,
            ).filter(
                Q(asiento__periodo__anio__lt=anio) |
                Q(asiento__periodo__anio=anio, asiento__periodo__mes__lt=mes)
            )
            for m in anteriores:
                if cuenta.naturaleza == "D":
                    saldo_inicial += m.debito - m.credito
                else:
                    saldo_inicial += m.credito - m.debito

        saldo_acumulado = saldo_inicial

        for m in qs:
            total_debito += m.debito
            total_credito += m.credito
            if cuenta.naturaleza == "D":
                saldo_acumulado += m.debito - m.credito
            else:
                saldo_acumulado += m.credito - m.debito
            movimientos.append({
                "fecha": m.asiento.fecha,
                "numero": m.asiento.numero,
                "concepto": m.asiento.concepto,
                "centro": m.centro_costo.codigo if m.centro_costo else "",
                "descripcion": m.descripcion,
                "debito": m.debito,
                "credito": m.credito,
                "saldo": saldo_acumulado,
            })

    context = {
        "empresa": empresa,
        "cuentas": cuentas,
        "cuenta": cuenta,
        "movimientos": movimientos,
        "saldo_inicial": saldo_inicial,
        "saldo_final": saldo_acumulado,
        "total_debito": total_debito,
        "total_credito": total_credito,
        "filtros": {"cuenta": cuenta_id, "anio": anio, "mes": mes},
    }
    return render(request, "contabilidad/libro_mayor.html", context)


@solo_rrhh
def balance_comprobacion(request):
    """Balance de Comprobación: sumas y saldos por cuenta."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    anio = request.GET.get("anio", "").strip() or str(date.today().year)
    mes = request.GET.get("mes", "").strip()

    qs = AsientoLinea.objects.filter(
        asiento__empresa=empresa,
        asiento__estado="contabilizado",
    )

    if anio:
        qs = qs.filter(asiento__periodo__anio=anio)
    if mes:
        qs = qs.filter(asiento__periodo__mes=mes)

    totales = qs.values(
        "cuenta__id", "cuenta__codigo", "cuenta__nombre",
        "cuenta__tipo", "cuenta__naturaleza",
    ).annotate(
        total_debito=Sum("debito"),
        total_credito=Sum("credito"),
    ).order_by("cuenta__codigo")

    filas = []
    gran_total_debito = Decimal("0")
    gran_total_credito = Decimal("0")
    gran_saldo_deudor = Decimal("0")
    gran_saldo_acreedor = Decimal("0")

    for t in totales:
        td = t["total_debito"] or Decimal("0")
        tc = t["total_credito"] or Decimal("0")
        if t["cuenta__naturaleza"] == "D":
            saldo = td - tc
            saldo_deudor = saldo if saldo > 0 else Decimal("0")
            saldo_acreedor = -saldo if saldo < 0 else Decimal("0")
        else:
            saldo = tc - td
            saldo_acreedor = saldo if saldo > 0 else Decimal("0")
            saldo_deudor = -saldo if saldo < 0 else Decimal("0")

        filas.append({
            "codigo": t["cuenta__codigo"],
            "nombre": t["cuenta__nombre"],
            "tipo": t["cuenta__tipo"],
            "debito": td,
            "credito": tc,
            "saldo_deudor": saldo_deudor,
            "saldo_acreedor": saldo_acreedor,
        })
        gran_total_debito += td
        gran_total_credito += tc
        gran_saldo_deudor += saldo_deudor
        gran_saldo_acreedor += saldo_acreedor

    context = {
        "empresa": empresa,
        "filas": filas,
        "gran_total_debito": gran_total_debito,
        "gran_total_credito": gran_total_credito,
        "gran_saldo_deudor": gran_saldo_deudor,
        "gran_saldo_acreedor": gran_saldo_acreedor,
        "cuadra": abs(gran_total_debito - gran_total_credito) < Decimal("0.01"),
        "filtros": {"anio": anio, "mes": mes},
    }
    return render(request, "contabilidad/balance_comprobacion.html", context)


@solo_rrhh
def estado_resultados(request):
    """Estado de Resultados (P&L) del período."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    anio = request.GET.get("anio", "").strip() or str(date.today().year)
    mes_desde = request.GET.get("mes_desde", "").strip() or "1"
    mes_hasta = request.GET.get("mes_hasta", "").strip() or "12"

    try:
        anio_int = int(anio)
        mes_desde_int = int(mes_desde)
        mes_hasta_int = int(mes_hasta)
    except (ValueError, TypeError):
        anio_int, mes_desde_int, mes_hasta_int = date.today().year, 1, 12

    filtro = Q(asiento__periodo__anio=anio_int) & \
             Q(asiento__periodo__mes__gte=mes_desde_int) & \
             Q(asiento__periodo__mes__lte=mes_hasta_int)

    def _agrupar(tipo):
        return AsientoLinea.objects.filter(
            asiento__empresa=empresa,
            asiento__estado="contabilizado",
            cuenta__tipo=tipo,
        ).filter(filtro).values(
            "cuenta__codigo", "cuenta__nombre", "cuenta__naturaleza",
        ).annotate(
            total_debito=Sum("debito"),
            total_credito=Sum("credito"),
        ).order_by("cuenta__codigo")

    ingresos = []
    total_ingresos = Decimal("0")
    for r in _agrupar("INGRESO"):
        monto = (r["total_credito"] or Decimal("0")) - (r["total_debito"] or Decimal("0"))
        ingresos.append({"codigo": r["cuenta__codigo"], "nombre": r["cuenta__nombre"], "monto": monto})
        total_ingresos += monto

    costos = []
    total_costos = Decimal("0")
    for r in _agrupar("COSTO"):
        monto = (r["total_debito"] or Decimal("0")) - (r["total_credito"] or Decimal("0"))
        costos.append({"codigo": r["cuenta__codigo"], "nombre": r["cuenta__nombre"], "monto": monto})
        total_costos += monto

    gastos = []
    total_gastos = Decimal("0")
    for r in _agrupar("GASTO"):
        monto = (r["total_debito"] or Decimal("0")) - (r["total_credito"] or Decimal("0"))
        gastos.append({"codigo": r["cuenta__codigo"], "nombre": r["cuenta__nombre"], "monto": monto})
        total_gastos += monto

    utilidad_bruta = total_ingresos - total_costos
    utilidad_neta = utilidad_bruta - total_gastos

    context = {
        "empresa": empresa,
        "ingresos": ingresos,
        "costos": costos,
        "gastos": gastos,
        "total_ingresos": total_ingresos,
        "total_costos": total_costos,
        "total_gastos": total_gastos,
        "utilidad_bruta": utilidad_bruta,
        "utilidad_neta": utilidad_neta,
        "filtros": {"anio": anio_int, "mes_desde": mes_desde_int, "mes_hasta": mes_hasta_int},
    }
    return render(request, "contabilidad/estado_resultados.html", context)


@solo_rrhh
def balance_general(request):
    """Balance General: Activo = Pasivo + Patrimonio."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    anio = request.GET.get("anio", "").strip() or str(date.today().year)
    try:
        anio_int = int(anio)
    except (ValueError, TypeError):
        anio_int = date.today().year

    qs = AsientoLinea.objects.filter(
        asiento__empresa=empresa,
        asiento__estado="contabilizado",
        asiento__periodo__anio__lte=anio_int,
    )

    def _agrupar_por_tipo(tipo):
        return qs.filter(cuenta__tipo=tipo).values(
            "cuenta__codigo", "cuenta__nombre", "cuenta__naturaleza",
        ).annotate(
            total_debito=Sum("debito"),
            total_credito=Sum("credito"),
        ).order_by("cuenta__codigo")

    activos = []
    total_activos = Decimal("0")
    for r in _agrupar_por_tipo("ACTIVO"):
        td = r["total_debito"] or Decimal("0")
        tc = r["total_credito"] or Decimal("0")

        if r["cuenta__naturaleza"] == "A":
            monto_visual = tc - td
            total_activos -= monto_visual
            activos.append({
                "codigo": r["cuenta__codigo"],
                "nombre": r["cuenta__nombre"],
                "monto": monto_visual,
                "es_resta": True,
            })
        else:
            monto_visual = td - tc
            total_activos += monto_visual
            activos.append({
                "codigo": r["cuenta__codigo"],
                "nombre": r["cuenta__nombre"],
                "monto": monto_visual,
                "es_resta": False,
            })

    pasivos = []
    total_pasivos = Decimal("0")
    for r in _agrupar_por_tipo("PASIVO"):
        td = r["total_debito"] or Decimal("0")
        tc = r["total_credito"] or Decimal("0")
        monto = tc - td
        pasivos.append({"codigo": r["cuenta__codigo"], "nombre": r["cuenta__nombre"], "monto": monto})
        total_pasivos += monto

    patrimonio = []
    total_patrimonio = Decimal("0")
    for r in _agrupar_por_tipo("PATRIMONIO"):
        td = r["total_debito"] or Decimal("0")
        tc = r["total_credito"] or Decimal("0")
        monto = tc - td
        patrimonio.append({"codigo": r["cuenta__codigo"], "nombre": r["cuenta__nombre"], "monto": monto})
        total_patrimonio += monto

    ingresos_qs = qs.filter(cuenta__tipo="INGRESO", asiento__periodo__anio=anio_int).aggregate(d=Sum("debito"), c=Sum("credito"))
    gastos_qs = qs.filter(cuenta__tipo="GASTO", asiento__periodo__anio=anio_int).aggregate(d=Sum("debito"), c=Sum("credito"))
    costos_qs = qs.filter(cuenta__tipo="COSTO", asiento__periodo__anio=anio_int).aggregate(d=Sum("debito"), c=Sum("credito"))

    total_ingresos = (ingresos_qs["c"] or 0) - (ingresos_qs["d"] or 0)
    total_gastos = (gastos_qs["d"] or 0) - (gastos_qs["c"] or 0)
    total_costos = (costos_qs["d"] or 0) - (costos_qs["c"] or 0)

    utilidad_ejercicio = total_ingresos - total_gastos - total_costos
    total_patrimonio_con_utilidad = total_patrimonio + utilidad_ejercicio
    total_pasivo_patrimonio = total_pasivos + total_patrimonio_con_utilidad

    cuadra = abs(total_activos - total_pasivo_patrimonio) < Decimal("0.01")

    context = {
        "empresa": empresa,
        "activos": activos,
        "pasivos": pasivos,
        "patrimonio": patrimonio,
        "total_activos": total_activos,
        "total_pasivos": total_pasivos,
        "total_patrimonio": total_patrimonio_con_utilidad,
        "utilidad_ejercicio": utilidad_ejercicio,
        "total_pasivo_patrimonio": total_pasivo_patrimonio,
        "cuadra": cuadra,
        "filtros": {"anio": anio_int},
    }
    return render(request, "contabilidad/balance_general.html", context)


@solo_rrhh
def dashboard_contable(request):
    """Dashboard con KPIs y evolución mensual."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    anio = request.GET.get("anio", "").strip() or str(date.today().year)
    try:
        anio_int = int(anio)
    except (ValueError, TypeError):
        anio_int = date.today().year

    total_asientos = Asiento.objects.filter(empresa=empresa, estado="contabilizado", periodo__anio=anio_int).count()
    total_borradores = ComprobanteBorrador.objects.filter(empresa=empresa, estado="borrador").count()

    meses_data = []
    for mes in range(1, 13):
        agg = AsientoLinea.objects.filter(
            asiento__empresa=empresa,
            asiento__estado="contabilizado",
            asiento__periodo__anio=anio_int,
            asiento__periodo__mes=mes,
        ).aggregate(d=Sum("debito"), c=Sum("credito"))
        meses_data.append({
            "mes": mes,
            "debito": float(agg["d"] or 0),
            "credito": float(agg["c"] or 0),
        })

    top_cuentas = AsientoLinea.objects.filter(
        asiento__empresa=empresa,
        asiento__estado="contabilizado",
        asiento__periodo__anio=anio_int,
    ).values("cuenta__codigo", "cuenta__nombre").annotate(
        movimientos=Sum("debito") + Sum("credito"),
    ).order_by("-movimientos")[:5]

    ultimos = Asiento.objects.filter(empresa=empresa, estado="contabilizado").order_by("-fecha", "-numero")[:5]

    context = {
        "empresa": empresa,
        "kpis": {
            "total_asientos": total_asientos,
            "total_borradores": total_borradores,
        },
        "meses_data": meses_data,
        "top_cuentas": top_cuentas,
        "ultimos": ultimos,
        "filtros": {"anio": anio_int},
    }
    return render(request, "contabilidad/dashboard.html", context)


# =====================================================================
#  INTEGRACIÓN CON NÓMINA
# =====================================================================

@solo_rrhh
def configuracion_nomina(request):
    """Vista de configuración de cuentas contables por concepto de nómina."""
    from .models import ConfiguracionContableNomina
    from rrhh.models import ConceptoNomina

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    conceptos = ConceptoNomina.objects.filter(
        Q(empresa=empresa) | Q(empresa__isnull=True),
        activo=True,
    ).order_by("tipo", "prioridad", "codigo")

    cuentas = PlanCuenta.objects.filter(empresa=empresa, activa=True, es_agrupadora=False).order_by("codigo")

    if request.method == "POST":
        for c in conceptos:
            cuenta_id = request.POST.get(f"cuenta_{c.id}", "").strip()
            cuenta_pasivo_id = request.POST.get(f"cuenta_pasivo_{c.id}", "").strip()

            if cuenta_id:
                try:
                    cuenta = PlanCuenta.objects.get(id=cuenta_id, empresa=empresa)
                    cuenta_pasivo = None
                    if cuenta_pasivo_id:
                        cuenta_pasivo = PlanCuenta.objects.get(id=cuenta_pasivo_id, empresa=empresa)

                    ConfiguracionContableNomina.objects.update_or_create(
                        empresa=empresa,
                        concepto=c,
                        defaults={"cuenta": cuenta, "cuenta_pasivo": cuenta_pasivo},
                    )
                except PlanCuenta.DoesNotExist:
                    pass
            else:
                ConfiguracionContableNomina.objects.filter(
                    empresa=empresa, concepto=c
                ).delete()
        messages.success(request, "Configuración contable de nómina guardada.")
        return redirect("contabilidad:configuracion_nomina")

    configs = {
        c.concepto_id: c
        for c in ConfiguracionContableNomina.objects.filter(empresa=empresa).select_related("cuenta", "cuenta_pasivo")
    }

    filas = []
    for c in conceptos:
        config = configs.get(c.id)
        filas.append({
            "concepto": c,
            "cuenta_id": config.cuenta_id if config else None,
            "cuenta_pasivo_id": config.cuenta_pasivo_id if config else None,
        })

    context = {
        "empresa": empresa,
        "cuentas": cuentas,
        "filas": filas,
    }
    return render(request, "contabilidad/configuracion_nomina.html", context)


@solo_rrhh
@require_POST
def generar_asiento_nomina_view(request, periodo_id):
    """Vista que dispara la generación del asiento de nómina."""
    from rrhh.models import PeriodoNomina
    from .services import generar_asiento_nomina

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    try:
        periodo = PeriodoNomina.objects.get(pk=periodo_id, empresa=empresa)
    except PeriodoNomina.DoesNotExist:
        messages.error(request, "Período de nómina no encontrado.")
        return redirect("rrhh:dashboard")

    try:
        asiento = generar_asiento_nomina(empresa, periodo, usuario=request.user)
        messages.success(request, f"Asiento N° {asiento.numero} generado correctamente.")
    except Exception as e:
        messages.error(request, f"Error al generar asiento: {e}")

    try:
        return redirect("rrhh:nomina_periodo_detalle", periodo_id=periodo_id)
    except Exception:
        return redirect("rrhh:dashboard")


# =====================================================================
#  ACTIVOS FIJOS / DEPRECIACIÓN
# =====================================================================

@solo_rrhh
def depreciacion_lista(request):
    """Lista de depreciaciones y botón para ejecutar la del mes."""
    from activos.models import DepreciacionActivo, ActivoFijo
    from activos.services import depreciar_mes

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    if request.method == "POST":
        anio = request.POST.get("anio", "").strip()
        mes = request.POST.get("mes", "").strip()
        try:
            anio_int = int(anio)
            mes_int = int(mes)
            resultado = depreciar_mes(empresa, anio_int, mes_int, usuario=request.user)
            if resultado["errores"]:
                for activo, error in resultado["errores"]:
                    messages.error(request, f"{activo.codigo}: {error}")
            if resultado["asiento"]:
                messages.success(request, resultado["mensaje"])
            else:
                messages.info(request, resultado["mensaje"])
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect("contabilidad:depreciacion_lista")

    qs = DepreciacionActivo.objects.filter(
        activo__empresa=empresa
    ).select_related("activo", "asiento").order_by("-fecha", "activo__codigo")

    total_depreciado = qs.aggregate(total=Sum("monto"))["total"] or 0
    cantidad_activos = ActivoFijo.objects.filter(empresa=empresa, activo=True).count()

    hoy = timezone.now().date()

    context = {
        "empresa": empresa,
        "depreciaciones": qs[:200],
        "kpis": {
            "total_depreciado": total_depreciado,
            "cantidad_activos": cantidad_activos,
        },
        "hoy": hoy,
        "meses": [
            (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
            (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
            (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
        ],
    }
    return render(request, "contabilidad/depreciacion_lista.html", context)


# =====================================================================
#  FASE 3: PRESUPUESTO (GERENCIAL)
# =====================================================================

MESES_PRESUPUESTO = [
    ("enero", "Ene"), ("febrero", "Feb"), ("marzo", "Mar"),
    ("abril", "Abr"), ("mayo", "May"), ("junio", "Jun"),
    ("julio", "Jul"), ("agosto", "Ago"), ("septiembre", "Sep"),
    ("octubre", "Oct"), ("noviembre", "Nov"), ("diciembre", "Dic"),
]
MESES_KEYS = [k for k, _ in MESES_PRESUPUESTO]
MESES_LABELS = [v for _, v in MESES_PRESUPUESTO]


@solo_rrhh
def presupuesto_lista(request):
    """Listado de presupuestos con opción de crear uno nuevo."""
    from .models import Presupuesto, EjercicioFiscal

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    if request.method == "POST":
        ejercicio_id = request.POST.get("ejercicio", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        try:
            ejercicio = EjercicioFiscal.objects.get(id=ejercicio_id, empresa=empresa)
            presupuesto = Presupuesto.objects.create(
                empresa=empresa,
                ejercicio=ejercicio,
                nombre=nombre,
            )
            messages.success(request, f"Presupuesto '{presupuesto.nombre}' creado exitosamente.")
            return redirect("contabilidad:presupuesto_detalle", presupuesto_id=presupuesto.id)
        except EjercicioFiscal.DoesNotExist:
            messages.error(request, "Ejercicio fiscal inválido.")
        except Exception as e:
            messages.error(request, f"Error al crear presupuesto: {e}")
        return redirect("contabilidad:presupuesto_lista")

    presupuestos = Presupuesto.objects.filter(empresa=empresa).select_related("ejercicio").order_by("-ejercicio__anio", "nombre")
    ejercicios = EjercicioFiscal.objects.filter(empresa=empresa).order_by("-anio")

    context = {
        "empresa": empresa,
        "presupuestos": presupuestos,
        "ejercicios": ejercicios,
    }
    return render(request, "contabilidad/presupuesto_lista.html", context)


@solo_rrhh
def presupuesto_detalle(request, presupuesto_id):
    """Grilla de carga mensual de las líneas del presupuesto."""
    from .models import Presupuesto, PresupuestoLinea

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    presupuesto = get_object_or_404(Presupuesto, pk=presupuesto_id, empresa=empresa)

    if request.method == "POST":
        lineas_keys = request.POST.getlist("linea_key")
        lineas_guardadas = 0
        errores = []

        with transaction.atomic():
            for key in lineas_keys:
                if key.startswith("existing_"):
                    try:
                        linea_id = int(key.replace("existing_", ""))
                        linea = PresupuestoLinea.objects.get(
                            id=linea_id, presupuesto=presupuesto
                        )
                        cuenta = linea.cuenta
                        centro = linea.centro_costo
                    except (ValueError, PresupuestoLinea.DoesNotExist):
                        errores.append(f"Línea existente inválida: {key}")
                        continue
                elif key.startswith("new_"):
                    cuenta_id = request.POST.get(f"cuenta_id_{key}", "").strip()
                    centro_id = request.POST.get(f"centro_id_{key}", "").strip() or None
                    if not cuenta_id:
                        errores.append(f"Falta cuenta para {key}")
                        continue
                    cuenta = PlanCuenta.objects.filter(id=cuenta_id, empresa=empresa).first()
                    if not cuenta:
                        errores.append(f"Cuenta inválida para {key}")
                        continue
                    centro = (
                        CentroCosto.objects.filter(id=centro_id, empresa=empresa).first()
                        if centro_id else None
                    )
                    linea = None
                else:
                    try:
                        cuenta_id = int(key)
                    except ValueError:
                        errores.append(f"Fila inválida: {key}")
                        continue
                    cuenta = PlanCuenta.objects.filter(id=cuenta_id, empresa=empresa).first()
                    if not cuenta:
                        errores.append(f"Cuenta inválida: {key}")
                        continue
                    centro_id = request.POST.get(f"centro_{cuenta_id}", "").strip() or None
                    centro = (
                        CentroCosto.objects.filter(id=centro_id, empresa=empresa).first()
                        if centro_id else None
                    )
                    linea = None

                if linea is None:
                    linea, _created = PresupuestoLinea.objects.get_or_create(
                        presupuesto=presupuesto,
                        cuenta=cuenta,
                        centro_costo=centro,
                    )

                for mes_key in MESES_KEYS:
                    input_name = f"monto_{mes_key}_{key}"
                    valor_str = request.POST.get(input_name, "0").strip() or "0"
                    try:
                        setattr(linea, f"monto_{mes_key}", Decimal(valor_str))
                    except (InvalidOperation, ValueError):
                        setattr(linea, f"monto_{mes_key}", Decimal("0"))

                linea.save()
                lineas_guardadas += 1

        if errores:
            for e in errores:
                messages.warning(request, e)
        messages.success(
            request,
            f"Presupuesto guardado. {lineas_guardadas} línea(s) actualizada(s).",
        )
        return redirect("contabilidad:presupuesto_detalle", presupuesto_id=presupuesto.id)

    cuentas = PlanCuenta.objects.filter(
        empresa=empresa, activa=True, es_agrupadora=False,
    ).order_by("codigo")

    centros = CentroCosto.objects.filter(empresa=empresa, activo=True).order_by("codigo")

    lineas_por_cuenta = {}
    for linea in presupuesto.lineas.select_related("cuenta", "centro_costo").all():
        lineas_por_cuenta.setdefault(linea.cuenta_id, []).append(linea)

    cuentas_con_linea = []
    for c in cuentas:
        lineas_cuenta = lineas_por_cuenta.get(c.id, [])

        if not lineas_cuenta:
            valores_vacios = [{"key": k, "monto": Decimal("0")} for k in MESES_KEYS]
            cuentas_con_linea.append({
                "cuenta": c,
                "lineas": [{
                    "linea": None,
                    "linea_key": str(c.id),
                    "centro": None,
                    "valores_meses": valores_vacios,
                    "total": Decimal("0"),
                }],
                "total_cuenta": Decimal("0"),
            })
            continue

        filas = []
        total_cuenta = Decimal("0")
        for linea in lineas_cuenta:
            valores = []
            total_linea = Decimal("0")
            for k in MESES_KEYS:
                monto = getattr(linea, f"monto_{k}") or Decimal("0")
                valores.append({"key": k, "monto": monto})
                total_linea += monto
            filas.append({
                "linea": linea,
                "linea_key": f"existing_{linea.id}",
                "centro": linea.centro_costo,
                "valores_meses": valores,
                "total": total_linea,
            })
            total_cuenta += total_linea

        cuentas_con_linea.append({
            "cuenta": c,
            "lineas": filas,
            "total_cuenta": total_cuenta,
        })

    context = {
        "empresa": empresa,
        "presupuesto": presupuesto,
        "cuentas_con_linea": cuentas_con_linea,
        "centros": centros,
        "meses": MESES_PRESUPUESTO,
        "meses_labels": MESES_LABELS,
    }
    return render(request, "contabilidad/presupuesto_detalle.html", context)


def _calcular_reales_vs_presupuesto(presupuesto, centro_costo_id=None):
    """Calcula el diccionario de reales por (cuenta_id, mes) para el presupuesto."""
    empresa = presupuesto.empresa
    anio = presupuesto.ejercicio.anio

    qs = AsientoLinea.objects.filter(
        asiento__empresa=empresa,
        asiento__estado="contabilizado",
        asiento__periodo__anio=anio,
    )
    if centro_costo_id:
        qs = qs.filter(centro_costo_id=centro_costo_id)

    reales = qs.values(
        "cuenta_id",
        "cuenta__tipo",
        "asiento__periodo__mes",
    ).annotate(
        total_debito=Sum("debito"),
        total_credito=Sum("credito"),
    )

    reales_dict = {}
    for r in reales:
        td = r["total_debito"] or Decimal("0")
        tc = r["total_credito"] or Decimal("0")
        if r["cuenta__tipo"] == "INGRESO":
            monto = tc - td
        else:
            monto = td - tc
        reales_dict[(r["cuenta_id"], r["asiento__periodo__mes"])] = monto

    return reales_dict


@solo_rrhh
def presupuesto_vs_real(request, presupuesto_id):
    """Reporte: comparación Presupuesto vs Real con desviaciones."""
    from .models import Presupuesto
    from .presupuesto_engine import calcular_desviacion

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    presupuesto = get_object_or_404(Presupuesto, pk=presupuesto_id, empresa=empresa)
    centros = CentroCosto.objects.filter(empresa=empresa, activo=True).order_by("codigo")

    centro_id_str = request.GET.get("centro", "").strip()
    centro_filtro = None
    if centro_id_str:
        try:
            centro_filtro = CentroCosto.objects.get(
                id=int(centro_id_str), empresa=empresa
            )
        except (ValueError, CentroCosto.DoesNotExist):
            centro_filtro = None

    reales_dict = _calcular_reales_vs_presupuesto(
        presupuesto,
        centro_costo_id=centro_filtro.id if centro_filtro else None,
    )

    filas = []
    lineas_qs = presupuesto.lineas.select_related("cuenta", "centro_costo")
    if centro_filtro:
        lineas_qs = lineas_qs.filter(centro_costo=centro_filtro)

    totales_por_mes = [
        {"presupuesto": Decimal("0"), "real": Decimal("0")} for _ in MESES_KEYS
    ]
    gran_total_pres = Decimal("0")
    gran_total_real = Decimal("0")

    for linea in lineas_qs:
        cuenta = linea.cuenta
        meses_data = []
        for idx, mes_key in enumerate(MESES_KEYS):
            monto_pres = getattr(linea, f"monto_{mes_key}") or Decimal("0")
            monto_real = reales_dict.get((cuenta.id, idx + 1), Decimal("0"))
            desv = calcular_desviacion(monto_pres, monto_real, cuenta.tipo)
            meses_data.append(desv)
            totales_por_mes[idx]["presupuesto"] += monto_pres
            totales_por_mes[idx]["real"] += monto_real

        total_pres = sum(m["presupuesto"] for m in meses_data)
        total_real = sum(m["real"] for m in meses_data)
        total_desv = calcular_desviacion(total_pres, total_real, cuenta.tipo)

        gran_total_pres += total_pres
        gran_total_real += total_real

        filas.append({
            "cuenta": cuenta,
            "centro_costo": linea.centro_costo,
            "meses": meses_data,
            "total_presupuesto": total_pres,
            "total_real": total_real,
            "total_desviacion": total_desv,
        })

    gran_total_desv_monto = gran_total_real - gran_total_pres
    gran_total_desv_pct = (
        (gran_total_desv_monto / gran_total_pres * 100) if gran_total_pres != 0 else Decimal("0")
    )

    qs_export = f"?centro={centro_filtro.id}" if centro_filtro else ""

    context = {
        "empresa": empresa,
        "presupuesto": presupuesto,
        "filas": filas,
        "meses_labels": MESES_LABELS,
        "centros": centros,
        "centro_filtro": centro_filtro,
        "qs_export": qs_export,
        "totales_por_mes": totales_por_mes,
        "gran_total_pres": gran_total_pres,
        "gran_total_real": gran_total_real,
        "gran_total_desv_monto": gran_total_desv_monto,
        "gran_total_desv_pct": gran_total_desv_pct,
    }
    return render(request, "contabilidad/presupuesto_vs_real.html", context)


@solo_rrhh
def presupuesto_vs_real_export(request, presupuesto_id):
    """Exporta el reporte Presupuesto vs Real a Excel."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from .models import Presupuesto
    from .presupuesto_engine import calcular_desviacion

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    presupuesto = get_object_or_404(Presupuesto, pk=presupuesto_id, empresa=empresa)

    centro_id_str = request.GET.get("centro", "").strip()
    centro_filtro = None
    if centro_id_str:
        try:
            centro_filtro = CentroCosto.objects.get(
                id=int(centro_id_str), empresa=empresa
            )
        except (ValueError, CentroCosto.DoesNotExist):
            centro_filtro = None

    reales_dict = _calcular_reales_vs_presupuesto(
        presupuesto,
        centro_costo_id=centro_filtro.id if centro_filtro else None,
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Presupuesto vs Real"

    ws.merge_cells("A1:P1")
    ws["A1"] = f"Presupuesto vs Real — {presupuesto.nombre} ({presupuesto.ejercicio.anio})"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A2:P2")
    subtitulo = f"Empresa: {empresa.razon_social}"
    if centro_filtro:
        subtitulo += f"  |  Centro de Costo: {centro_filtro.codigo} - {centro_filtro.nombre}"
    ws["A2"] = subtitulo
    ws["A2"].font = Font(italic=True, size=10)
    ws["A2"].alignment = Alignment(horizontal="center")

    headers = ["Cuenta", "Nombre", "Centro Costo"]
    for label in MESES_LABELS:
        headers.append(f"{label} Pres.")
        headers.append(f"{label} Real")
    headers.extend(["Total Pres.", "Total Real", "Desviación", "Estado"])

    header_row = 4
    for col, h in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    lineas_qs = presupuesto.lineas.select_related("cuenta", "centro_costo")
    if centro_filtro:
        lineas_qs = lineas_qs.filter(centro_costo=centro_filtro)

    totales_por_mes = [
        {"presupuesto": Decimal("0"), "real": Decimal("0")} for _ in MESES_KEYS
    ]
    gran_total_pres = Decimal("0")
    gran_total_real = Decimal("0")

    fila_actual = header_row + 1
    for linea in lineas_qs:
        cuenta = linea.cuenta
        ws.cell(row=fila_actual, column=1, value=cuenta.codigo)
        ws.cell(row=fila_actual, column=2, value=cuenta.nombre)
        ws.cell(
            row=fila_actual, column=3,
            value=linea.centro_costo.codigo if linea.centro_costo else "",
        )

        col = 4
        total_pres = Decimal("0")
        total_real = Decimal("0")
        for idx, mes_key in enumerate(MESES_KEYS):
            monto_pres = getattr(linea, f"monto_{mes_key}") or Decimal("0")
            monto_real = reales_dict.get((cuenta.id, idx + 1), Decimal("0"))
            ws.cell(row=fila_actual, column=col, value=float(monto_pres))
            ws.cell(row=fila_actual, column=col + 1, value=float(monto_real))
            total_pres += monto_pres
            total_real += monto_real
            totales_por_mes[idx]["presupuesto"] += monto_pres
            totales_por_mes[idx]["real"] += monto_real
            col += 2

        total_desv = calcular_desviacion(total_pres, total_real, cuenta.tipo)
        ws.cell(row=fila_actual, column=col, value=float(total_pres))
        ws.cell(row=fila_actual, column=col + 1, value=float(total_real))
        ws.cell(row=fila_actual, column=col + 2, value=float(total_desv["diferencia"]))
        ws.cell(row=fila_actual, column=col + 3, value=total_desv["estado"])

        gran_total_pres += total_pres
        gran_total_real += total_real

        fila_actual += 1

    fila_gran_total = fila_actual
    ws.cell(row=fila_gran_total, column=1, value="GRAN TOTAL")

    col = 4
    for idx in range(len(MESES_KEYS)):
        ws.cell(row=fila_gran_total, column=col, value=float(totales_por_mes[idx]["presupuesto"]))
        ws.cell(row=fila_gran_total, column=col + 1, value=float(totales_por_mes[idx]["real"]))
        col += 2

    gran_total_desv_monto = gran_total_real - gran_total_pres
    gran_total_desv_pct = (
        (gran_total_desv_monto / gran_total_pres * 100) if gran_total_pres != 0 else Decimal("0")
    )

    ws.cell(row=fila_gran_total, column=col, value=float(gran_total_pres))
    ws.cell(row=fila_gran_total, column=col + 1, value=float(gran_total_real))
    ws.cell(row=fila_gran_total, column=col + 2, value=float(gran_total_desv_monto))
    ws.cell(row=fila_gran_total, column=col + 3, value=f"{gran_total_desv_pct:.1f}%")

    for c in range(1, col + 4):
        cell = ws.cell(row=fila_gran_total, column=c)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")

    for row in ws.iter_rows(min_row=header_row + 1, max_row=fila_gran_total, min_col=4, max_col=col + 2):
        for cell in row:
            cell.number_format = '#,##0.00'

    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 30
    ws.column_dimensions["C"].width = 12
    for col_letter in ["D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O",
                       "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
                       "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH"]:
        ws.column_dimensions[col_letter].width = 13

    ws.freeze_panes = ws.cell(row=header_row + 1, column=4)

    nombre_archivo = f"presupuesto_vs_real_{presupuesto.id}_{presupuesto.ejercicio.anio}"
    if centro_filtro:
        nombre_archivo += f"_cc_{centro_filtro.codigo}"
    nombre_archivo += ".xlsx"

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    wb.save(response)
    return response


@solo_rrhh
def dashboard_gerencial(request, presupuesto_id):
    """Dashboard Gerencial con KPIs y gráficos de ejecución presupuestaria."""
    from .models import Presupuesto
    from .presupuesto_engine import calcular_desviacion

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    presupuesto = get_object_or_404(Presupuesto, pk=presupuesto_id, empresa=empresa)
    anio = presupuesto.ejercicio.anio

    reales_por_mes = AsientoLinea.objects.filter(
        asiento__empresa=empresa,
        asiento__estado="contabilizado",
        asiento__periodo__anio=anio,
    ).values(
        "asiento__periodo__mes",
        "cuenta__tipo",
    ).annotate(
        total_debito=Sum("debito"),
        total_credito=Sum("credito"),
    )

    reales_dict = {
        m: {"INGRESO": Decimal("0"), "GASTO": Decimal("0"), "COSTO": Decimal("0")}
        for m in range(1, 13)
    }
    for r in reales_por_mes:
        td = r["total_debito"] or Decimal("0")
        tc = r["total_credito"] or Decimal("0")
        tipo = r["cuenta__tipo"]
        mes = r["asiento__periodo__mes"]
        if tipo in reales_dict[mes]:
            if tipo == "INGRESO":
                reales_dict[mes][tipo] += tc - td
            else:
                reales_dict[mes][tipo] += td - tc

    pres_ingreso_mes = []
    pres_egreso_mes = []
    pres_bruto_mes = []

    real_ingreso_mes = []
    real_egreso_mes = []
    real_bruto_mes = []

    for idx, mes_key in enumerate(MESES_KEYS, start=1):
        pres_ing = Decimal("0")
        pres_egr = Decimal("0")
        for linea in presupuesto.lineas.all():
            monto = getattr(linea, f"monto_{mes_key}") or Decimal("0")
            if linea.cuenta.tipo == "INGRESO":
                pres_ing += monto
            else:
                pres_egr += monto

        real_ing = reales_dict[idx]["INGRESO"]
        real_egr = reales_dict[idx]["GASTO"] + reales_dict[idx]["COSTO"]

        pres_ingreso_mes.append(float(pres_ing))
        pres_egreso_mes.append(float(pres_egr))
        pres_bruto_mes.append(float(pres_ing + pres_egr))

        real_ingreso_mes.append(float(real_ing))
        real_egreso_mes.append(float(real_egr))
        real_bruto_mes.append(float(real_ing + real_egr))

    total_pres_ingreso = sum(pres_ingreso_mes)
    total_pres_egreso = sum(pres_egreso_mes)
    total_real_ingreso = sum(real_ingreso_mes)
    total_real_egreso = sum(real_egreso_mes)

    ejecucion_ingreso = (
        (total_real_ingreso / total_pres_ingreso * 100) if total_pres_ingreso > 0 else 0
    )
    ejecucion_egreso = (
        (total_real_egreso / total_pres_egreso * 100) if total_pres_egreso > 0 else 0
    )

    desviaciones = []
    for linea in presupuesto.lineas.select_related("cuenta").all():
        total_pres = sum(
            (getattr(linea, f"monto_{k}") or Decimal("0")) for k in MESES_KEYS
        )
        real_cuenta = AsientoLinea.objects.filter(
            asiento__empresa=empresa,
            asiento__estado="contabilizado",
            asiento__periodo__anio=anio,
            cuenta=linea.cuenta,
        ).aggregate(d=Sum("debito"), c=Sum("credito"))

        if linea.cuenta.tipo == "INGRESO":
            total_real = (real_cuenta["c"] or 0) - (real_cuenta["d"] or 0)
        else:
            total_real = (real_cuenta["d"] or 0) - (real_cuenta["c"] or 0)

        desv = calcular_desviacion(total_pres, total_real, linea.cuenta.tipo)
        desviaciones.append({
            "cuenta": linea.cuenta,
            "presupuesto": total_pres,
            "real": total_real,
            "diferencia": abs(desv["diferencia"]),
            "desviacion": desv,
        })

    desviaciones.sort(key=lambda x: x["diferencia"], reverse=True)
    top_desviaciones = desviaciones[:5]

    total_presupuesto_legacy = total_pres_ingreso + total_pres_egreso
    total_real_legacy = total_real_ingreso + total_real_egreso
    diferencia_total_legacy = total_real_legacy - total_presupuesto_legacy
    porcentaje_ejecucion_legacy = (
        (total_real_legacy / total_presupuesto_legacy * 100)
        if total_presupuesto_legacy > 0 else 0
    )

    context = {
        "empresa": empresa,
        "presupuesto": presupuesto,
        "kpis": {
            "total_pres_ingreso": total_pres_ingreso,
            "total_pres_egreso": total_pres_egreso,
            "total_real_ingreso": total_real_ingreso,
            "total_real_egreso": total_real_egreso,
            "ejecucion_ingreso": ejecucion_ingreso,
            "ejecucion_egreso": ejecucion_egreso,
            "total_presupuesto": total_presupuesto_legacy,
            "total_real": total_real_legacy,
            "diferencia_total": diferencia_total_legacy,
            "porcentaje_ejecucion": porcentaje_ejecucion_legacy,
        },
        "meses_labels": MESES_LABELS,
        "pres_ingreso_mes": pres_ingreso_mes,
        "pres_egreso_mes": pres_egreso_mes,
        "real_ingreso_mes": real_ingreso_mes,
        "real_egreso_mes": real_egreso_mes,
        "presupuesto_por_mes": pres_bruto_mes,
        "real_por_mes": real_bruto_mes,
        "top_desviaciones": top_desviaciones,
    }
    return render(request, "contabilidad/dashboard_gerencial.html", context)


# =====================================================================
#  FASE 4: COSTOS
# =====================================================================

@solo_rrhh
def costos_ordenes_lista(request):
    """Listado de órdenes de producción con opción de costear."""
    from costos.models import OrdenProduccion
    from costos.services import consolidar_costo_orden

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    if request.method == "POST":
        orden_id = request.POST.get("orden_id")
        try:
            orden = OrdenProduccion.objects.get(id=orden_id, empresa=empresa)
            fecha_ref = orden.fecha_fin or orden.fecha_inicio
            periodo = PeriodoContable.objects.filter(
                ejercicio__empresa=empresa,
                anio=fecha_ref.year,
                mes=fecha_ref.month,
                estado="abierto"
            ).first()

            if not periodo:
                messages.error(request, f"No hay período contable abierto para {fecha_ref.year}-{fecha_ref.month:02d}.")
            else:
                costos = consolidar_costo_orden(orden, periodo, usuario=request.user)
                messages.success(request, f"Orden {orden.numero} costeada. Costo Total: Bs. {costos['costo_total']:,.2f}")
        except Exception as e:
            messages.error(request, f"Error al costear: {e}")
        return redirect("contabilidad:costos_ordenes_lista")

    ordenes = OrdenProduccion.objects.filter(empresa=empresa).select_related("empresa").order_by("-fecha_inicio")

    context = {
        "empresa": empresa,
        "ordenes": ordenes,
    }
    return render(request, "contabilidad/costos_ordenes_lista.html", context)


@solo_rrhh
def costos_sincronizar(request):
    """Vista para sincronizar los costos del mes."""
    from costos.services import sincronizar_todos_los_costos

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    hoy = timezone.now().date()

    if request.method == "POST":
        anio = request.POST.get("anio", "").strip()
        mes = request.POST.get("mes", "").strip()
        try:
            anio_int = int(anio)
            mes_int = int(mes)
            resultado = sincronizar_todos_los_costos(empresa, anio_int, mes_int, usuario=request.user)

            messages.success(
                request,
                f"Sincronización completada: "
                f"{resultado['maquinas']} máquinas, "
                f"{resultado['mano_obra']} empleados, "
                f"{resultado['insumos']} insumos."
            )
            if resultado["errores"]:
                for error in resultado["errores"]:
                    messages.error(request, error)
        except Exception as e:
            messages.error(request, f"Error al sincronizar: {e}")
        return redirect("contabilidad:costos_sincronizar")

    from costos.models import RecursoCosto
    costos = RecursoCosto.objects.filter(
        recurso__empresa=empresa,
    ).select_related("recurso", "periodo").order_by("-periodo__anio", "-periodo__mes", "recurso__nombre")

    context = {
        "empresa": empresa,
        "costos": costos[:100],
        "hoy": hoy,
        "meses": [
            (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
            (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
            (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
        ],
    }
    return render(request, "contabilidad/costos_sincronizar.html", context)


# =====================================================================
#  FASE 2.5: REPARTO DE CIF
# =====================================================================

@solo_rrhh
def cif_reporte(request):
    """Reporte de distribución de CIF por centro de costo."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    config = ConfiguracionCIF.objects.filter(empresa=empresa).first()
    periodos = PeriodoContable.objects.filter(
        ejercicio__empresa=empresa,
    ).order_by("-anio", "-mes")[:24]

    periodo_id = request.GET.get("periodo", "").strip()
    periodo = None
    if periodo_id:
        try:
            periodo = PeriodoContable.objects.get(id=int(periodo_id), ejercicio__empresa=empresa)
        except (ValueError, PeriodoContable.DoesNotExist):
            periodo = None

    monto_str = request.GET.get("monto", "").strip()
    try:
        monto = Decimal(monto_str) if monto_str else Decimal("100000")
    except (InvalidOperation, ValueError):
        monto = Decimal("100000")

    resultado = calcular_cif_por_centro(empresa, monto, periodo=periodo)

    chart_labels = [c["centro_costo"].codigo for c in resultado["centros"]]
    chart_data = [float(c["cif_asignado"]) for c in resultado["centros"]]

    context = {
        "empresa": empresa,
        "config": config,
        "periodos": periodos,
        "periodo": periodo,
        "monto": monto,
        "resultado": resultado,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
        "driver_label": DRIVER_LABELS.get(resultado.get("driver"), resultado.get("driver") or "—"),
    }
    return render(request, "contabilidad/cif_reporte.html", context)


@solo_rrhh
def cif_reporte_export(request):
    """Exporta el reporte de CIF a Excel."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    monto_str = request.GET.get("monto", "").strip()
    try:
        monto = Decimal(monto_str) if monto_str else Decimal("100000")
    except (InvalidOperation, ValueError):
        monto = Decimal("100000")

    resultado = calcular_cif_por_centro(empresa, monto)

    wb = Workbook()
    ws = wb.active
    ws.title = "CIF por Centro"

    ws.merge_cells("A1:G1")
    ws["A1"] = f"Distribución de CIF — {empresa.razon_social}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A2:G2")
    ws["A2"] = (
        f"Driver: {resultado['driver']}  |  "
        f"Pivot: {resultado['centro_pivot']}  |  "
        f"CIF Total: Bs. {monto:,.2f}"
    )
    ws["A2"].font = Font(italic=True, size=10)
    ws["A2"].alignment = Alignment(horizontal="center")

    headers = ["Código", "Centro de Costo", "Área (cm²)", "Coef.", "%", "CIF Asignado", "Tipo"]
    header_row = 4
    for col, h in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    fila = header_row + 1
    for c in resultado["centros"]:
        ws.cell(row=fila, column=1, value=c["centro_costo"].codigo)
        ws.cell(row=fila, column=2, value=c["centro_costo"].nombre)
        ws.cell(row=fila, column=3, value=float(c["valor_driver"]))
        ws.cell(row=fila, column=4, value=float(c["coeficiente"]))
        ws.cell(row=fila, column=5, value=f"{c['porcentaje']:.2f}%")
        ws.cell(row=fila, column=6, value=float(c["cif_asignado"]))
        ws.cell(row=fila, column=7, value="PIVOT" if c["centro_costo"] == resultado["centro_pivot"] else "")
        fila += 1

    ws.cell(row=fila, column=1, value="TOTAL")
    ws.cell(row=fila, column=6, value=float(resultado["total_asignado"]))
    for col in range(1, 8):
        cell = ws.cell(row=fila, column=col)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")

    for row in ws.iter_rows(min_row=header_row + 1, max_row=fila, min_col=3, max_col=6):
        for cell in row:
            cell.number_format = '#,##0.00'

    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 35
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 10
    ws.column_dimensions["E"].width = 8
    ws.column_dimensions["F"].width = 18
    ws.column_dimensions["G"].width = 10

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="cif_por_centro.xlsx"'
    wb.save(response)
    return response


@solo_rrhh
def cif_configuracion(request):
    """Editor de la configuración CIF: cabecera + detalle por centro."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    config = ConfiguracionCIF.objects.filter(empresa=empresa).first()
    centros = CentroCosto.objects.filter(empresa=empresa, activo=True).order_by("codigo")

    if request.method == "POST":
        accion = request.POST.get("accion", "guardar")

        if accion == "crear":
            if config:
                messages.warning(request, "Ya existe una configuración CIF.")
            else:
                config = ConfiguracionCIF.objects.create(
                    empresa=empresa,
                    driver=request.POST.get("driver") or "AREA",
                    metodo=request.POST.get("metodo") or "PROPORCIONAL",
                    activa=True,
                )
                messages.success(request, "Configuración CIF creada.")
            return redirect("contabilidad:cif_configuracion")

        if accion == "guardar" and config:
            try:
                config.driver = request.POST.get("driver") or config.driver
                config.metodo = request.POST.get("metodo") or config.metodo
                config.activa = request.POST.get("activa") == "on"
                config.notas = request.POST.get("notas", "").strip()

                pivot_id = request.POST.get("centro_pivot", "").strip()
                if pivot_id:
                    config.centro_pivot = CentroCosto.objects.get(id=int(pivot_id), empresa=empresa)
                else:
                    config.centro_pivot = None

                base_str = request.POST.get("base_pivot", "").strip()
                config.base_pivot = Decimal(base_str) if base_str else None

                config.save()

                centros_ids = request.POST.getlist("cc_id")
                creados = 0
                actualizados = 0
                for cc_id in centros_ids:
                    cc = CentroCosto.objects.filter(id=int(cc_id), empresa=empresa).first()
                    if not cc:
                        continue
                    cdc, created = CentroCostoCIF.objects.get_or_create(
                        configuracion=config,
                        centro_costo=cc,
                    )
                    cdc.area_cm2 = _parse_decimal(request.POST.get(f"area_{cc_id}"))
                    cdc.horas_maquina_mes = _parse_decimal(request.POST.get(f"horas_maquina_{cc_id}"))
                    cdc.horas_hombre_mes = _parse_decimal(request.POST.get(f"horas_hombre_{cc_id}"))
                    cdc.unidades_mes = _parse_decimal(request.POST.get(f"unidades_{cc_id}"))
                    cdc.costo_directo_mes = _parse_decimal(request.POST.get(f"costo_directo_{cc_id}"))
                    cdc.coeficiente_manual = _parse_decimal(request.POST.get(f"coef_manual_{cc_id}"))
                    cdc.save()
                    if created:
                        creados += 1
                    else:
                        actualizados += 1

                messages.success(
                    request,
                    f"Configuración guardada. Centros: {creados} creados, {actualizados} actualizados.",
                )
            except Exception as e:
                messages.error(request, f"Error al guardar: {e}")
            return redirect("contabilidad:cif_configuracion")

        if accion == "recalcular" and config:
            for cdc in config.centros.all():
                cdc.save()
            messages.success(request, "Coeficientes recalculados.")
            return redirect("contabilidad:cif_configuracion")

        if accion == "reset" and config:
            config.delete()
            messages.success(request, "Configuración CIF eliminada.")
            return redirect("contabilidad:cif_configuracion")

    centros_config = {}
    if config:
        for cdc in config.centros.select_related("centro_costo").all():
            centros_config[cdc.centro_costo_id] = cdc

    filas = []
    for cc in centros:
        cdc = centros_config.get(cc.id)
        filas.append({
            "centro": cc,
            "cdc": cdc,
            "area": cdc.area_cm2 if cdc else None,
            "horas_maquina": cdc.horas_maquina_mes if cdc else None,
            "horas_hombre": cdc.horas_hombre_mes if cdc else None,
            "unidades": cdc.unidades_mes if cdc else None,
            "costo_directo": cdc.costo_directo_mes if cdc else None,
            "coef_manual": cdc.coeficiente_manual if cdc else None,
            "coef_calculado": cdc.coeficiente_calculado if cdc else None,
        })

    context = {
        "empresa": empresa,
        "config": config,
        "filas": filas,
        "centros": centros,
        "drivers": DRIVER_CIF_CHOICES,
        "metodos": METODO_CIF_CHOICES,
    }
    return render(request, "contabilidad/cif_configuracion.html", context)


def _parse_decimal(valor):
    """Convierte un string a Decimal, tolerante a comas y vacíos."""
    if valor is None:
        return None
    valor = str(valor).strip().replace(",", ".")
    if not valor:
        return None
    try:
        return Decimal(valor)
    except (InvalidOperation, ValueError):
        return None


@solo_rrhh
def cif_centro_detalle(request, centro_costo_id):
    """Auditoría de un centro de costo específico dentro del reparto de CIF."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    centro = get_object_or_404(CentroCosto, pk=centro_costo_id, empresa=empresa)
    config = ConfiguracionCIF.objects.filter(empresa=empresa).first()

    if not config:
        messages.error(request, "No hay configuración CIF.")
        return redirect("contabilidad:cif_reporte")

    try:
        cdc = CentroCostoCIF.objects.select_related(
            "configuracion", "configuracion__centro_pivot"
        ).get(configuracion=config, centro_costo=centro)
    except CentroCostoCIF.DoesNotExist:
        messages.error(request, f"El centro {centro.codigo} no está en la configuración CIF.")
        return redirect("contabilidad:cif_reporte")

    valores_driver = {
        "AREA": cdc.area_cm2,
        "HORAS_MAQUINA": cdc.horas_maquina_mes,
        "HORAS_HOMBRE": cdc.horas_hombre_mes,
        "UNIDADES": cdc.unidades_mes,
        "COSTO_DIRECTO": cdc.costo_directo_mes,
    }

    context = {
        "empresa": empresa,
        "centro": centro,
        "config": config,
        "cdc": cdc,
        "valores_driver": valores_driver,
        "driver_label": DRIVER_LABELS.get(config.driver, config.driver),
    }
    return render(request, "contabilidad/cif_centro_detalle.html", context)


# =====================================================================
#  FASE 3: LIBROS SENIAT
# =====================================================================

def _libro_default_params(request):
    """Extrae los parámetros comunes (año, mes) de la request."""
    anio_str = request.GET.get("anio", "").strip() or str(date.today().year)
    mes_str = request.GET.get("mes", "").strip() or str(date.today().month)
    try:
        anio = int(anio_str)
        mes = int(mes_str)
        if not (1 <= mes <= 12):
            mes = date.today().month
    except (ValueError, TypeError):
        anio = date.today().year
        mes = date.today().month
    return anio, mes


@solo_rrhh
def libro_compras(request):
    """Reporte del Libro de Compras del período."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    anio, mes = _libro_default_params(request)
    libro = generar_libro_compras(empresa, anio, mes)

    context = {
        "empresa": empresa,
        "libro": libro,
        "anio": anio,
        "mes": mes,
        "meses": [
            (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
            (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
            (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
        ],
    }
    return render(request, "contabilidad/libro_compras.html", context)


@solo_rrhh
def libro_ventas(request):
    """Reporte del Libro de Ventas del período."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    anio, mes = _libro_default_params(request)
    libro = generar_libro_ventas(empresa, anio, mes)

    context = {
        "empresa": empresa,
        "libro": libro,
        "anio": anio,
        "mes": mes,
        "meses": [
            (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
            (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
            (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
        ],
    }
    return render(request, "contabilidad/libro_ventas.html", context)


@solo_rrhh
def libro_compras_export(request):
    """Exporta el Libro de Compras a Excel."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    anio, mes = _libro_default_params(request)
    libro = generar_libro_compras(empresa, anio, mes)

    wb = Workbook()
    ws = wb.active
    ws.title = "Libro de Compras"

    ws.merge_cells("A1:N1")
    ws["A1"] = f"Libro de Compras — {empresa.razon_social}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A2:N2")
    ws["A2"] = f"Período: {mes:02d}/{anio}  |  Total facturas: {libro['total_facturas']}"
    ws["A2"].font = Font(italic=True, size=10)
    ws["A2"].alignment = Alignment(horizontal="center")

    headers = [
        "Nº Op.", "Fecha", "Nº Factura", "Nº Control",
        "RIF Proveedor", "Razón Social",
        "Base Imponible", "Alícuota", "IVA", "Exento",
        "Total", "IVA Retenido", "Nº Comprobante Ret.", "Estado",
    ]
    header_row = 4
    for col, h in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    fila = header_row + 1
    for f in libro["filas"]:
        ws.cell(row=fila, column=1, value=f["numero_operacion"])
        ws.cell(row=fila, column=2, value=f["fecha_formateada"])
        ws.cell(row=fila, column=3, value=f["numero_factura"])
        ws.cell(row=fila, column=4, value=f["numero_control"])
        ws.cell(row=fila, column=5, value=f["rif_contraparte"])
        ws.cell(row=fila, column=6, value=f["razon_social_contraparte"])
        ws.cell(row=fila, column=7, value=float(f["base_imponible"]))
        ws.cell(row=fila, column=8, value=f"{f['alicuota_iva']:.2f}%")
        ws.cell(row=fila, column=9, value=float(f["monto_iva"]))
        ws.cell(row=fila, column=10, value=float(f["monto_exento"]))
        ws.cell(row=fila, column=11, value=float(f["monto_total"]))
        ws.cell(row=fila, column=12, value=float(f["iva_retenido"]))
        ws.cell(row=fila, column=13, value=f["numero_comprobante_retencion"])
        ws.cell(row=fila, column=14, value=f["estado"])
        fila += 1

    # Totales
    t = libro["totales"]
    ws.cell(row=fila, column=1, value="TOTAL")
    ws.cell(row=fila, column=7, value=float(t["base_imponible"]))
    ws.cell(row=fila, column=9, value=float(t["monto_iva"]))
    ws.cell(row=fila, column=10, value=float(t["monto_exento"]))
    ws.cell(row=fila, column=11, value=float(t["monto_total"]))
    ws.cell(row=fila, column=12, value=float(t["iva_retenido"]))
    for col in range(1, 15):
        cell = ws.cell(row=fila, column=col)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")

    for row in ws.iter_rows(min_row=header_row + 1, max_row=fila, min_col=7, max_col=12):
        for cell in row:
            cell.number_format = '#,##0.00'

    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 30
    for col_letter in ["G", "H", "I", "J", "K", "L", "M", "N"]:
        ws.column_dimensions[col_letter].width = 14

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="libro_compras_{anio}_{mes:02d}.xlsx"'
    wb.save(response)
    return response


@solo_rrhh
def libro_ventas_export(request):
    """Exporta el Libro de Ventas a Excel."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    anio, mes = _libro_default_params(request)
    libro = generar_libro_ventas(empresa, anio, mes)

    wb = Workbook()
    ws = wb.active
    ws.title = "Libro de Ventas"

    ws.merge_cells("A1:N1")
    ws["A1"] = f"Libro de Ventas — {empresa.razon_social}"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A2:N2")
    ws["A2"] = f"Período: {mes:02d}/{anio}  |  Total facturas: {libro['total_facturas']}"
    ws["A2"].font = Font(italic=True, size=10)
    ws["A2"].alignment = Alignment(horizontal="center")

    headers = [
        "Nº Op.", "Fecha", "Nº Factura", "Nº Control",
        "RIF Cliente", "Razón Social",
        "Base Imponible", "Alícuota", "IVA", "Exento",
        "Total", "IVA Retenido", "Nº Comprobante Ret.", "Estado",
    ]
    header_row = 4
    for col, h in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    fila = header_row + 1
    for f in libro["filas"]:
        ws.cell(row=fila, column=1, value=f["numero_operacion"])
        ws.cell(row=fila, column=2, value=f["fecha_formateada"])
        ws.cell(row=fila, column=3, value=f["numero_factura"])
        ws.cell(row=fila, column=4, value=f["numero_control"])
        ws.cell(row=fila, column=5, value=f["rif_contraparte"])
        ws.cell(row=fila, column=6, value=f["razon_social_contraparte"])
        ws.cell(row=fila, column=7, value=float(f["base_imponible"]))
        ws.cell(row=fila, column=8, value=f"{f['alicuota_iva']:.2f}%")
        ws.cell(row=fila, column=9, value=float(f["monto_iva"]))
        ws.cell(row=fila, column=10, value=float(f["monto_exento"]))
        ws.cell(row=fila, column=11, value=float(f["monto_total"]))
        ws.cell(row=fila, column=12, value=float(f["iva_retenido"]))
        ws.cell(row=fila, column=13, value=f["numero_comprobante_retencion"])
        ws.cell(row=fila, column=14, value=f["estado"])
        fila += 1

    t = libro["totales"]
    ws.cell(row=fila, column=1, value="TOTAL")
    ws.cell(row=fila, column=7, value=float(t["base_imponible"]))
    ws.cell(row=fila, column=9, value=float(t["monto_iva"]))
    ws.cell(row=fila, column=10, value=float(t["monto_exento"]))
    ws.cell(row=fila, column=11, value=float(t["monto_total"]))
    ws.cell(row=fila, column=12, value=float(t["iva_retenido"]))
    for col in range(1, 15):
        cell = ws.cell(row=fila, column=col)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")

    for row in ws.iter_rows(min_row=header_row + 1, max_row=fila, min_col=7, max_col=12):
        for cell in row:
            cell.number_format = '#,##0.00'

    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 30
    for col_letter in ["G", "H", "I", "J", "K", "L", "M", "N"]:
        ws.column_dimensions[col_letter].width = 14

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="libro_ventas_{anio}_{mes:02d}.xlsx"'
    wb.save(response)
    return response


@solo_rrhh
def libro_compras_txt(request):
    """Descarga el Libro de Compras en formato TXT (SENIAT)."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    anio, mes = _libro_default_params(request)
    libro = generar_libro_compras(empresa, anio, mes)
    contenido = generar_txt_libro(libro)

    response = HttpResponse(contenido, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="libro_compras_{anio}_{mes:02d}.txt"'
    return response


@solo_rrhh
def libro_ventas_txt(request):
    """Descarga el Libro de Ventas en formato TXT (SENIAT)."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    anio, mes = _libro_default_params(request)
    libro = generar_libro_ventas(empresa, anio, mes)
    contenido = generar_txt_libro(libro)

    response = HttpResponse(contenido, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="libro_ventas_{anio}_{mes:02d}.txt"'
    return response


# =====================================================================
#  FACTURAS FISCALES (CRUD)
# =====================================================================

@solo_rrhh
def factura_fiscal_lista(request):
    """Listado de facturas fiscales con filtros."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    qs = FacturaFiscal.objects.filter(empresa=empresa).select_related("asiento")

    tipo = request.GET.get("tipo", "").strip()
    estado = request.GET.get("estado", "").strip()
    q = request.GET.get("q", "").strip()
    if tipo:
        qs = qs.filter(tipo=tipo)
    if estado:
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(
            Q(numero_factura__icontains=q) |
            Q(numero_control__icontains=q) |
            Q(rif_contraparte__icontains=q) |
            Q(razon_social_contraparte__icontains=q)
        )

    qs = qs.order_by("-fecha_emision", "-numero_factura")

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    kpis = {
        "total": qs.count(),
        "compras": qs.filter(tipo="COMPRA").count(),
        "ventas": qs.filter(tipo="VENTA").count(),
        "borradores": qs.filter(estado="borrador").count(),
    }

    context = {
        "empresa": empresa,
        "page_obj": page_obj,
        "kpis": kpis,
        "filtros": {"tipo": tipo, "estado": estado, "q": q},
        "tipos": FacturaFiscal.TIPO_CHOICES,
        "estados": FacturaFiscal.ESTADO_CHOICES,
    }
    return render(request, "contabilidad/factura_fiscal_lista.html", context)


@solo_rrhh
def factura_fiscal_nueva(request):
    """Formulario para crear una factura fiscal."""
    empresa = _empresa_activa(request)
    if not empresa:
        messages.error(request, "No tienes empresas asignadas.")
        return redirect("rrhh:dashboard")

    config_iva = ConfiguracionIVA.objects.filter(empresa=empresa, activa=True).first()

    if request.method == "POST":
        tipo = request.POST.get("tipo", "").strip()
        numero_factura = request.POST.get("numero_factura", "").strip()
        numero_control = request.POST.get("numero_control", "").strip()
        fecha_emision = request.POST.get("fecha_emision", "").strip()
        rif_contraparte = request.POST.get("rif_contraparte", "").strip()
        razon_social_contraparte = request.POST.get("razon_social_contraparte", "").strip()
        base_imponible = _parse_decimal(request.POST.get("base_imponible"))
        alicuota_iva = _parse_decimal(request.POST.get("alicuota_iva")) or Decimal("16.00")
        monto_exento = _parse_decimal(request.POST.get("monto_exento")) or Decimal("0")
        iva_retenido = _parse_decimal(request.POST.get("iva_retenido")) or Decimal("0")

        errores = []
        if not tipo:
            errores.append("El tipo es obligatorio.")
        if not numero_factura:
            errores.append("El número de factura es obligatorio.")
        if not numero_control:
            errores.append("El número de control es obligatorio.")
        if not fecha_emision:
            errores.append("La fecha de emisión es obligatoria.")
        if not rif_contraparte:
            errores.append("El RIF de la contraparte es obligatorio.")
        if not razon_social_contraparte:
            errores.append("La razón social de la contraparte es obligatoria.")
        if not base_imponible or base_imponible <= 0:
            errores.append("La base imponible debe ser mayor a cero.")

        if errores:
            for e in errores:
                messages.error(request, e)
        else:
            try:
                with transaction.atomic():
                    factura = FacturaFiscal.objects.create(
                        empresa=empresa,
                        tipo=tipo,
                        numero_factura=numero_factura,
                        numero_control=numero_control,
                        fecha_emision=fecha_emision,
                        rif_contraparte=rif_contraparte,
                        razon_social_contraparte=razon_social_contraparte,
                        base_imponible=base_imponible,
                        alicuota_iva=alicuota_iva,
                        monto_exento=monto_exento,
                        iva_retenido=iva_retenido,
                        estado="borrador",
                        creado_por=request.user,
                        tipo_transaccion=request.POST.get("tipo_transaccion", "NACIONAL"),
                    )
                messages.success(request, f"Factura {factura.numero_factura} creada como borrador.")
                return redirect("contabilidad:factura_fiscal_detalle", factura_id=factura.id)
            except Exception as e:
                messages.error(request, f"Error al crear factura: {e}")

    context = {
        "empresa": empresa,
        "config_iva": config_iva,
        "tipos": FacturaFiscal.TIPO_CHOICES,
        "alicuotas_sugeridas": [
            (config_iva.alicuota_general if config_iva else Decimal("16.00"), "General"),
            (config_iva.alicuota_reducida if config_iva else Decimal("8.00"), "Reducida"),
            (Decimal("0"), "Exento"),
        ],
    }
    return render(request, "contabilidad/factura_fiscal_nueva.html", context)


@solo_rrhh
def factura_fiscal_detalle(request, factura_id):
    """Detalle de una factura fiscal."""
    empresa = _empresa_activa(request)
    factura = get_object_or_404(FacturaFiscal, pk=factura_id, empresa=empresa)
    errores_validacion = validar_factura_para_libro(factura)

    context = {
        "empresa": empresa,
        "factura": factura,
        "errores_validacion": errores_validacion,
        "lineas": factura.lineas.all(),
    }
    return render(request, "contabilidad/factura_fiscal_detalle.html", context)


@solo_rrhh
@require_POST
def factura_fiscal_confirmar(request, factura_id):
    """Confirma una factura fiscal (la pasa de borrador a confirmada)."""
    empresa = _empresa_activa(request)
    factura = get_object_or_404(FacturaFiscal, pk=factura_id, empresa=empresa)

    if factura.estado != "borrador":
        messages.warning(request, "Solo se pueden confirmar facturas en borrador.")
        return redirect("contabilidad:factura_fiscal_detalle", factura_id=factura.id)

    errores = validar_factura_para_libro(factura)
    if errores:
        messages.error(request, "No se puede confirmar: " + ", ".join(errores))
        return redirect("contabilidad:factura_fiscal_detalle", factura_id=factura.id)

    factura.estado = "confirmada"
    factura.save(update_fields=["estado", "actualizado_at"])
    messages.success(request, f"Factura {factura.numero_factura} confirmada.")
    return redirect("contabilidad:factura_fiscal_detalle", factura_id=factura.id)