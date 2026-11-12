from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from rrhh.models import Empresa, Sede
from contabilidad.models import PlanCuenta, CentroCosto, Asiento
from .constants import METODOS_DEPRECIACION

class ActivoFijo(models.Model):
    """Ficha del activo fijo (Vehículo, Maquinaria, Equipo, etc.)"""
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="activos_fijos")
    sede = models.ForeignKey(Sede, on_delete=models.SET_NULL, null=True, blank=True)
    centro_costo = models.ForeignKey(CentroCosto, on_delete=models.SET_NULL, null=True, blank=True,
                                     help_text="Para asignar la depreciación a Gerencia/Costos.")

    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    serial = models.CharField(max_length=100, blank=True)

    # Fechas y Valores
    fecha_adquisicion = models.DateField()
    fecha_inicio_depreciacion = models.DateField()
    costo_adquisicion = models.DecimalField(
        max_digits=18, decimal_places=2, validators=[MinValueValidator(0)],
        help_text="Monto total pagado por el activo (incluye IVA capitalizable si aplica)."
    )
    valor_residual = models.DecimalField(
        max_digits=18, decimal_places=2, default=0, validators=[MinValueValidator(0)],
        help_text="Valor estimado al final de la vida útil. La base depreciable = Costo - Residual."
    )
    vida_util_anios = models.PositiveIntegerField(
        default=10,
        help_text="Años de vida útil según SENIAT o política de la empresa."
    )

    # Método de Depreciación
    metodo_depreciacion = models.CharField(max_length=30, choices=METODOS_DEPRECIACION, default="LINEA_RECTA")
    tasa_anual = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Solo informativo. Se calcula: 100 / Vida Útil."
    )

    # Para método de Unidades de Producción (Fase 4)
    total_unidades_estimadas = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True,
        help_text="Solo para método de Unidades de Producción. Total de unidades a producir en la vida útil."
    )

    # Cuentas Contables
    cuenta_activo = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT, related_name="activos_fijos")
    cuenta_gasto_depreciacion = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT, related_name="gastos_depreciacion")
    cuenta_depreciacion_acumulada = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT, related_name="depreciacion_acumulada")

    activo = models.BooleanField(default=True)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "act_activo_fijo"
        verbose_name = "Activo Fijo"
        verbose_name_plural = "Activos Fijos"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    # ---- PROPIEDADES DE CÁLCULO (VISIBLES EN EL ADMIN Y EN EL LISTADO) ----

    @property
    def base_depreciable(self):
        """Costo de adquisición menos valor residual. Tolera valores None (formulario nuevo)."""
        costo = self.costo_adquisicion or 0
        residual = self.valor_residual or 0
        return costo - residual

    @property
    def depreciacion_mensual(self):
        """Monto que se deprecia cada mes (Línea Recta)."""
        if not self.vida_util_anios or self.vida_util_anios == 0:
            return 0
        return self.base_depreciable / (self.vida_util_anios * 12)

    @property
    def depreciacion_anual(self):
        """Monto que se deprecia cada año (Línea Recta)."""
        if not self.vida_util_anios or self.vida_util_anios == 0:
            return 0
        return self.base_depreciable / self.vida_util_anios

    @property
    def total_depreciado(self):
        """Suma de todas las depreciaciones ya registradas."""
        from django.db.models import Sum
        if not self.pk: # Si el activo es nuevo (no guardado), no hay depreciaciones
            return 0
        return self.depreciaciones.aggregate(total=Sum("monto"))["total"] or 0

    @property
    def valor_libro(self):
        """Valor en libros actual = Costo - Depreciación acumulada."""
        costo = self.costo_adquisicion or 0
        return costo - self.total_depreciado

    @property
    def esta_totalmente_depreciado(self):
        """True si ya se depreció toda la base depreciable."""
        if not self.pk:
            return False
        return self.total_depreciado >= self.base_depreciable


class DepreciacionActivo(models.Model):
    """Histórico de la depreciación mes a mes."""
    activo = models.ForeignKey(ActivoFijo, on_delete=models.CASCADE, related_name="depreciaciones")
    fecha = models.DateField()
    monto = models.DecimalField(max_digits=18, decimal_places=2)
    asiento = models.ForeignKey(Asiento, on_delete=models.SET_NULL, null=True, blank=True, 
                                help_text="Asiento contable generado por esta depreciación.")
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "act_depreciacion"
        unique_together = ("activo", "fecha")
        verbose_name = "Depreciación de Activo"
        verbose_name_plural = "Depreciaciones de Activos"