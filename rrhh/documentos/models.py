"""
Modelos para el registro y trazabilidad de documentos formales.
"""

from django.contrib.auth.models import User
from django.db import models


class DocumentoEmitido(models.Model):
    """
    Registro de cada documento formal emitido (constancia, ARC, etc.).

    Guarda el número de control único, los parámetros de emisión
    (para poder regenerar el PDF) y la trazabilidad de quién lo emitió.
    """
    TIPO_CHOICES = [
        ("constancia_trabajo", "Constancia de Trabajo"),
        ("arc", "Planilla ARC"),
    ]

    # Identificación
    tipo = models.CharField(
        max_length=30,
        choices=TIPO_CHOICES,
        verbose_name="Tipo de documento",
    )
    numero_control = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Número de control",
        help_text="Ej: CT-2026-0001, ARC-2026-0001",
    )
    anio = models.PositiveIntegerField(
        verbose_name="Año",
        help_text="Año del correlativo (para reiniciar la numeración cada año).",
    )

    # Relaciones
    empleado = models.ForeignKey(
        "rrhh.Empleado",
        on_delete=models.PROTECT,
        related_name="documentos_emitidos",
        verbose_name="Empleado",
    )
    empresa = models.ForeignKey(
        "rrhh.Empresa",
        on_delete=models.PROTECT,
        related_name="documentos_emitidos",
        verbose_name="Empresa",
    )

    # Emisión
    emitido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documentos_emitidos",
        verbose_name="Emitido por",
    )
    emitido_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de emisión",
    )

    # Parámetros (para regenerar el PDF)
    parametros = models.JSONField(
        default=dict,
        verbose_name="Parámetros de emisión",
        help_text="Datos necesarios para regenerar el PDF exactamente igual.",
    )

    # Metadata de uso
    descargas = models.PositiveIntegerField(
        default=0,
        verbose_name="Descargas",
    )
    ultima_descarga = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Última descarga",
    )

    class Meta:
        db_table = "rrhh_documento_emitido"
        verbose_name = "Documento emitido"
        verbose_name_plural = "Documentos emitidos"
        ordering = ["-emitido_at"]
        indexes = [
            models.Index(fields=["tipo", "anio"]),
            models.Index(fields=["empleado", "tipo"]),
            models.Index(fields=["empresa", "tipo", "anio"]),
        ]

    def __str__(self):
        return f"{self.numero_control} - {self.empleado.numero_empleado} ({self.get_tipo_display()})"