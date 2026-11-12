# costos/models.py
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from rrhh.models import Empresa, Empleado
from contabilidad.models import CentroCosto, PlanCuenta, PeriodoContable
from activos.models import ActivoFijo
from .constants import TIPO_RECURSO_CHOICES, UNIDAD_CHOICES, ESTADO_ORDEN_CHOICES


class Recurso(models.Model):
    """Cualquier cosa que cuesta dinero: máquina, empleado o insumo."""
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="recursos_costos")
    codigo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_RECURSO_CHOICES)
    unidad_medida = models.CharField(max_length=20, choices=UNIDAD_CHOICES, default="UNIDAD")
    activo = models.BooleanField(default=True)
    creado_at = models.DateTimeField(auto_now_add=True)

    # Vinculaciones opcionales (solo una se usa según el tipo)
    activo_fijo = models.ForeignKey(
        ActivoFijo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recursos_costos",
        help_text="Solo si es una máquina/equipo.",
    )
    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recursos_costos",
        help_text="Solo si es mano de obra.",
    )

    class Meta:
        db_table = "cos_recurso"
        unique_together = ("empresa", "codigo")
        verbose_name = "Recurso"
        verbose_name_plural = "Recursos"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class RecursoCosto(models.Model):
    """Costo real de un recurso en un período (para calcular costeo real)."""
    recurso = models.ForeignKey(Recurso, on_delete=models.CASCADE, related_name="costos_reales")
    periodo = models.ForeignKey(PeriodoContable, on_delete=models.PROTECT)
    costo_total_periodo = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        help_text="Costo total del recurso en el mes (salario, depreciación, compra, etc.)",
    )
    horas_trabajadas = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Horas reales trabajadas en el período (si aplica).",
    )
    cantidad_producida = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
        help_text="Cantidad de unidades producidas en el período (si aplica).",
    )
    costo_unitario = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        default=0,
        help_text="Costo por hora o por unidad (se calcula automáticamente).",
    )
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cos_recurso_costo"
        unique_together = ("recurso", "periodo")
        verbose_name = "Costo Real de Recurso"
        verbose_name_plural = "Costos Reales de Recursos"

    def __str__(self):
        return f"{self.recurso.nombre} - {self.periodo}"

    def save(self, *args, **kwargs):
        # Calcular costo unitario automáticamente
        if self.horas_trabajadas and self.horas_trabajadas > 0:
            self.costo_unitario = self.costo_total_periodo / self.horas_trabajadas
        elif self.cantidad_producida and self.cantidad_producida > 0:
            self.costo_unitario = self.costo_total_periodo / self.cantidad_producida
        else:
            self.costo_unitario = 0
        super().save(*args, **kwargs)


class Actividad(models.Model):
    """Proceso productivo que consume recursos (ej: Corte, Ensamble, Impresión)."""
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="actividades_costos")
    codigo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=200)
    centro_costo = models.ForeignKey(
        CentroCosto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actividades_costos",
        help_text="Centro de costo contable asociado.",
    )
    activo = models.BooleanField(default=True)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cos_actividad"
        unique_together = ("empresa", "codigo")
        verbose_name = "Actividad"
        verbose_name_plural = "Actividades"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class ActividadRecurso(models.Model):
    """Recursos que consume una actividad (para costear la actividad)."""
    actividad = models.ForeignKey(Actividad, on_delete=models.CASCADE, related_name="recursos")
    recurso = models.ForeignKey(Recurso, on_delete=models.PROTECT)
    cantidad_estimada = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=0,
        help_text="Cantidad estándar de este recurso para la actividad.",
    )

    class Meta:
        db_table = "cos_actividad_recurso"
        unique_together = ("actividad", "recurso")
        verbose_name = "Recurso de Actividad"
        verbose_name_plural = "Recursos de Actividad"

    def __str__(self):
        return f"{self.actividad.nombre} - {self.recurso.nombre}"


class OrdenProduccion(models.Model):
    """Documento que representa un lote de producción o servicio."""
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="ordenes_produccion")
    # NOTA: numero es único POR EMPRESA (via unique_together), no global.
    # Dos empresas pueden tener OP-001 sin conflicto.
    numero = models.CharField(max_length=30)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    cantidad_producida = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    unidad_producida = models.CharField(max_length=20, choices=UNIDAD_CHOICES, default="UNIDAD")
    estado = models.CharField(max_length=20, choices=ESTADO_ORDEN_CHOICES, default="BORRADOR")

    # Costos consolidados (se llenan al finalizar)
    costo_materia_prima = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    costo_mano_obra = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    costo_indirecto = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    costo_total = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    costo_unitario = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cos_orden_produccion"
        unique_together = ("empresa", "numero")
        verbose_name = "Orden de Producción"
        verbose_name_plural = "Órdenes de Producción"

    def __str__(self):
        return f"{self.numero} - {self.nombre}"


class OrdenReceta(models.Model):
    """Estructura (BOM) de una orden de producción: qué recursos consume."""
    orden = models.ForeignKey(OrdenProduccion, on_delete=models.CASCADE, related_name="receta")
    recurso = models.ForeignKey(Recurso, on_delete=models.PROTECT)
    cantidad_estimada = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    costo_unitario_estimado = models.DecimalField(max_digits=18, decimal_places=6, default=0)

    class Meta:
        db_table = "cos_orden_receta"
        verbose_name = "Receta de Orden"
        verbose_name_plural = "Recetas de Órdenes"

    def __str__(self):
        return f"{self.orden.numero} - {self.recurso.nombre}"


class OrdenConsumoReal(models.Model):
    """Registro real de cuánto se consumió de cada recurso en la orden."""
    orden = models.ForeignKey(OrdenProduccion, on_delete=models.CASCADE, related_name="consumos_reales")
    recurso = models.ForeignKey(Recurso, on_delete=models.PROTECT)
    cantidad_real = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    costo_unitario_real = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    fecha_consumo = models.DateField()
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cos_orden_consumo_real"
        verbose_name = "Consumo Real de Orden"
        verbose_name_plural = "Consumos Reales de Órdenes"

    def __str__(self):
        return f"{self.orden.numero} - {self.recurso.nombre}"

    @property
    def costo_total(self):
        return self.cantidad_real * self.costo_unitario_real