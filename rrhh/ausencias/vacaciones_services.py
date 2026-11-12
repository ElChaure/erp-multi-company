"""
Servicios de negocio del módulo de vacaciones.

Orquesta:
    - Configuración por empresa
    - Generación de saldos anuales (individual y masiva)
    - Recálculo de saldos
    - Vencimiento
    - Vacaciones colectivas
    - Fraccionadas al egreso
"""
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from rrhh.models import (
    ConfiguracionVacaciones,
    Empleado,
    SaldoVacaciones,
    MovimientoSaldoVacaciones,
    TipoAusencia,
    VacacionColectiva,
    SolicitudAusencia,
)

from .vacaciones_engine import (
    calcular_saldo_anual,
    calcular_vencimiento,
    calcular_vacaciones_fraccionadas,
    dias_habiles_entre,
)


# ═══════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════

def obtener_configuracion(empresa):
    """Obtiene o crea la configuración de vacaciones de una empresa."""
    config, _ = ConfiguracionVacaciones.objects.get_or_create(
        empresa=empresa,
    )
    return config


# ═══════════════════════════════════════════════════════════
#  GENERACIÓN DE SALDOS
# ═══════════════════════════════════════════════════════════

@transaction.atomic
def generar_saldo_anual(empleado, anio, usuario=None):
    """
    Genera (o actualiza) el saldo de vacaciones de un empleado para un año.

    - Si no existe, lo crea.
    - Si existe, actualiza `dias_derecho` (por si cambió la antigüedad).

    Returns:
        SaldoVacaciones
    """
    config = obtener_configuracion(empleado.empresa)
    calculo = calcular_saldo_anual(empleado, anio, config)

    saldo, created = SaldoVacaciones.objects.get_or_create(
        empleado=empleado,
        anio=anio,
        defaults={
            "dias_derecho": calculo["dias_derecho"],
            "dias_tomados": Decimal("0"),
            "dias_pagados": Decimal("0"),
            "dias_ajuste": Decimal("0"),
            "fecha_limite_uso": calculo["fecha_vencimiento"],
        },
    )

    if not created:
        # Actualizar días de derecho y vencimiento
        saldo.dias_derecho = calculo["dias_derecho"]
        saldo.fecha_limite_uso = calculo["fecha_vencimiento"]
        saldo.save(update_fields=["dias_derecho", "fecha_limite_uso", "updated_at"])

    # Registrar movimiento si es nuevo
    if created:
        MovimientoSaldoVacaciones.objects.create(
            saldo=saldo,
            tipo="asignacion",
            dias=calculo["dias_derecho"],
            saldo_anterior=Decimal("0"),
            saldo_nuevo=calculo["dias_derecho"],
            motivo=f"Generación anual {anio} (antigüedad: {calculo['anios_antiguedad']} año/s)",
            usuario=usuario,
        )

    return saldo


@transaction.atomic
def generar_saldos_masivos(empresa, anio, usuario=None, incluir_egresados=False):
    """
    Genera los saldos de vacaciones para todos los empleados activos
    (o todos los que ingresaron antes del 31/12 del año) de una empresa.

    Returns:
        dict con:
            - creados: int
            - actualizados: int
            - omitidos: int
            - errores: list
    """
    empleados = Empleado.objects.filter(empresa=empresa)

    if not incluir_egresados:
        empleados = empleados.filter(estatus="activo")

    # Solo empleados que ingresaron antes o durante el año
    empleados = empleados.filter(fecha_ingreso__year__lte=anio)

    resultado = {
        "creados": 0,
        "actualizados": 0,
        "omitidos": 0,
        "errores": [],
    }

    for empleado in empleados:
        # Omitir si ya está egresado antes del cierre del año
        if empleado.fecha_egreso and empleado.fecha_egreso < date(anio, 1, 1):
            resultado["omitidos"] += 1
            continue

        try:
            existia = SaldoVacaciones.objects.filter(
                empleado=empleado, anio=anio,
            ).exists()

            generar_saldo_anual(empleado, anio, usuario)

            if existia:
                resultado["actualizados"] += 1
            else:
                resultado["creados"] += 1
        except Exception as e:
            resultado["errores"].append({
                "empleado": empleado.numero_empleado,
                "error": str(e),
            })

    return resultado


@transaction.atomic
def recalcular_saldo(saldo, usuario=None):
    """
    Recalcula un saldo existente (por si cambió la configuración o la antigüedad).
    No toca días tomados, pagados ni ajustes.
    """
    empleado = saldo.empleado
    anio = saldo.anio
    config = obtener_configuracion(empleado.empresa)
    calculo = calcular_saldo_anual(empleado, anio, config)

    saldo.dias_derecho = calculo["dias_derecho"]
    saldo.fecha_limite_uso = calculo["fecha_vencimiento"]
    saldo.save(update_fields=["dias_derecho", "fecha_limite_uso", "updated_at"])

    return saldo


# ═══════════════════════════════════════════════════════════
#  VENCIMIENTO
# ═══════════════════════════════════════════════════════════

@transaction.atomic
def procesar_vencimientos(empresa, usuario=None):
    """
    Marca como vencidos los días pendientes de saldos cuya fecha límite ya pasó.

    Los días vencidos se registran como un movimiento tipo "vencimiento"
    con valor negativo (o se ajusta un campo, según prefieras).

    En este MVP: creamos un movimiento de "vencimiento" con los días
    que quedaron pendientes, y marcamos el saldo con observaciones.

    Returns:
        dict con:
            - procesados: int
            - total_dias_vencidos: Decimal
    """
    hoy = date.today()

    saldos = SaldoVacaciones.objects.filter(
        empleado__empresa=empresa,
        fecha_limite_uso__lt=hoy,
        dias_tomados__lt=Decimal("0") + Decimal("999") + Decimal("999"),  # placeholder
    ).select_related("empleado")

    # Filtramos manualmente los que tienen días pendientes > 0
    saldos_a_vencer = [s for s in saldos if s.dias_pendientes > 0]

    total_dias = Decimal("0")
    procesados = 0

    for saldo in saldos_a_vencer:
        dias = saldo.dias_pendientes
        saldo_anterior = dias

        # Registrar movimiento de vencimiento
        MovimientoSaldoVacaciones.objects.create(
            saldo=saldo,
            tipo="vencimiento",
            dias=-dias,
            saldo_anterior=saldo_anterior,
            saldo_nuevo=Decimal("0"),
            motivo=f"Días vencidos (fecha límite: {saldo.fecha_limite_uso})",
            usuario=usuario,
        )

        # Ajuste negativo para reflejar el vencimiento
        saldo.dias_ajuste -= dias
        saldo.save(update_fields=["dias_ajuste", "updated_at"])

        total_dias += dias
        procesados += 1

    return {
        "procesados": procesados,
        "total_dias_vencidos": total_dias,
    }


# ═══════════════════════════════════════════════════════════
#  VACACIONES COLECTIVAS
# ═══════════════════════════════════════════════════════════

@transaction.atomic
def aplicar_vacacion_colectiva(vacacion, usuario=None):
    """
    Aplica una vacación colectiva:
        1. Calcula los días hábiles.
        2. Obtiene los empleados del alcance.
        3. Crea una SolicitudAusencia por cada empleado.
        4. Descuenta los días del saldo correspondiente.

    Returns:
        dict con:
            - total_empleados
            - solicitudes_creadas
            - errores (lista)
    """
    if vacacion.estatus != "borrador":
        raise ValueError(
            f"Solo se pueden aplicar vacaciones colectivas en estado borrador. "
            f"Esta está en '{vacacion.get_estatus_display()}'."
        )

    # Días hábiles
    dias_habiles = dias_habiles_entre(vacacion.fecha_inicio, vacacion.fecha_fin)
    vacacion.dias_habiles = dias_habiles

    # Tipo de ausencia
    tipo = vacacion.tipo_ausencia
    if not tipo:
        tipo = TipoAusencia.objects.filter(
            empresa=vacacion.empresa,
            categoria="vacaciones",
            activo=True,
        ).first()
        if not tipo:
            tipo = TipoAusencia.objects.filter(
                empresa__isnull=True,
                categoria="vacaciones",
                activo=True,
            ).first()
        if not tipo:
            raise ValueError(
                "No hay un tipo de ausencia de categoría 'vacaciones' "
                "configurado. Créalo antes de aplicar la vacación colectiva."
            )
        vacacion.tipo_ausencia = tipo

    # Empleados del alcance
    empleados = vacacion._empleados_queryset()

    solicitudes_creadas = 0
    errores = []

    for empleado in empleados:
        try:
            # Obtener saldo (año en que inicia)
            anio = vacacion.fecha_inicio.year
            saldo = SaldoVacaciones.objects.filter(
                empleado=empleado, anio=anio,
            ).first()

            if not saldo:
                # Crear saldo si no existe
                saldo = generar_saldo_anual(empleado, anio, usuario)

            # Verificar saldo suficiente
            if saldo.dias_pendientes < dias_habiles:
                errores.append({
                    "empleado": empleado.numero_empleado,
                    "error": f"Saldo insuficiente ({saldo.dias_pendientes} días).",
                })
                continue

            # Crear solicitud (ya aprobada, porque es colectiva)
            solicitud = SolicitudAusencia.objects.create(
                empleado=empleado,
                tipo=tipo,
                fecha_inicio=vacacion.fecha_inicio,
                fecha_fin=vacacion.fecha_fin,
                dias_solicitados=Decimal(str(dias_habiles)),
                dias_calendario=(vacacion.fecha_fin - vacacion.fecha_inicio).days + 1,
                fecha_reincorporacion=vacacion.fecha_fin + __import__("datetime").timedelta(days=1),
                motivo=f"Vacaciones colectivas: {vacacion.nombre}",
                estatus="aprobada",
                aprobador=None,  # Colectiva, no requiere aprobador individual
                fecha_resolucion=timezone.now(),
                comentario_aprobador=f"Aplicada por vacación colectiva '{vacacion.nombre}'",
            )

            # Descontar del saldo
            saldo_anterior = saldo.dias_pendientes
            saldo.dias_tomados += Decimal(str(dias_habiles))
            saldo.save(update_fields=["dias_tomados", "updated_at"])

            MovimientoSaldoVacaciones.objects.create(
                saldo=saldo,
                tipo="solicitud",
                dias=-Decimal(str(dias_habiles)),
                saldo_anterior=saldo_anterior,
                saldo_nuevo=saldo.dias_pendientes,
                solicitud=solicitud,
                motivo=f"Vacación colectiva: {vacacion.nombre}",
                usuario=usuario,
            )

            solicitudes_creadas += 1

        except Exception as e:
            errores.append({
                "empleado": empleado.numero_empleado,
                "error": str(e),
            })

    # Actualizar estatus
    vacacion.estatus = "aplicada"
    vacacion.aplicada_por = usuario
    vacacion.aplicada_at = timezone.now()
    vacacion.save()

    return {
        "total_empleados": empleados.count(),
        "solicitudes_creadas": solicitudes_creadas,
        "errores": errores,
    }


# ═══════════════════════════════════════════════════════════
#  FRACCIONADAS AL EGRESO
# ═══════════════════════════════════════════════════════════

def calcular_fraccionadas_al_egreso(empleado, fecha_egreso=None):
    """
    Calcula las vacaciones fraccionadas al egreso (para liquidación).

    Args:
        empleado: instancia de Empleado
        fecha_egreso: fecha de egreso (default: empleado.fecha_egreso o hoy)

    Returns:
        dict con el cálculo de la fracción.
    """
    if fecha_egreso is None:
        fecha_egreso = empleado.fecha_egreso or date.today()

    config = obtener_configuracion(empleado.empresa)
    return calcular_vacaciones_fraccionadas(empleado, fecha_egreso, config)