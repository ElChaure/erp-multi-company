"""
Servicios de negocio para el módulo de ausencias.

Contiene toda la lógica:
  - Cálculo de días hábiles y calendario
  - Cálculo de días de vacaciones según LOTTT
  - Asignación de saldos
  - Aprobación / rechazo de solicitudes
  - Generación de incidencias de nómina
  - Validaciones
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import (
    Empleado, TipoAusencia, SaldoVacaciones, SolicitudAusencia,
    MovimientoSaldoVacaciones, IncidenciaNomina, PeriodoNomina,
)


# ═══════════════════════════════════════════════════════════
#  CÁLCULO DE DÍAS
# ═══════════════════════════════════════════════════════════

DIAS_SEMANA = {
    0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
    4: "viernes", 5: "sábado", 6: "domingo",
}


def calcular_dias_habiles(fecha_inicio, fecha_fin):
    """
    Calcula los días hábiles (lunes a viernes) entre dos fechas inclusive.
    """
    if fecha_inicio > fecha_fin:
        return 0

    dias = 0
    fecha = fecha_inicio
    while fecha <= fecha_fin:
        if fecha.weekday() < 5:  # 0=lunes ... 4=viernes
            dias += 1
        fecha += timedelta(days=1)
    return dias


def calcular_dias_calendario(fecha_inicio, fecha_fin):
    """Días calendario entre dos fechas inclusive."""
    if fecha_inicio > fecha_fin:
        return 0
    return (fecha_fin - fecha_inicio).days + 1


def calcular_dias_vacaciones_lottt(anios_antiguedad, dias_base=15, dias_max=30):
    """
    Calcula los días de vacaciones según la LOTTT venezolana (Art. 190).

    Regla:
      - 15 días hábiles por el primer año.
      - +1 día por cada año adicional de servicio.
      - Tope: 30 días.
    """
    if anios_antiguedad < 1:
        return dias_base
    return min(dias_base + (anios_antiguedad - 1), dias_max)


def calcular_dias_bono_vacacional_lottt(anios_antiguedad, dias_base=15, dias_max=30):
    """Bono vacacional según LOTTT Art. 192."""
    if anios_antiguedad < 1:
        return dias_base
    return min(dias_base + (anios_antiguedad - 1), dias_max)


def calcular_anios_antiguedad(fecha_ingreso, fecha_referencia=None):
    """Años completos entre la fecha de ingreso y la fecha de referencia."""
    if fecha_referencia is None:
        fecha_referencia = date.today()

    anios = fecha_referencia.year - fecha_ingreso.year
    if (fecha_referencia.month, fecha_referencia.day) < (fecha_ingreso.month, fecha_ingreso.day):
        anios -= 1
    return max(anios, 0)


# ═══════════════════════════════════════════════════════════
#  SALDOS DE VACACIONES
# ═══════════════════════════════════════════════════════════

@transaction.atomic
def asignar_saldo_inicial(empleado, anio=None, usuario=None):
    """
    Asigna el saldo de vacaciones de un empleado para un año.

    Returns:
        SaldoVacaciones: la instancia creada o existente.
    """
    if anio is None:
        anio = date.today().year

    # Verificar si ya existe
    saldo_existente = SaldoVacaciones.objects.filter(
        empleado=empleado, anio=anio,
    ).first()
    if saldo_existente:
        return saldo_existente

    # Calcular días según antigüedad
    anios = calcular_anios_antiguedad(empleado.fecha_ingreso, date(anio, 12, 31))
    dias_derecho = calcular_dias_vacaciones_lottt(anios)

    # Si ingresó este año, prorratear
    if empleado.fecha_ingreso.year == anio:
        meses_trabajados = 12 - empleado.fecha_ingreso.month + 1
        dias_derecho = round(dias_derecho * meses_trabajados / 12, 2)

    fecha_limite = date(anio + 1, 12, 31)  # Vence al año siguiente

    saldo = SaldoVacaciones.objects.create(
        empleado=empleado,
        anio=anio,
        dias_derecho=Decimal(str(dias_derecho)),
        dias_tomados=Decimal("0"),
        dias_pagados=Decimal("0"),
        dias_ajuste=Decimal("0"),
        fecha_limite_uso=fecha_limite,
    )

    # Registrar movimiento
    MovimientoSaldoVacaciones.objects.create(
        saldo=saldo,
        tipo="asignacion",
        dias=Decimal(str(dias_derecho)),
        saldo_anterior=Decimal("0"),
        saldo_nuevo=Decimal(str(dias_derecho)),
        motivo=f"Asignación inicial {anio}",
        usuario=usuario,
    )

    return saldo


def obtener_saldo(empleado, anio=None):
    """Obtiene el saldo del empleado para un año (o lo crea si no existe)."""
    if anio is None:
        anio = date.today().year

    saldo = SaldoVacaciones.objects.filter(
        empleado=empleado, anio=anio,
    ).first()

    if not saldo:
        saldo = asignar_saldo_inicial(empleado, anio)

    return saldo


@transaction.atomic
def descontar_dias_saldo(saldo, dias, solicitud=None, usuario=None, motivo=""):
    """
    Descuenta días del saldo y registra el movimiento.
    """
    saldo_anterior = saldo.dias_pendientes
    saldo.dias_tomados += Decimal(str(dias))
    saldo.save(update_fields=["dias_tomados", "updated_at"])

    MovimientoSaldoVacaciones.objects.create(
        saldo=saldo,
        tipo="solicitud",
        dias=-Decimal(str(dias)),
        saldo_anterior=saldo_anterior,
        saldo_nuevo=saldo.dias_pendientes,
        solicitud=solicitud,
        motivo=motivo or f"Solicitud #{solicitud.id if solicitud else 'N/A'}",
        usuario=usuario,
    )


@transaction.atomic
def devolver_dias_saldo(saldo, dias, solicitud=None, usuario=None, motivo=""):
    """
    Devuelve días al saldo (al cancelar una solicitud aprobada).
    """
    saldo_anterior = saldo.dias_pendientes
    saldo.dias_tomados = max(Decimal("0"), saldo.dias_tomados - Decimal(str(dias)))
    saldo.save(update_fields=["dias_tomados", "updated_at"])

    MovimientoSaldoVacaciones.objects.create(
        saldo=saldo,
        tipo="ajuste",
        dias=Decimal(str(dias)),
        saldo_anterior=saldo_anterior,
        saldo_nuevo=saldo.dias_pendientes,
        solicitud=solicitud,
        motivo=motivo or "Devolución por cancelación",
        usuario=usuario,
    )


# ═══════════════════════════════════════════════════════════
#  VALIDACIONES
# ═══════════════════════════════════════════════════════════

def validar_solicitud(empleado, tipo, fecha_inicio, fecha_fin, dias_solicitados):
    """
    Valida una solicitud antes de crearla o aprobarla.

    Raises:
        ValidationError con el detalle del problema.
    """
    errores = []

    # 1. Fechas coherentes
    if fecha_inicio > fecha_fin:
        errores.append("La fecha de inicio no puede ser posterior a la fecha de fin.")

    # 2. Días solicitados > 0
    if dias_solicitados <= 0:
        errores.append("Los días solicitados deben ser mayores a 0.")

    # 3. Antelación mínima
    if tipo.dias_antelacion_minima > 0:
        dias_antelacion = (fecha_inicio - date.today()).days
        if dias_antelacion < tipo.dias_antelacion_minima:
            errores.append(
                f"Este tipo de ausencia requiere al menos "
                f"{tipo.dias_antelacion_minima} días de antelación. "
                f"Solo hay {dias_antelacion} días."
            )

    # 4. Días máximos por solicitud
    if tipo.dias_max_por_solicitud and dias_solicitados > tipo.dias_max_por_solicitud:
        errores.append(
            f"El máximo por solicitud es {tipo.dias_max_por_solicitud} días. "
            f"Se solicitaron {dias_solicitados}."
        )

    # 5. Saldo de vacaciones suficiente
    if tipo.afecta_saldo_vacaciones:
        saldo = obtener_saldo(empleado, fecha_inicio.year)
        if saldo.dias_pendientes < dias_solicitados:
            errores.append(
                f"Saldo insuficiente. Disponible: {saldo.dias_pendientes} días. "
                f"Solicitados: {dias_solicitados}."
            )

    # 6. Solapamiento con otras solicitudes aprobadas o pendientes
    solapamiento = SolicitudAusencia.objects.filter(
        empleado=empleado,
        estatus__in=["pendiente", "aprobada", "en_disfrute"],
    ).filter(
        fecha_inicio__lte=fecha_fin,
        fecha_fin__gte=fecha_inicio,
    ).exists()

    if solapamiento:
        errores.append("Ya existe una solicitud en esas fechas.")

    # 7. Comprobante obligatorio
    if tipo.requiere_comprobante:
        # Se valida después de subir el archivo
        pass

    if errores:
        raise ValidationError(errores)

    return True


# ═══════════════════════════════════════════════════════════
#  APROBAR / RECHAZAR SOLICITUD
# ═══════════════════════════════════════════════════════════

@transaction.atomic
def aprobar_solicitud(solicitud, aprobador, comentario=""):
    """
    Aprueba una solicitud de ausencia.

    Acciones:
      1. Cambia el estatus a "aprobada"
      2. Descuenta días del saldo (si aplica)
      3. Genera incidencia de nómina (si aplica)
    """
    if solicitud.estatus != "pendiente":
        raise ValidationError(
            f"Solo se pueden aprobar solicitudes pendientes. "
            f"Esta está en estado '{solicitud.get_estatus_display()}'."
        )

    # 1. Cambiar estatus
    solicitud.estatus = "aprobada"
    solicitud.aprobador = aprobador
    solicitud.fecha_resolucion = timezone.now()
    solicitud.comentario_aprobador = comentario
    solicitud.fecha_reincorporacion = solicitud.fecha_fin + timedelta(days=1)
    solicitud.dias_calendario = calcular_dias_calendario(
        solicitud.fecha_inicio, solicitud.fecha_fin,
    )

    # 2. Descontar del saldo si aplica
    if solicitud.tipo.afecta_saldo_vacaciones:
        saldo = obtener_saldo(solicitud.empleado, solicitud.fecha_inicio.year)
        descontar_dias_saldo(
            saldo=saldo,
            dias=solicitud.dias_solicitados,
            solicitud=solicitud,
            usuario=aprobador.usuario if hasattr(aprobador, "usuario") else None,
            motivo=f"Aprobación de {solicitud.tipo.nombre}",
        )

    # 3. Generar incidencia de nómina si aplica
    if solicitud.tipo.afecta_nomina:
        incidencia = generar_incidencia_nomina(solicitud)
        solicitud.incidencia_generada = incidencia

    solicitud.save()

    return solicitud


@transaction.atomic
def rechazar_solicitud(solicitud, aprobador, comentario=""):
    """Rechaza una solicitud."""
    if solicitud.estatus != "pendiente":
        raise ValidationError(
            f"Solo se pueden rechazar solicitudes pendientes."
        )

    solicitud.estatus = "rechazada"
    solicitud.aprobador = aprobador
    solicitud.fecha_resolucion = timezone.now()
    solicitud.comentario_aprobador = comentario
    solicitud.save()

    return solicitud


@transaction.atomic
def cancelar_solicitud(solicitud, usuario=None, motivo=""):
    """
    Cancela una solicitud. Si estaba aprobada y afectaba el saldo,
    se devuelven los días.
    """
    if not solicitud.puede_cancelar:
        raise ValidationError(
            f"No se puede cancelar una solicitud en estado "
            f"'{solicitud.get_estatus_display()}'."
        )

    estatus_anterior = solicitud.estatus

    # Si estaba aprobada y afectó el saldo, devolver días
    if estatus_anterior in ("aprobada", "en_disfrute"):
        if solicitud.tipo.afecta_saldo_vacaciones:
            saldo = obtener_saldo(solicitud.empleado, solicitud.fecha_inicio.year)
            devolver_dias_saldo(
                saldo=saldo,
                dias=solicitud.dias_solicitados,
                solicitud=solicitud,
                usuario=usuario,
                motivo=motivo or "Cancelación de solicitud",
            )

        # Eliminar la incidencia de nómina si existe
        if solicitud.incidencia_generada:
            solicitud.incidencia_generada.delete()
            solicitud.incidencia_generada = None

    solicitud.estatus = "cancelada"
    solicitud.comentario_aprobador = motivo or "Cancelada"
    solicitud.save()

    return solicitud


# ═══════════════════════════════════════════════════════════
#  INTEGRACIÓN CON NÓMINA
# ═══════════════════════════════════════════════════════════

def encontrar_periodo_para_fecha(fecha, empresa_id):
    """
    Encuentra el periodo de nómina que contiene una fecha dada.
    """
    return PeriodoNomina.objects.filter(
        empresa_id=empresa_id,
        fecha_inicio__lte=fecha,
        fecha_fin__gte=fecha,
        estatus__in=["abierto", "calculado"],
    ).first()


@transaction.atomic
def generar_incidencia_nomina(solicitud):
    """
    Genera una incidencia de nómina a partir de una solicitud aprobada.

    La incidencia se asocia al periodo que contiene la fecha de inicio.
    """
    periodo = encontrar_periodo_para_fecha(
        solicitud.fecha_inicio,
        solicitud.empleado.empresa_id,
    )

    if not periodo:
        # No hay periodo abierto, no se puede generar la incidencia
        return None

    # Mapear tipo de ausencia → tipo de incidencia
    tipo_incidencia_map = {
        "vacaciones": "vacacion",
        "enfermedad": "incapacidad",
        "maternidad": "incapacidad",
        "permiso": "permiso",
    }
    tipo_incidencia = tipo_incidencia_map.get(
        solicitud.tipo.categoria, "permiso",
    )

    incidencia = IncidenciaNomina.objects.create(
        empleado=solicitud.empleado,
        periodo=periodo,
        tipo=tipo_incidencia,
        fecha=solicitud.fecha_inicio,
        cantidad=solicitud.dias_solicitados,
        unidad="dias",
        motivo=f"{solicitud.tipo.nombre}: {solicitud.motivo[:100]}",
        estatus="aprobada",
        aprobado_por=solicitud.aprobador.usuario
            if solicitud.aprobador and hasattr(solicitud.aprobador, "usuario")
            else None,
        aprobado_at=timezone.now(),
    )

    return incidencia


# ═══════════════════════════════════════════════════════════
#  REPORTES BÁSICOS
# ═══════════════════════════════════════════════════════════

def saldos_por_empleado(empresa_id, anio=None, empleado_id=None):
    """Devuelve los saldos de vacaciones de los empleados de una empresa."""
    if anio is None:
        anio = date.today().year

    qs = SaldoVacaciones.objects.filter(
        empleado__empresa_id=empresa_id,
        anio=anio,
    ).select_related("empleado", "empleado__cargo", "empleado__departamento")

    if empleado_id:
        qs = qs.filter(empleado_id=empleado_id)

    resultado = []
    for saldo in qs.order_by("empleado__apellido_paterno", "empleado__nombre"):
        resultado.append({
            "empleado_id": saldo.empleado.id,
            "empleado_numero": saldo.empleado.numero_empleado,
            "empleado_nombre": saldo.empleado.nombre_completo,
            "empleado_cedula": saldo.empleado.cedula_completa,
            "departamento": saldo.empleado.departamento.nombre if saldo.empleado.departamento else "",
            "cargo": saldo.empleado.cargo.nombre if saldo.empleado.cargo else "",
            "anio": saldo.anio,
            "dias_derecho": saldo.dias_derecho,
            "dias_tomados": saldo.dias_tomados,
            "dias_pagados": saldo.dias_pagados,
            "dias_ajuste": saldo.dias_ajuste,
            "dias_pendientes": saldo.dias_pendientes,
        })

    return resultado


def solicitudes_por_rango(empresa_id, fecha_desde=None, fecha_hasta=None,
                            estatus=None, tipo_id=None, empleado_id=None):
    """Lista las solicitudes de ausencia en un rango de fechas."""
    qs = SolicitudAusencia.objects.filter(
        empleado__empresa_id=empresa_id,
    ).select_related("empleado", "tipo", "aprobador")

    if fecha_desde:
        qs = qs.filter(fecha_fin__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_inicio__lte=fecha_hasta)
    if estatus:
        if isinstance(estatus, str):
            estatus = [estatus]
        qs = qs.filter(estatus__in=estatus)
    if tipo_id:
        qs = qs.filter(tipo_id=tipo_id)
    if empleado_id:
        qs = qs.filter(empleado_id=empleado_id)

    resultado = []
    for sol in qs.order_by("-fecha_inicio"):
        resultado.append({
            "id": sol.id,
            "empleado_id": sol.empleado.id,
            "empleado_numero": sol.empleado.numero_empleado,
            "empleado_nombre": sol.empleado.nombre_completo,
            "empleado_cedula": sol.empleado.cedula_completa,
            "departamento": sol.empleado.departamento.nombre if sol.empleado.departamento else "",
            "tipo": sol.tipo.nombre,
            "categoria": sol.tipo.categoria,
            "fecha_inicio": sol.fecha_inicio,
            "fecha_fin": sol.fecha_fin,
            "dias_solicitados": sol.dias_solicitados,
            "dias_calendario": sol.dias_calendario,
            "estatus": sol.estatus,
            "estatus_display": sol.get_estatus_display(),
            "aprobador": sol.aprobador.nombre_completo if sol.aprobador else "",
            "fecha_solicitud": sol.fecha_solicitud,
            "motivo": sol.motivo,
        })

    return resultado