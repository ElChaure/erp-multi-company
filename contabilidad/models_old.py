# contabilidad/models.py
from django.db import models
from decimal import Decimal
from rrhh.models import Empresa  # Asumimos que existe
from .constants import *


class EjercicioFiscal(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="ejercicios_fiscales")
    anio = models.PositiveIntegerField()
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    cerrado = models.BooleanField(default=False)

    class Meta:
        db_table = "cont_ejercicio"
        unique_together = ("empresa", "anio")
        verbose_name = "Ejercicio Fiscal"
        verbose_name_plural = "Ejercicios Fiscales"

    def __str__(self):
        return f"{self.empresa.razon_social} - {self.anio}"


class PeriodoContable(models.Model):
    ejercicio = models.ForeignKey(EjercicioFiscal, on_delete=models.CASCADE, related_name="periodos")
    mes = models.PositiveSmallIntegerField()  # 1-12
    anio = models.PositiveIntegerField()
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    estado = models.CharField(
        max_length=20,
        choices=[("abierto", "Abierto"), ("cerrado", "Cerrado")],
        default="abierto",
    )

    class Meta:
        db_table = "cont_periodo"
        unique_together = ("ejercicio", "mes")
        verbose_name = "Período Contable"
        verbose_name_plural = "Períodos Contables"

    def __str__(self):
        return f"{self.ejercicio.anio} - Mes {self.mes}"


class PlanCuenta(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="plan_cuentas")
    codigo = models.CharField(max_length=20)
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_CUENTA_CHOICES)
    naturaleza = models.CharField(max_length=1, choices=NATURALEZA_CHOICES)
    es_agrupadora = models.BooleanField(default=False, help_text="Si es True, no permite asientos directos.")
    activa = models.BooleanField(default=True)
    es_cuenta_de_costo = models.BooleanField(
        default=False,
        help_text="Marca si se usa para acumular costos de producción.",
    )

    class Meta:
        db_table = "cont_plan_cuenta"
        unique_together = ("empresa", "codigo")
        ordering = ["codigo"]
        verbose_name = "Plan de Cuenta"
        verbose_name_plural = "Plan de Cuentas"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class CentroCosto(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="centros_costo")
    codigo = models.CharField(max_length=20)
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=CC_TIPO_CHOICES)
    activo = models.BooleanField(default=True)
    capacidad_horas_mes = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Para tarifas predeterminadas.",
    )

    class Meta:
        db_table = "cont_centro_costo"
        unique_together = ("empresa", "codigo")
        verbose_name = "Centro de Costo"
        verbose_name_plural = "Centros de Costo"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Asiento(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    periodo = models.ForeignKey(PeriodoContable, on_delete=models.PROTECT)
    fecha = models.DateField()
    numero = models.CharField(max_length=20)
    concepto = models.TextField()
    origen_modulo = models.CharField(
        max_length=50,
        blank=True,
        help_text="Ej: 'costos', 'nomina', 'bancos'",
    )
    origen_id = models.CharField(max_length=50, blank=True, help_text="ID del documento origen")
    periodo_nomina = models.ForeignKey(
        "rrhh.PeriodoNomina",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asientos_contables",
        help_text="Si el asiento viene de nómina, apunta al período de origen.",
    )
    total_debito = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_credito = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    estado = models.CharField(
        max_length=20,
        choices=[("contabilizado", "Contabilizado"), ("anulado", "Anulado")],
        default="contabilizado",
    )

    class Meta:
        db_table = "cont_asiento"
        ordering = ["-fecha", "-numero"]
        verbose_name = "Asiento Contable"
        verbose_name_plural = "Asientos Contables"
        unique_together = ("empresa", "numero")

    def __str__(self):
        return f"Asiento {self.numero} - {self.fecha}"


class AsientoLinea(models.Model):
    asiento = models.ForeignKey(Asiento, on_delete=models.CASCADE, related_name="lineas")
    cuenta = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT)
    centro_costo = models.ForeignKey(CentroCosto, on_delete=models.SET_NULL, null=True, blank=True)
    debito = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    credito = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    descripcion = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "cont_asiento_linea"
        verbose_name = "Línea de Asiento"
        verbose_name_plural = "Líneas de Asiento"


class SaldoCuenta(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    periodo = models.ForeignKey(PeriodoContable, on_delete=models.CASCADE)
    cuenta = models.ForeignKey(PlanCuenta, on_delete=models.CASCADE)
    centro_costo = models.ForeignKey(CentroCosto, on_delete=models.SET_NULL, null=True, blank=True)
    saldo_inicial = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    debitos_periodo = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    creditos_periodo = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    saldo_final = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cont_saldo_cuenta"
        unique_together = ("empresa", "periodo", "cuenta", "centro_costo")
        verbose_name = "Saldo de Cuenta"
        verbose_name_plural = "Saldos de Cuentas"


class ComprobanteBorrador(models.Model):
    """
    Comprobante en staging. NO afecta saldos hasta ser contabilizado.
    """
    ESTADO_CHOICES = [
        ("borrador", "Borrador"),
        ("pendiente", "Pendiente de Verificación"),
        ("rechazado", "Rechazado"),
        ("contabilizado", "Contabilizado"),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="comprobantes_borrador")
    periodo = models.ForeignKey(PeriodoContable, on_delete=models.PROTECT)
    fecha = models.DateField()
    numero = models.CharField(max_length=20, help_text="Se genera automáticamente.")
    concepto = models.TextField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="borrador")

    total_debito = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    total_credito = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    cuadra = models.BooleanField(default=False)

    # Trazabilidad
    creado_por = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comprobantes_creados",
    )
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    # Cuando se contabiliza, apuntamos al asiento final
    asiento_generado = models.OneToOneField(
        Asiento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comprobante_origen",
    )

    class Meta:
        db_table = "cont_comprobante_borrador"
        ordering = ["-creado_at"]
        verbose_name = "Comprobante Borrador"
        verbose_name_plural = "Comprobantes Borradores"

    def __str__(self):
        return f"{self.numero} - {self.concepto[:50]}"

    def recalcular_totales(self):
        """Recalcula los totales y el cuadre desde las líneas."""
        totales = self.lineas.aggregate(
            total_debito=models.Sum("debito"),
            total_credito=models.Sum("credito"),
        )
        self.total_debito = totales["total_debito"] or Decimal("0")
        self.total_credito = totales["total_credito"] or Decimal("0")
        self.cuadra = abs(self.total_debito - self.total_credito) < Decimal("0.005")
        self.save(update_fields=["total_debito", "total_credito", "cuadra", "actualizado_at"])


class ComprobanteBorradorLinea(models.Model):
    """Línea de detalle del comprobante borrador."""
    comprobante = models.ForeignKey(ComprobanteBorrador, on_delete=models.CASCADE, related_name="lineas")
    cuenta = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT)
    centro_costo = models.ForeignKey(CentroCosto, on_delete=models.SET_NULL, null=True, blank=True)
    debito = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    credito = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    descripcion = models.CharField(max_length=200, blank=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "cont_comprobante_borrador_linea"
        ordering = ["orden", "id"]
        verbose_name = "Línea de Comprobante Borrador"
        verbose_name_plural = "Líneas de Comprobante Borrador"


class ConfiguracionContableNomina(models.Model):
    """
    Mapeo de conceptos de nómina a cuentas contables.
    Cada concepto (sueldo base, IVSS, etc.) se asocia a una cuenta contable.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="config_contable_nomina")
    concepto = models.ForeignKey(
        "rrhh.ConceptoNomina",
        on_delete=models.CASCADE,
        related_name="config_contable",
        verbose_name="Concepto de nómina",
    )
    cuenta = models.ForeignKey(
        PlanCuenta,
        on_delete=models.PROTECT,
        help_text="Cuenta contable asociada al concepto.",
    )
    # Opcional: para aportes patronales que necesitan 2 cuentas (gasto + pasivo)
    # Si no se especifica, se usa la misma cuenta para el débito y el crédito.
    cuenta_pasivo = models.ForeignKey(
        PlanCuenta,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="config_contable_pasivo",
        help_text="Solo para aportes patronales: cuenta de pasivo donde se acumula el aporte.",
    )

    class Meta:
        db_table = "cont_config_nomina"
        unique_together = ("empresa", "concepto")
        verbose_name = "Configuración Contable de Nómina"
        verbose_name_plural = "Configuraciones Contables de Nómina"

    def __str__(self):
        return f"{self.concepto.codigo} → {self.cuenta.codigo}"


class Presupuesto(models.Model):
    """
    Cabecera del presupuesto anual de una empresa.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="presupuestos")
    ejercicio = models.ForeignKey(EjercicioFiscal, on_delete=models.CASCADE, related_name="presupuestos")
    nombre = models.CharField(max_length=100, help_text="Ej: Presupuesto Operativo 2026")
    activo = models.BooleanField(default=True)
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cont_presupuesto"
        unique_together = ("empresa", "ejercicio", "nombre")
        verbose_name = "Presupuesto"
        verbose_name_plural = "Presupuestos"

    def __str__(self):
        return f"{self.nombre} - {self.ejercicio.anio}"


class PresupuestoLinea(models.Model):
    """
    Detalle mensual del presupuesto por cuenta y centro de costo.
    """
    presupuesto = models.ForeignKey(Presupuesto, on_delete=models.CASCADE, related_name="lineas")
    cuenta = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT)
    centro_costo = models.ForeignKey(CentroCosto, on_delete=models.SET_NULL, null=True, blank=True)

    monto_enero = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    monto_febrero = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    monto_marzo = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    monto_abril = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    monto_mayo = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    monto_junio = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    monto_julio = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    monto_agosto = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    monto_septiembre = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    monto_octubre = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    monto_noviembre = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    monto_diciembre = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    # Orden de meses (centralizado, para no repetirlo en cada método)
    MESES = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]

    class Meta:
        db_table = "cont_presupuesto_linea"
        unique_together = ("presupuesto", "cuenta", "centro_costo")
        verbose_name = "Línea de Presupuesto"
        verbose_name_plural = "Líneas de Presupuesto"

    def __str__(self):
        return f"{self.cuenta.codigo} - {self.presupuesto.nombre}"

    def total_anual(self):
        """
        Suma los 12 meses del presupuesto.

        Fix: convierte cada valor con Decimal(str(x or 0)) para tolerar
        None, int, str o Decimal sin provocar TypeError.
        """
        total = Decimal("0")
        for mes in self.MESES:
            valor = getattr(self, f"monto_{mes}", None)
            total += Decimal(str(valor or 0))
        return total