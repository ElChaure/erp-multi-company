"""
Signals para registrar automáticamente los cambios en los modelos clave.
"""
from django.db.models.signals import post_save, pre_save, post_delete, pre_delete
from django.dispatch import receiver

from .models import Accion
from . import services
from .middleware import get_current_user


# ═══════════════════════════════════════════════════════════
#  LISTA DE MODELOS AUDITADOS
# ═══════════════════════════════════════════════════════════

# Modelos que se auditan automáticamente
MODELOS_AUDITADOS = [
    # Core
    "core.Empresa",
    "core.Sucursal",
    "core.Departamento",
    "core.Puesto",
    "core.CentroCosto",
    # Empleados
    "empleados.Empleado",
    "empleados.Contrato",
    "empleados.Documento",
    # Nómina
    "nomina.PeriodoNomina",
    "nomina.NominaEmpleado",
    "nomina.ConceptoNomina",
    "nomina.IncidenciaNomina",
    # Ausencias
    "rrhh.TipoAusencia",
    "rrhh.SaldoVacaciones",
    "rrhh.SolicitudAusencia",
]


# ═══════════════════════════════════════════════════════════
#  CACHE DE SNAPSHOTS ANTES DE GUARDAR
# ═══════════════════════════════════════════════════════════

@receiver(pre_save)
def capturar_valores_anteriores(sender, instance, **kwargs):
    """
    Antes de guardar, captura el estado actual del registro (si existe).
    Lo guarda en un atributo para que post_save lo use.
    """
    # Solo procesar modelos auditados
    nombre = f"{sender._meta.app_label}.{sender._meta.object_name}"
    # Verificar si el modelo está en la lista o si su app está auditada
    if not _es_modelo_auditado(sender):
        return

    if instance.pk:
        try:
            anterior = sender.objects.get(pk=instance.pk)
            instance._auditoria_snapshot_anterior = services._snapshot(anterior)
        except sender.DoesNotExist:
            instance._auditoria_snapshot_anterior = None
    else:
        instance._auditoria_snapshot_anterior = None


@receiver(post_save)
def registrar_cambio(sender, instance, created, **kwargs):
    """Registra creación o actualización."""
    if not _es_modelo_auditado(sender):
        return

    if created:
        services.registrar(
            accion=Accion.CREATE,
            instance=instance,
            descripcion=f"Creación de {sender._meta.verbose_name}",
        )
    else:
        anterior = getattr(instance, "_auditoria_snapshot_anterior", None)
        if anterior:
            services.registrar(
                accion=Accion.UPDATE,
                instance=instance,
                valores_anteriores=anterior,
                descripcion=f"Actualización de {sender._meta.verbose_name}",
            )


@receiver(post_delete)
def registrar_eliminacion(sender, instance, **kwargs):
    """Registra eliminación."""
    if not _es_modelo_auditado(sender):
        return

    services.registrar(
        accion=Accion.DELETE,
        instance=instance,
        descripcion=f"Eliminación de {sender._meta.verbose_name}",
    )


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _es_modelo_auditado(model):
    """Verifica si un modelo está en la lista de auditados."""
    # Formato: app.Modelo o solo app
    for item in MODELOS_AUDITADOS:
        if "." in item:
            app, modelo = item.split(".")
            if model._meta.app_label == app and model._meta.object_name == modelo:
                return True
        else:
            if model._meta.app_label == item:
                return True
    return False