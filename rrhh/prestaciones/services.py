"""
Servicios de negocio del módulo de prestaciones.
"""
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from rrhh.models import Empleado

from .engine import (
    calcular_garantia_trimestre,
    calcular_garantia_acumulada,
    calcular_retroactivo,
    calcular_prestaciones,
    rango_trimestre,
)
from .models import (
    ConfiguracionPrestaciones,
    PrestacionSocial,
    DepositoPrestacion,
    CalculoRetroactivo,
)


# ═══════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════

def obtener_configuracion(empresa):
    """Obtiene o crea la configuración de prestaciones de una empresa."""
    config, _ = ConfiguracionPrestaciones.objects.get_or_create(
        empresa=empresa,
    )
    return config


# ═══════════════════════════════════════════════════════════
#  PRESTACIÓN SOCIAL
# ═══════════════════════════════════════════════════════════

def obtener_prestacion(empleado):
    """Obtiene o crea la prestación social de un empleado."""
    prestacion, created = PrestacionSocial.objects.get_or_create(
        empleado=empleado,
        defaults={
            "fecha_inicio": empleado.fecha_ingreso,
        },
    )
    return prestacion


# ═══════════════════════════════════════════════════════════
#  DEPÓSITOS
# ═══════════════════════════════════════════════════════════

@transaction.atomic
def generar_deposito_trimestre(empleado, anio, trimestre, parametros=None):
    """
    Genera el depósito de un trimestre específico.

    Si ya existe, lo actualiza. Si no, lo crea.
    """
    prestacion = obtener_prestacion(empleado)

    resultado = calcular_garantia_trimestre(
        empleado, anio, trimestre, parametros
    )
    if not resultado:
        return None

    deposito, created = DepositoPrestacion.objects.update_or_create(
        prestacion=prestacion,
        anio=anio,
        trimestre=trimestre,
        defaults={
            "fecha_inicio": resultado["fecha_inicio"],
            "fecha_fin": resultado["fecha_fin"],
            "dias_garantia": resultado["dias_garantia"],
            "dias_adicionales": resultado["dias_adicionales"],
            "salario_integral_diario_ves": resultado["salario_integral_diario"],
            "monto_ves": resultado["monto_ves"],
            "estatus": "calculado",
        },
    )

    return deposito


@transaction.atomic
def generar_depositos_anio(empleado, anio, parametros=None):
    """Genera los 4 depósitos trimestrales de un año."""
    depositos = []
    for trimestre in (1, 2, 3, 4):
        deposito = generar_deposito_trimestre(
            empleado, anio, trimestre, parametros
        )
        if deposito:
            depositos.append(deposito)
    return depositos


@transaction.atomic
def recalcular_prestacion(empleado, parametros=None):
    """
    Recalcula el saldo acumulado de la prestación social.
    """
    prestacion = obtener_prestacion(empleado)

    # Total garantía acumulada
    total = sum(
        dep.monto_ves for dep in prestacion.depositos.filter(
            estatus__in=["calculado", "depositado", "acreditado"]
        )
    )
    total_intereses = sum(
        dep.intereses_ves for dep in prestacion.depositos.filter(
            estatus__in=["calculado", "depositado", "acreditado"]
        )
    )

    prestacion.saldo_garantia_ves = total
    prestacion.saldo_intereses_ves = total_intereses
    prestacion.saldo_total_ves = total + total_intereses

    # Cálculo retroactivo actual
    retro = calcular_retroactivo(empleado, parametros=parametros)
    prestacion.ultimo_retroactivo = retro["monto_ves"]

    # Método seleccionado
    config = obtener_configuracion(empleado.empresa)
    if config.modo_calculo == "auto":
        if prestacion.saldo_total_ves >= retro["monto_ves"]:
            prestacion.ultimo_metodo_aplicado = "garantia"
        else:
            prestacion.ultimo_metodo_aplicado = "retroactivo"
    else:
        prestacion.ultimo_metodo_aplicado = config.modo_calculo

    prestacion.save()

    return prestacion


@transaction.atomic
def registrar_calculo_retroactivo(empleado, fecha_corte=None):
    """
    Ejecuta y guarda un snapshot del cálculo retroactivo para trazabilidad.
    """
    prestacion = obtener_prestacion(empleado)

    calculo = calcular_prestaciones(empleado, fecha_corte)
    garantia = calculo["garantia"]
    retro = calculo["retroactivo"]

    registro = CalculoRetroactivo.objects.create(
        prestacion=prestacion,
        fecha_corte=calculo["fecha_corte"],
        anios_servicio=retro["anios_servicio"],
        meses_fraccion=retro["meses_fraccion"],
        dias_retroactivo=retro["dias_retroactivo"],
        ultimo_salario_integral_diario_ves=retro["salario_integral_diario"],
        monto_retroactivo_ves=retro["monto_ves"],
        saldo_garantia_ves=garantia["total_ves"],
        metodo_seleccionado=calculo["metodo_seleccionado"],
        monto_final_ves=calculo["monto_final_ves"],
        detalle={
            "garantia": {
                "total_dias": float(garantia["total_dias"]),
                "total_ves": float(garantia["total_ves"]),
                "trimestres": len(garantia["trimestres"]),
            },
            "retroactivo": {
                "anios": float(retro["anios_servicio"]),
                "meses_fraccion": retro["meses_fraccion"],
                "fraccion_cuenta": retro["fraccion_cuenta_como_anio"],
                "dias": float(retro["dias_retroactivo"]),
                "monto": float(retro["monto_ves"]),
            },
        },
    )

    return registro