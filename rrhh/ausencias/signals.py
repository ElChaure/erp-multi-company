"""
Signals para automatizar el módulo de ausencias.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from ..models import Empleado, SolicitudAusencia, SaldoVacaciones
from . import services


# ═══════════════════════════════════════════════════════════
#  ASIGNAR SALDO AL CREAR EMPLEADO
# ═══════════════════════════════════════════════════════════

@receiver(post_save, sender=Empleado)
def asignar_saldo_al_crear_empleado(sender, instance, created, **kwargs):
    """
    Asigna el saldo de vacaciones del año actual al crear un empleado.

    Usa la lógica nueva (vacaciones_services.generar_saldo_anual), que
    respeta la configuración de vacaciones de la empresa (incluido
    contrato colectivo) y calcula el vencimiento configurable.
    """
    if not created:
        return

    # No generar saldo si no tiene fecha de ingreso
    if not instance.fecha_ingreso:
        return

    # No generar saldo si nace ya egresado (caso raro, ej: importación)
    if instance.fecha_egreso:
        return

    try:
        from .vacaciones_services import generar_saldo_anual
        anio = instance.fecha_ingreso.year
        generar_saldo_anual(instance, anio)
    except Exception as e:
        # Loggear pero no romper la creación del empleado
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"No se pudo asignar saldo de vacaciones a "
            f"{instance.numero_empleado} ({instance.nombre_completo}): {e}"
        )


# ═══════════════════════════════════════════════════════════
#  VALIDAR SOLICITUD AL GUARDAR (si es nueva)
# ═══════════════════════════════════════════════════════════

@receiver(pre_save, sender=SolicitudAusencia)
def validar_solicitud_antes_de_guardar(sender, instance, **kwargs):
    """
    Valida la solicitud antes de guardarla si es nueva o si pasa a pendiente.
    """
    if not instance.pk:
        if instance.estatus in ("pendiente", "aprobada"):
            try:
                services.validar_solicitud(
                    empleado=instance.empleado,
                    tipo=instance.tipo,
                    fecha_inicio=instance.fecha_inicio,
                    fecha_fin=instance.fecha_fin,
                    dias_solicitados=instance.dias_solicitados,
                )
            except Exception:
                raise


# ═══════════════════════════════════════════════════════════
#  DETECTAR CAMBIOS EN SOLICITUD
# ═══════════════════════════════════════════════════════════

@receiver(pre_save, sender=SolicitudAusencia)
def guardar_estatus_anterior(sender, instance, **kwargs):
    """Guarda el estatus anterior para detectar cambios."""
    if instance.pk:
        try:
            anterior = SolicitudAusencia.objects.get(pk=instance.pk)
            instance._estatus_anterior = anterior.estatus
        except SolicitudAusencia.DoesNotExist:
            instance._estatus_anterior = None
    else:
        instance._estatus_anterior = None