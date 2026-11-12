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
    mes = models.PositiveSmallIntegerField()
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
        max_digits=10, decimal_places=2, null=True, blank=True,
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
    origen_modulo = models.CharField(max_length=50, blank=True)
    origen_id = models.CharField(max_length=50, blank=True)
    periodo_nomina = models.ForeignKey(
        "rrhh.PeriodoNomina", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="asientos_contables",
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
    creado_por = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="comprobantes_creados")
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)
    asiento_generado = models.OneToOneField(Asiento, on_delete=models.SET_NULL, null=True, blank=True, related_name="comprobante_origen")

    class Meta:
        db_table = "cont_comprobante_borrador"
        ordering = ["-creado_at"]
        verbose_name = "Comprobante Borrador"
        verbose_name_plural = "Comprobantes Borradores"

    def __str__(self):
        return f"{self.numero} - {self.concepto[:50]}"

    def recalcular_totales(self):
        totales = self.lineas.aggregate(
            total_debito=models.Sum("debito"),
            total_credito=models.Sum("credito"),
        )
        self.total_debito = totales["total_debito"] or Decimal("0")
        self.total_credito = totales["total_credito"] or Decimal("0")
        self.cuadra = abs(self.total_debito - self.total_credito) < Decimal("0.005")
        self.save(update_fields=["total_debito", "total_credito", "cuadra", "actualizado_at"])


class ComprobanteBorradorLinea(models.Model):
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
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="config_contable_nomina")
    concepto = models.ForeignKey("rrhh.ConceptoNomina", on_delete=models.CASCADE, related_name="config_contable", verbose_name="Concepto de nómina")
    cuenta = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT, help_text="Cuenta contable asociada al concepto.")
    cuenta_pasivo = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT, null=True, blank=True, related_name="config_contable_pasivo", help_text="Solo para aportes patronales.")

    class Meta:
        db_table = "cont_config_nomina"
        unique_together = ("empresa", "concepto")
        verbose_name = "Configuración Contable de Nómina"
        verbose_name_plural = "Configuraciones Contables de Nómina"

    def __str__(self):
        return f"{self.concepto.codigo} → {self.cuenta.codigo}"


class Presupuesto(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="presupuestos")
    ejercicio = models.ForeignKey(EjercicioFiscal, on_delete=models.CASCADE, related_name="presupuestos")
    nombre = models.CharField(max_length=100)
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

    MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

    class Meta:
        db_table = "cont_presupuesto_linea"
        unique_together = ("presupuesto", "cuenta", "centro_costo")
        verbose_name = "Línea de Presupuesto"
        verbose_name_plural = "Líneas de Presupuesto"

    def __str__(self):
        return f"{self.cuenta.codigo} - {self.presupuesto.nombre}"

    def total_anual(self):
        total = Decimal("0")
        for mes in self.MESES:
            valor = getattr(self, f"monto_{mes}", None)
            total += Decimal(str(valor or 0))
        return total


class ConfiguracionContableCostos(models.Model):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name="config_contable_costos", verbose_name="Empresa")
    cuenta_inventario_pt = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT, null=True, blank=True, related_name="config_costos_inventario")
    cuenta_costo_mp = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT, null=True, blank=True, related_name="config_costos_mp")
    cuenta_costo_mod = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT, null=True, blank=True, related_name="config_costos_mod")
    cuenta_costo_cif = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT, null=True, blank=True, related_name="config_costos_cif")
    cuenta_sueldos_por_pagar = models.ForeignKey(PlanCuenta, on_delete=models.PROTECT, null=True, blank=True, related_name="config_costos_sueldos_pagar")
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cont_config_costos"
        verbose_name = "Configuración Contable de Costos"
        verbose_name_plural = "Configuraciones Contables de Costos"

    def __str__(self):
        return f"Config. costos — {self.empresa.razon_social}"


class ConfiguracionCIF(models.Model):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name="config_cif", verbose_name="Empresa")
    driver = models.CharField(max_length=30, choices=DRIVER_CIF_CHOICES, default=DRIVER_AREA)
    centro_pivot = models.ForeignKey(CentroCosto, on_delete=models.PROTECT, null=True, blank=True, related_name="config_cif_pivot")
    base_pivot = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    metodo = models.CharField(max_length=20, choices=METODO_CIF_CHOICES, default=METODO_PROPORCIONAL)
    activa = models.BooleanField(default=True)
    notas = models.TextField(blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cont_config_cif"
        verbose_name = "Configuración de Reparto de CIF"
        verbose_name_plural = "Configuraciones de Reparto de CIF"

    def __str__(self):
        return f"Config. CIF — {self.empresa.razon_social} ({self.get_driver_display()})"


class CentroCostoCIF(models.Model):
    configuracion = models.ForeignKey(ConfiguracionCIF, on_delete=models.CASCADE, related_name="centros", verbose_name="Configuración CIF")
    centro_costo = models.ForeignKey(CentroCosto, on_delete=models.CASCADE, related_name="config_cif_detalle", verbose_name="Centro de Costo")
    area_cm2 = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    horas_maquina_mes = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    horas_hombre_mes = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unidades_mes = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    costo_directo_mes = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    coeficiente_manual = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    coeficiente_calculado = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cont_config_cif_detalle"
        unique_together = ("configuracion", "centro_costo")
        verbose_name = "Detalle CIF por Centro de Costo"
        verbose_name_plural = "Detalles CIF por Centro de Costo"

    def __str__(self):
        return f"{self.centro_costo.codigo} — coef. {self.coeficiente_calculado}"

    def valor_driver(self):
        driver = self.configuracion.driver if self.configuracion_id else None
        mapa = {
            "AREA": self.area_cm2,
            "HORAS_MAQUINA": self.horas_maquina_mes,
            "HORAS_HOMBRE": self.horas_hombre_mes,
            "UNIDADES": self.unidades_mes,
            "COSTO_DIRECTO": self.costo_directo_mes,
        }
        return mapa.get(driver) or Decimal("0")

    def save(self, *args, **kwargs):
        if self.coeficiente_manual is not None:
            self.coeficiente_calculado = self.coeficiente_manual
        else:
            base = self.configuracion.base_pivot if self.configuracion_id else None
            valor = self.valor_driver()
            if base and base > 0:
                self.coeficiente_calculado = valor / base
            else:
                self.coeficiente_calculado = Decimal("0")
        super().save(*args, **kwargs)


class ConfiguracionIVA(models.Model):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name="config_iva", verbose_name="Empresa")
    alicuota_general = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("16.00"), verbose_name="Alícuota general (%)")
    alicuota_reducida = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("8.00"), verbose_name="Alícuota reducida (%)")
    contribuyente_especial = models.BooleanField(default=False, verbose_name="¿Contribuyente especial?")
    rif = models.CharField(max_length=20, blank=True, verbose_name="RIF")
    razon_social = models.CharField(max_length=200, blank=True, verbose_name="Razón social fiscal")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cont_config_iva"
        verbose_name = "Configuración de IVA"
        verbose_name_plural = "Configuraciones de IVA"

    def __str__(self):
        return f"Config. IVA — {self.empresa.razon_social} ({self.alicuota_general}%)"


class FacturaFiscal(models.Model):
    """
    Documento fiscal (compra o venta) con todos los datos que exige el SENIAT.

    NOTA: numero_control es único por empresa + tipo. Cada tipo de documento
    (compra, venta, nota de débito, nota de crédito) tiene su propia serie
    de números de control. Esto refleja la práctica fiscal venezolana, donde
    compras y ventas usan series separadas.
    """
    TIPO_CHOICES = [
        ("COMPRA", "Compra"),
        ("VENTA", "Venta"),
        ("NOTA_DEBITO", "Nota de Débito"),
        ("NOTA_CREDITO", "Nota de Crédito"),
    ]

    ESTADO_CHOICES = [
        ("borrador", "Borrador"),
        ("confirmada", "Confirmada"),
        ("anulada", "Anulada"),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="facturas_fiscales", verbose_name="Empresa")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo de documento")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="borrador", verbose_name="Estado")

    numero_factura = models.CharField(max_length=30, verbose_name="Número de factura")
    numero_control = models.CharField(max_length=30, verbose_name="Número de control")
    fecha_emision = models.DateField(verbose_name="Fecha de emisión")
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de vencimiento")

    rif_contraparte = models.CharField(max_length=20, verbose_name="RIF del proveedor/cliente")
    razon_social_contraparte = models.CharField(max_length=200, verbose_name="Razón social")
    direccion_contraparte = models.TextField(blank=True, verbose_name="Dirección fiscal")

    base_imponible = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Base imponible")
    alicuota_iva = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("16.00"), verbose_name="Alícuota IVA (%)")
    monto_iva = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto IVA")
    monto_exento = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto exento")
    monto_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto total")

    iva_retenido = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="IVA retenido")
    numero_comprobante_retencion = models.CharField(max_length=30, blank=True, verbose_name="Nº comprobante retención")

    tipo_transaccion = models.CharField(
        max_length=30, blank=True,
        choices=[("NACIONAL", "Compra/Venta nacional"), ("IMPORTACION", "Importación"), ("EXPORTACION", "Exportación")],
        default="NACIONAL", verbose_name="Tipo de transacción",
    )

    asiento = models.OneToOneField(Asiento, on_delete=models.SET_NULL, null=True, blank=True, related_name="factura_fiscal", verbose_name="Asiento contable")
    factura_origen = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="notas", verbose_name="Factura origen")

    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    creado_por = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="facturas_creadas")
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cont_factura_fiscal"
        ordering = ["-fecha_emision", "-numero_factura"]
        verbose_name = "Factura Fiscal"
        verbose_name_plural = "Facturas Fiscales"
        # IMPORTANTE: el numero_control se distingue por tipo de documento.
        # Compras y ventas tienen series de control separadas.
        unique_together = [
            ("empresa", "tipo", "numero_factura"),
            ("empresa", "tipo", "numero_control"),
        ]
        indexes = [
            models.Index(fields=["empresa", "tipo", "fecha_emision"]),
            models.Index(fields=["empresa", "rif_contraparte"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.numero_factura} — {self.razon_social_contraparte}"

    def save(self, *args, **kwargs):
        if not self.monto_total or self.monto_total == 0:
            self.monto_total = (self.base_imponible or Decimal("0")) + \
                              (self.monto_iva or Decimal("0")) + \
                              (self.monto_exento or Decimal("0"))
        if (not self.monto_iva or self.monto_iva == 0) and self.base_imponible and self.alicuota_iva:
            self.monto_iva = (self.base_imponible * self.alicuota_iva / Decimal("100")).quantize(Decimal("0.01"))
            self.monto_total = self.base_imponible + self.monto_iva + (self.monto_exento or Decimal("0"))
        super().save(*args, **kwargs)

    @property
    def es_compra(self):
        return self.tipo in ("COMPRA", "NOTA_DEBITO") and self.factura_origen is None or self.tipo == "COMPRA"

    @property
    def es_venta(self):
        return self.tipo == "VENTA"


class FacturaFiscalLinea(models.Model):
    factura = models.ForeignKey(FacturaFiscal, on_delete=models.CASCADE, related_name="lineas", verbose_name="Factura")
    descripcion = models.CharField(max_length=300, verbose_name="Descripción")
    cantidad = models.DecimalField(max_digits=12, decimal_places=2, default=1, verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Precio unitario")
    base_imponible = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Base imponible")
    alicuota_iva = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("16.00"), verbose_name="Alícuota IVA (%)")
    monto_iva = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto IVA")
    monto_total = models.DecimalField(max_digits=18, decimal_places=2, default=0, verbose_name="Monto total")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")

    class Meta:
        db_table = "cont_factura_fiscal_linea"
        ordering = ["orden", "id"]
        verbose_name = "Línea de Factura Fiscal"
        verbose_name_plural = "Líneas de Factura Fiscal"

    def __str__(self):
        return f"{self.descripcion} — {self.monto_total}"

    def save(self, *args, **kwargs):
        if self.cantidad and self.precio_unitario:
            self.base_imponible = (self.cantidad * self.precio_unitario).quantize(Decimal("0.01"))
        if self.base_imponible and self.alicuota_iva:
            self.monto_iva = (self.base_imponible * self.alicuota_iva / Decimal("100")).quantize(Decimal("0.01"))
        self.monto_total = (self.base_imponible or Decimal("0")) + (self.monto_iva or Decimal("0"))
        super().save(*args, **kwargs)