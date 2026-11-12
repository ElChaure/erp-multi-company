"""
Modelo de auditoría. Registra todos los cambios en las tablas monitoreadas.
"""
from django.db import models
from django.contrib.auth.models import User


# ═══════════════════════════════════════════════════════════
#  TIPOS DE ACCIÓN
# ═══════════════════════════════════════════════════════════

class Accion(models.TextChoices):
    CREATE = "create", "Crear"
    UPDATE = "update", "Actualizar"
    DELETE = "delete", "Eliminar"
    LOGIN = "login", "Inicio de sesión"
    LOGOUT = "logout", "Cierre de sesión"
    LOGIN_FAILED = "login_failed", "Intento de login fallido"
    EXPORT = "export", "Exportar"
    VIEW = "view", "Ver"
    APPROVE = "approve", "Aprobar"
    REJECT = "reject", "Rechazar"
    CANCEL = "cancel", "Cancelar"


# ═══════════════════════════════════════════════════════════
#  AUDITORÍA
# ═══════════════════════════════════════════════════════════

class Auditoria(models.Model):
    """
    Registro de auditoría de cambios en el sistema.

    Cada fila representa una acción realizada por un usuario sobre un registro.
    Los valores_anteriores y valores_nuevos guardan snapshots JSON.
    """

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="auditorias",
        verbose_name="Usuario",
    )

    # Identificación del registro afectado
    empresa_id = models.BigIntegerField(
        null=True, blank=True,
        verbose_name="Empresa",
        db_index=True,
    )
    tabla = models.CharField(
        max_length=100,
        verbose_name="Tabla",
        db_index=True,
        help_text="Nombre completo: esquema.tabla o app.modelo",
    )
    registro_id = models.BigIntegerField(
        null=True, blank=True,
        verbose_name="ID del registro",
        db_index=True,
    )
    registro_repr = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Representación del registro",
        help_text="Texto legible del registro (ej: 'EMP-0001 - Juan Pérez')",
    )

    # Acción
    accion = models.CharField(
        max_length=20,
        choices=Accion.choices,
        verbose_name="Acción",
        db_index=True,
    )

    # Cambios
    valores_anteriores = models.JSONField(
        null=True, blank=True,
        verbose_name="Valores anteriores",
    )
    valores_nuevos = models.JSONField(
        null=True, blank=True,
        verbose_name="Valores nuevos",
    )
    campos_modificados = models.JSONField(
        null=True, blank=True,
        verbose_name="Campos modificados",
        help_text="Lista de nombres de campos que cambiaron",
    )

    # Contexto
    ip = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name="Dirección IP",
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name="User Agent",
    )
    url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="URL",
    )
    metodo_http = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Método HTTP",
    )

    # Metadata
    descripcion = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Descripción",
        help_text="Texto legible de la acción",
    )
    metadata = models.JSONField(
        null=True, blank=True,
        verbose_name="Metadata adicional",
    )

    fecha = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha",
        db_index=True,
    )

    class Meta:
        db_table = "rrhh_auditoria"
        verbose_name = "Auditoría"
        verbose_name_plural = "Auditorías"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["tabla", "registro_id"]),
            models.Index(fields=["usuario", "-fecha"]),
            models.Index(fields=["empresa_id", "-fecha"]),
            models.Index(fields=["accion", "-fecha"]),
            models.Index(fields=["-fecha"]),
        ]

    def __str__(self):
        return f"{self.fecha} - {self.usuario} - {self.accion} - {self.tabla}#{self.registro_id}"

    @property
    def accion_display(self):
        return self.get_accion_display()

    @property
    def resumen(self):
        """Resumen legible de la auditoría."""
        if self.descripcion:
            return self.descripcion
        return f"{self.get_accion_display()} en {self.tabla}"