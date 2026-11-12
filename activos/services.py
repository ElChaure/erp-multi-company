# activos/services.py
from decimal import Decimal
from datetime import date
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Sum

from contabilidad.models import PeriodoContable, Asiento, PlanCuenta
from contabilidad.services import contabilizar_asiento
from .models import ActivoFijo, DepreciacionActivo
from .engine import calcular_depreciacion_mensual


def _obtener_periodo_contable(empresa, anio, mes):
    """Busca el período contable abierto para el mes/año."""
    periodo = PeriodoContable.objects.filter(
        ejercicio__empresa=empresa,
        anio=anio,
        mes=mes,
        estado="abierto",
    ).first()
    if not periodo:
        raise ValidationError(
            f"No hay período contable abierto para {anio}-{mes:02d}. "
            "Ábrelo en Contabilidad antes de depreciar."
        )
    return periodo


@transaction.atomic
def depreciar_mes(empresa, anio, mes, usuario=None):
    """
    Procesa la depreciación de todos los activos activos de la empresa
    para el mes indicado.
    
    Retorna:
        dict con:
        - asiento: el Asiento generado (o None si no hubo nada que depreciar)
        - activos_procesados: cantidad de activos depreciados
        - monto_total: suma de la depreciación
        - errores: lista de tuplas (activo, mensaje_error)
    """
    periodo = _obtener_periodo_contable(empresa, anio, mes)
    fecha_depreciacion = date(anio, mes, 1)  # Primer día del mes

    activos = ActivoFijo.objects.filter(
        empresa=empresa, activo=True,
        fecha_inicio_depreciacion__lte=fecha_depreciacion,
    ).select_related(
        "cuenta_activo", "cuenta_gasto_depreciacion",
        "cuenta_depreciacion_acumulada", "centro_costo"
    )

    lineas_asiento = []
    activos_procesados = 0
    monto_total = Decimal("0")
    errores = []

    for activo in activos:
        try:
            # 1. Verificar que no se haya depreciado ya este mes
            ya_depreciado = DepreciacionActivo.objects.filter(
                activo=activo,
                fecha__year=anio,
                fecha__month=mes,
            ).exists()
            if ya_depreciado:
                continue  # Saltar silenciosamente (ya está hecho)

            # 2. Calcular la depreciación del mes
            monto = calcular_depreciacion_mensual(activo)

            if monto <= 0:
                continue

            # 3. Verificar que el activo no esté totalmente depreciado
            total_depreciado = DepreciacionActivo.objects.filter(
                activo=activo
            ).aggregate(total=Sum("monto"))["total"] or Decimal("0")

            base_depreciable = activo.costo_adquisicion - activo.valor_residual
            if total_depreciado >= base_depreciable:
                continue  # Ya está totalmente depreciado

            # 4. Si el monto excede lo que falta, ajustarlo (último mes)
            restante = base_depreciable - total_depreciado
            if monto > restante:
                monto = restante

            # 5. Crear las líneas del asiento
            # Débito: Gasto por depreciación
            lineas_asiento.append({
                "cuenta_id": activo.cuenta_gasto_depreciacion_id,
                "centro_costo_id": activo.centro_costo_id,
                "debito": monto,
                "credito": Decimal("0"),
                "descripcion": f"Depreciación {activo.codigo} - {activo.nombre}",
            })
            # Crédito: Depreciación acumulada
            lineas_asiento.append({
                "cuenta_id": activo.cuenta_depreciacion_acumulada_id,
                "centro_costo_id": activo.centro_costo_id,
                "debito": Decimal("0"),
                "credito": monto,
                "descripcion": f"Dep. acumulada {activo.codigo} - {activo.nombre}",
            })

            activos_procesados += 1
            monto_total += monto

        except Exception as e:
            errores.append((activo, str(e)))

    if not lineas_asiento:
        return {
            "asiento": None,
            "activos_procesados": 0,
            "monto_total": Decimal("0"),
            "errores": errores,
            "mensaje": "No hay activos pendientes de depreciar en este mes."
        }

    # 6. Contabilizar el asiento consolidado
    concepto = f"Depreciación de Activos Fijos - {anio}/{mes:02d}"
    asiento = contabilizar_asiento(
        empresa=empresa,
        periodo=periodo,
        fecha=fecha_depreciacion,
        concepto=concepto,
        lineas_data=lineas_asiento,
        usuario=usuario,
        origen_modulo="activos",
        origen_id=f"{anio}-{mes:02d}",
    )

    # 7. Registrar cada depreciación y vincularla al asiento
    activos_depreciados_ids = []
    for activo in activos:
        monto = calcular_depreciacion_mensual(activo)
        if monto <= 0:
            continue
        total_depreciado = DepreciacionActivo.objects.filter(
            activo=activo
        ).aggregate(total=Sum("monto"))["total"] or Decimal("0")
        restante = (activo.costo_adquisicion - activo.valor_residual) - total_depreciado
        if monto > restante:
            monto = restante
        if monto > 0:
            DepreciacionActivo.objects.create(
                activo=activo,
                fecha=fecha_depreciacion,
                monto=monto,
                asiento=asiento,
            )

    return {
        "asiento": asiento,
        "activos_procesados": activos_procesados,
        "monto_total": monto_total,
        "errores": errores,
        "mensaje": f"Depreciación generada: {activos_procesados} activos, "
                   f"total Bs. {monto_total:,.2f}. Asiento N° {asiento.numero}.",
    }