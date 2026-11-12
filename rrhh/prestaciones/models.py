"""
Modelos del módulo de prestaciones sociales (Art. 142 LOTTT).

Estructura:
    - ConfiguracionPrestaciones: por empresa
    - PrestacionSocial: cabecera por empleado
    - DepositoPrestacion: cada aporte trimestral (literal a+b)
    - CalculoRetroactivo: proyección del literal c
    - TasaInteresPrestaciones: tasas BCV por mes
"""
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from rrhh.models import Empleado, Empresa

from .constants import (
    MODOS_CALCULO,
    FRECUENCIAS_DEPOSITO,
    TIPOS_ACREDITACION,
    FUENTES_TASA,
    MONEDAS,
)


# ═══════════════════════════════════════════════════════════
#  CONFIGURACIÓN POR EMPRESA
# ═══════════════════════════════════════════════════════════

class ConfiguracionPrestaciones(models.Model):
    """
    Configuración de prestaciones sociales para una empresa.

    Define:
    - Modo de cálculo preferido
    - Frecuencia de depósito
    - Método de acreditación (fideicomiso, cuenta aparte, autoadministrado)
    - Cuenta matriz para débitos (si aplica)
    """
    empresa = models.OneToOneField(
        Empresa,
        on_delete=models.CASCADE,
        related_name="configuracion_prestaciones",
        verbose_name="Empresa",
    )

    modo_calculo = models.CharField(
        max_length=20,
        choices=MODOS_CALCULO,
        default="auto",
        verbose_name="Modo de cálculo",
        help_text="Art. 142.d: por defecto se paga el mayor entre garantía y retroactivo.",
    )

    frecuencia_deposito = models.CharField(
        max_length=20,
        choices=FRECUENCIAS_DEPOSITO,
        default="trimestral",
        verbose_name="Frecuencia de depósito",
    )

    tipo_acreditacion = models.CharField(
        max_length=20,
        choices=TIPOS_ACREDITACION,
        default="cuenta_aparte",
        verbose_name="Tipo de acreditación",
        help_text="Fideicomiso: banco externo. Cuenta aparte: cuenta interna. Autoadministrado: solo registro.",
    )

    # Datos del fideicomiso (si aplica)
    banco_fideicomiso = models.ForeignKey(
        "rrhh.Banco",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fideicomisos",
        verbose_name="Banco del fideicomiso",
    )
    numero_fideicomiso = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Número de fideicomiso",
    )

    # Cuenta matriz de la empresa (para débitos)
    cuenta_matriz_ves = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Cuenta matriz (VES)",
        help_text="Cuenta en bolívares de la empresa para débitos.",
    )
    cuenta_matriz_usd = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Cuenta matriz (USD)",
        help_text="Cuenta en dólares de la empresa (si aplica).",
    )

    # Manejo de moneda
    maneja_doble_moneda = models.BooleanField(
        default=False,
        verbose_name="¿Maneja doble moneda?",
        help_text="Si está activo, los salarios se registran en VES y USD.",
    )

    # Intereses
    genera_intereses = models.BooleanField(
        default=True,
        verbose_name="¿Genera intereses?",
        help_text="Según Art. 143 LOTTT.",
    )

    activa = models.BooleanField(default=True, verbose_name="Activa")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_prestaciones_config"
        verbose_name = "Configuración de prestaciones"
        verbose_name_plural = "Configuraciones de prestaciones"

    def __str__(self):
        return f"Config. prestaciones - {self.empresa.razon_social}"


# ═══════════════════════════════════════════════════════════
#  PRESTACIÓN SOCIAL (cabecera por empleado)
# ═══════════════════════════════════════════════════════════

class PrestacionSocial(models.Model):
    """
    Cabecera de prestaciones sociales por empleado.

    Acumula el historial de depósitos, intereses y saldos.
    El saldo final se determina al egreso comparando garantía vs retroactivo.
    """
    ESTATUS_CHOICES = [
        ("activa", "Activa (empleado en nómina)"),
        ("liquidada", "Liquidada (empleado egresado)"),
        ("suspendida", "Suspendida"),
    ]

    empleado = models.OneToOneField(
        Empleado,
        on_delete=models.CASCADE,
        related_name="prestacion_social",
        verbose_name="Empleado",
    )

    fecha_inicio = models.DateField(
        verbose_name="Fecha de inicio del cálculo",
        help_text="Normalmente la fecha de ingreso del empleado.",
    )
    fecha_ultimo_deposito = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha del último depósito",
    )

    # Saldos acumulados (en VES)
    saldo_garantia_ves = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Saldo garantía (VES)",
        help_text="Acumulado de literales a+b.",
    )
    saldo_intereses_ves = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Intereses acumulados (VES)",
    )
    saldo_total_ves = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Saldo total (VES)",
    )

    # Saldos en USD (si aplica doble moneda)
    saldo_garantia_usd = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Saldo garantía (USD)",
    )
    saldo_intereses_usd = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Intereses acumulados (USD)",
    )
    saldo_total_usd = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Saldo total (USD)",
    )

    # Último cálculo retroactivo
    ultimo_retroactivo = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Último retroactivo calculado (VES)",
    )
    ultimo_metodo_aplicado = models.CharField(
        max_length=20,
        choices=MODOS_CALCULO,
        blank=True,
        verbose_name="Último método aplicado",
    )

    estatus = models.CharField(
        max_length=20,
        choices=ESTATUS_CHOICES,
        default="activa",
        verbose_name="Estatus",
    )

    # Datos de liquidación (si está liquidada)
    fecha_liquidacion = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de liquidación",
    )
    monto_liquidacion_ves = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Monto liquidado (VES)",
    )
    monto_liquidacion_usd = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Monto liquidado (USD)",
    )

    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_prestacion_social"
        verbose_name = "Prestación social"
        verbose_name_plural = "Prestaciones sociales"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["estatus"]),
            models.Index(fields=["fecha_inicio"]),
        ]

    def __str__(self):
        return f"Prestaciones - {self.empleado.nombre_completo}"

    @property
    def anios_servicio(self):
        """Años completos de servicio."""
        from datetime import date
        fin = self.fecha_liquidacion or date.today()
        anios = fin.year - self.fecha_inicio.year
        if (fin.month, fin.day) < (self.fecha_inicio.month, self.fecha_inicio.day):
            anios -= 1
        return max(0, anios)


# ═══════════════════════════════════════════════════════════
#  DEPÓSITOS TRIMESTRALES (literal a + b)
# ═══════════════════════════════════════════════════════════

class DepositoPrestacion(models.Model):
    """
    Registra cada depósito trimestral (literal a) y los días adicionales
    (literal b) que correspondan.

    Se genera uno por trimestre natural (T1, T2, T3, T4).
    """
    ESTATUS_CHOICES = [
        ("calculado", "Calculado"),
        ("depositado", "Depositado"),
        ("acreditado", "Acreditado en cuenta"),
        ("anulado", "Anulado"),
    ]

    prestacion = models.ForeignKey(
        PrestacionSocial,
        on_delete=models.CASCADE,
        related_name="depositos",
        verbose_name="Prestación social",
    )

    # Trimestre
    anio = models.PositiveIntegerField(verbose_name="Año")
    trimestre = models.PositiveSmallIntegerField(
        verbose_name="Trimestre",
        help_text="1, 2, 3 o 4.",
    )
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio del trimestre")
    fecha_fin = models.DateField(verbose_name="Fecha de fin del trimestre")

    # Días
    dias_garantia = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("15"),
        verbose_name="Días de garantía (Art. 142.a)",
    )
    dias_adicionales = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Días adicionales (Art. 142.b)",
        help_text="2 días por año de servicio, acumulativos hasta 30.",
    )

    # Salario base del trimestre
    salario_integral_diario_ves = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
        verbose_name="Salario integral diario (VES)",
    )
    salario_integral_diario_usd = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
        verbose_name="Salario integral diario (USD)",
    )

    # Montos
    monto_ves = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Monto (VES)",
    )
    monto_usd = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Monto (USD)",
    )

    # Intereses generados en el trimestre
    intereses_ves = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Intereses del trimestre (VES)",
    )
    intereses_usd = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Intereses del trimestre (USD)",
    )

    # Acreditación
    fecha_deposito = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de depósito",
    )
    referencia_bancaria = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Referencia bancaria",
    )

    estatus = models.CharField(
        max_length=20,
        choices=ESTATUS_CHOICES,
        default="calculado",
        verbose_name="Estatus",
    )

    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_prestacion_deposito"
        verbose_name = "Depósito de prestación"
        verbose_name_plural = "Depósitos de prestaciones"
        ordering = ["-anio", "-trimestre"]
        unique_together = [("prestacion", "anio", "trimestre")]
        indexes = [
            models.Index(fields=["prestacion", "-anio", "-trimestre"]),
            models.Index(fields=["estatus"]),
        ]

    def __str__(self):
        return (
            f"{self.prestacion.empleado.numero_empleado} - "
            f"{self.anio}-T{self.trimestre}"
        )

    @property
    def trimestre_label(self):
        return f"{self.anio}-T{self.trimestre}"


# ═══════════════════════════════════════════════════════════
#  CÁLCULO RETROACTIVO (proyección del literal c)
# ═══════════════════════════════════════════════════════════

class CalculoRetroactivo(models.Model):
    """
    Snapshot del cálculo retroactivo (Art. 142.c) en un momento dado.

    Se guarda cada vez que se ejecuta para tener trazabilidad.
    Sirve para comparar contra la garantía acumulada y determinar
    el monto a pagar (Art. 142.d).
    """
    prestacion = models.ForeignKey(
        PrestacionSocial,
        on_delete=models.CASCADE,
        related_name="calculos_retroactivos",
        verbose_name="Prestación social",
    )

    fecha_calculo = models.DateTimeField(
        default=timezone.now,
        verbose_name="Fecha del cálculo",
    )

    # Datos del cálculo
    fecha_corte = models.DateField(
        verbose_name="Fecha de corte",
        help_text="Fecha hasta la cual se calcula el retroactivo.",
    )
    anios_servicio = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name="Años de servicio",
    )
    meses_fraccion = models.PositiveIntegerField(
        default=0,
        verbose_name="Meses de la fracción",
    )
    dias_retroactivo = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Días a pagar (30 × años)",
    )

    # Salario base
    ultimo_salario_integral_diario_ves = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
        verbose_name="Último salario integral diario (VES)",
    )
    ultimo_salario_integral_diario_usd = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=Decimal("0"),
        verbose_name="Último salario integral diario (USD)",
    )

    # Montos
    monto_retroactivo_ves = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Retroactivo (VES)",
    )
    monto_retroactivo_usd = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Retroactivo (USD)",
    )

    # Comparación
    saldo_garantia_ves = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Saldo garantía en ese momento (VES)",
    )
    saldo_garantia_usd = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Saldo garantía en ese momento (USD)",
    )
    metodo_seleccionado = models.CharField(
        max_length=20,
        choices=MODOS_CALCULO,
        verbose_name="Método seleccionado",
    )
    monto_final_ves = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Monto final a pagar (VES)",
    )
    monto_final_usd = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Monto final a pagar (USD)",
    )

    detalle = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Detalle del cálculo",
        help_text="Snapshot con los pasos intermedios para auditoría.",
    )

    class Meta:
        db_table = "rrhh_prestacion_calculo_retroactivo"
        verbose_name = "Cálculo retroactivo"
        verbose_name_plural = "Cálculos retroactivos"
        ordering = ["-fecha_calculo"]
        indexes = [
            models.Index(fields=["prestacion", "-fecha_calculo"]),
        ]

    def __str__(self):
        return (
            f"{self.prestacion.empleado.numero_empleado} - "
            f"{self.fecha_corte} ({self.metodo_seleccionado})"
        )


# ═══════════════════════════════════════════════════════════
#  TASA DE INTERÉS (BCV)
# ═══════════════════════════════════════════════════════════

class TasaInteresPrestaciones(models.Model):
    """
    Tasa de interés mensual aplicable a las prestaciones.
    Se carga manualmente desde el admin, mes a mes.
    Fuente: BCV.
    """
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="tasas_prestaciones",
        verbose_name="Empresa",
    )
    anio = models.PositiveIntegerField(verbose_name="Año")
    mes = models.PositiveSmallIntegerField(
        verbose_name="Mes",
        help_text="1 = enero, 12 = diciembre.",
    )
    tasa_anual_pct = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name="Tasa anual (%)",
    )
    moneda = models.CharField(
        max_length=3,
        choices=MONEDAS,
        default="VES",
        verbose_name="Moneda",
    )
    fuente = models.CharField(
        max_length=20,
        choices=FUENTES_TASA,
        default="manual",
        verbose_name="Fuente",
    )
    observaciones = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Observaciones",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_prestacion_tasa_interes"
        verbose_name = "Tasa de interés de prestaciones"
        verbose_name_plural = "Tasas de interés de prestaciones"
        ordering = ["-anio", "-mes"]
        unique_together = [("empresa", "anio", "mes", "moneda")]

    def __str__(self):
        return f"{self.empresa.razon_social} - {self.anio}-{self.mes:02d} ({self.tasa_anual_pct}%)"

    @property
    def tasa_mensual(self):
        """Tasa mensual equivalente (anual / 12)."""
        return self.tasa_anual_pct / Decimal("12")

    @property
    def tasa_diaria(self):
        """Tasa diaria equivalente (anual / 360)."""
        return self.tasa_anual_pct / Decimal("360")