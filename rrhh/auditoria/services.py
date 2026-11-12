"""
Servicios para registrar auditorías.
"""
from decimal import Decimal
from datetime import date, datetime

from django.db import models
from django.utils import timezone

from .models import Auditoria, Accion
from .middleware import (
    get_current_user, get_current_ip,
    get_current_user_agent, get_current_url, get_current_method,
)


# ═══════════════════════════════════════════════════════════
#  SERIALIZACIÓN DE VALORES
# ═══════════════════════════════════════════════════════════

def _serializar_valor(valor):
    """Convierte un valor de Django a JSON serializable."""
    if valor is None:
        return None
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, models.Model):
        return {
            "id": valor.pk,
            "repr": str(valor),
        }
    if hasattr(valor, "name") and hasattr(valor, "url"):
        # FileField/ImageField
        try:
            return valor.url
        except Exception:
            return str(valor.name)
    return valor


def _snapshot(instance):
    """
    Crea un snapshot JSON de una instancia del modelo.

    Excluye campos internos y convierte valores a JSON serializable.
    """
    if instance is None:
        return None

    data = {}
    for field in instance._meta.fields:
        try:
            valor = getattr(instance, field.name)
            data[field.name] = _serializar_valor(valor)
        except Exception:
            data[field.name] = None
    return data


def _calcular_cambios(valores_ant, valores_new):
    """Devuelve la lista de campos que cambiaron."""
    if not valores_ant or not valores_new:
        return None

    cambios = []
    for key in set(valores_ant.keys()) | set(valores_new.keys()):
        val_ant = valores_ant.get(key)
        val_new = valores_new.get(key)
        if val_ant != val_new:
            cambios.append(key)
    return cambios


def _get_empresa_id(instance):
    """Intenta obtener el empresa_id de una instancia."""
    if instance is None:
        return None
    if hasattr(instance, "empresa_id"):
        return instance.empresa_id
    if hasattr(instance, "empresa") and instance.empresa:
        return instance.empresa.id
    if hasattr(instance, "empleado") and instance.empleado:
        if hasattr(instance.empleado, "empresa_id"):
            return instance.empleado.empresa_id
    return None


# ═══════════════════════════════════════════════════════════
#  REGISTRO DE AUDITORÍA
# ═══════════════════════════════════════════════════════════

def registrar(
    accion,
    instance=None,
    tabla=None,
    registro_id=None,
    valores_anteriores=None,
    valores_nuevos=None,
    descripcion="",
    metadata=None,
    usuario=None,
):
    """
    Registra una entrada de auditoría.

    Si se pasa `instance`, se infiere la tabla, id, empresa y snapshots.
    """
    if instance is not None:
        tabla = f"{instance._meta.app_label}.{instance._meta.model_name}"
        registro_id = instance.pk

        if accion == Accion.CREATE:
            valores_nuevos = valores_nuevos or _snapshot(instance)
        elif accion == Accion.UPDATE:
            valores_nuevos = valores_nuevos or _snapshot(instance)
        elif accion == Accion.DELETE:
            valores_anteriores = valores_anteriores or _snapshot(instance)

    campos_modificados = _calcular_cambios(valores_anteriores, valores_nuevos)

    # Obtener usuario (pasado o del contexto)
    if usuario is None:
        usuario = get_current_user()

    empresa_id = _get_empresa_id(instance) if instance else None

    # Representación del registro
    registro_repr = ""
    if instance is not None:
        try:
            registro_repr = str(instance)[:255]
        except Exception:
            registro_repr = ""

    # Descripción por defecto
    if not descripcion:
        accion_display = dict(Accion.choices).get(accion, accion)
        descripcion = f"{accion_display} en {tabla}" if tabla else accion_display

    return Auditoria.objects.create(
        usuario=usuario,
        empresa_id=empresa_id,
        tabla=tabla or "",
        registro_id=registro_id,
        registro_repr=registro_repr,
        accion=accion,
        valores_anteriores=valores_anteriores,
        valores_nuevos=valores_nuevos,
        campos_modificados=campos_modificados,
        ip=get_current_ip(),
        user_agent=get_current_user_agent(),
        url=get_current_url(),
        metodo_http=get_current_method(),
        descripcion=descripcion[:500],
        metadata=metadata,
    )


def registrar_creacion(instance, usuario=None, descripcion=""):
    """Atajo para registrar creación."""
    return registrar(
        accion=Accion.CREATE,
        instance=instance,
        usuario=usuario,
        descripcion=descripcion,
    )


def registrar_actualizacion(instance, valores_anteriores, usuario=None, descripcion=""):
    """Atajo para registrar actualización."""
    return registrar(
        accion=Accion.UPDATE,
        instance=instance,
        valores_anteriores=valores_anteriores,
        usuario=usuario,
        descripcion=descripcion,
    )


def registrar_eliminacion(instance, usuario=None, descripcion=""):
    """Atajo para registrar eliminación."""
    return registrar(
        accion=Accion.DELETE,
        instance=instance,
        usuario=usuario,
        descripcion=descripcion,
    )


def registrar_login(usuario, exitoso=True, descripcion=""):
    """Registra un intento de login."""
    return registrar(
        accion=Accion.LOGIN if exitoso else Accion.LOGIN_FAILED,
        usuario=usuario if exitoso else None,
        descripcion=descripcion or (
            f"Inicio de sesión exitoso: {usuario.username}" if exitoso
            else "Intento de login fallido"
        ),
        metadata={"username": usuario.username if usuario else None},
    )


def registrar_logout(usuario):
    """Registra un logout."""
    return registrar(
        accion=Accion.LOGOUT,
        usuario=usuario,
        descripcion=f"Cierre de sesión: {usuario.username}",
    )