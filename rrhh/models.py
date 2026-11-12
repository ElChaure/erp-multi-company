from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.validators import RegexValidator
from django.utils import timezone
from decimal import Decimal
from datetime import date

# ═══════════════════════════════════════════════════════════
#  EMPRESA (Persona jurídica del grupo)
# ═══════════════════════════════════════════════════════════
        
class Empresa(models.Model):
    """
    Persona jurídica. Puede ser matriz, filial, holding o empresa externa.
    Soporta estructura multi-company del grupo empresarial.
    """

    TIPO_CHOICES = [
        ("matriz", "Matriz / Casa principal"),
        ("filial", "Empresa filial"),
        ("holding", "Holding / Grupo empresarial"),
        ("externa", "Empresa externa relacionada"),
    ]

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="matriz",
        verbose_name="Tipo de empresa",
    )
    padre = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="filiales",
        verbose_name="Empresa matriz",
        help_text="Empresa a la que pertenece, si aplica",
    )

    # Identificación fiscal
    rif = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="RIF",
        help_text="Formato: J-12345678-9",
    )
    razon_social = models.CharField(max_length=200, verbose_name="Razón social")
    nombre_comercial = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nombre comercial",
    )

    # Contacto
    telefono = models.CharField(max_length=30, blank=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, verbose_name="Email")
    sitio_web = models.URLField(blank=True, verbose_name="Sitio web")

    # Dirección fiscal
    direccion = models.TextField(blank=True, verbose_name="Dirección fiscal")
    ciudad = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=100, blank=True)
    pais = models.CharField(max_length=2, default="VE", verbose_name="País")

    # Configuración fiscal/laboral
    moneda = models.CharField(
        max_length=3,
        default="VES",
        verbose_name="Moneda",
        help_text="VES, USD, EUR",
    )
    zona_horaria = models.CharField(
        max_length=50,
        default="America/Caracas",
        verbose_name="Zona horaria",
    )

    # Logo (opcional)
    logo = models.ImageField(
        upload_to="empresas/logos/",
        null=True,
        blank=True,
        verbose_name="Logo",
    )
    
    # Campos para documentos formales
    firma_agente_retencion = models.ImageField(
        upload_to="empresas/firmas/",
        null=True,
        blank=True,
        verbose_name="Firma del agente de retención",
    )
    sello_empresa = models.ImageField(
        upload_to="empresas/sellos/",
        null=True,
        blank=True,
        verbose_name="Sello de la empresa",
    )
    nombre_agente_retencion = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nombre del agente de retención",
    )
    cargo_agente_retencion = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Cargo del agente de retención",
    )
    
    activa = models.BooleanField(default=True, verbose_name="Activa")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_empresa"
        verbose_name = "Empresa"
        verbose_name_plural = "Empresas"
        ordering = ["razon_social"]

    def __str__(self):
        return f"{self.nombre_comercial or self.razon_social} ({self.rif})"


# ═══════════════════════════════════════════════════════════
#  SEDE (Ubicación física de una empresa)
# ═══════════════════════════════════════════════════════════

class Sede(models.Model):
    """
    Sede o sucursal física de una empresa.
    Cada empresa puede tener varias sedes.
    """

    TIPO_CHOICES = [
        ("principal", "Sede principal"),
        ("sucursal", "Sucursal"),
        ("almacen", "Almacén"),
        ("planta", "Planta / Fábrica"),
        ("oficina", "Oficina"),
    ]

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="sedes",
        verbose_name="Empresa",
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="sucursal",
        verbose_name="Tipo de sede",
    )
    es_principal = models.BooleanField(
        default=False,
        verbose_name="¿Es la sede principal?",
    )

    nombre = models.CharField(max_length=150, verbose_name="Nombre")
    codigo = models.CharField(
        max_length=20,
        verbose_name="Código",
        help_text="Código único dentro de la empresa",
    )

    # Dirección
    direccion = models.TextField(blank=True, verbose_name="Dirección")
    ciudad = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=100, blank=True)
    pais = models.CharField(max_length=2, default="VE", verbose_name="País")
    codigo_postal = models.CharField(max_length=10, blank=True)

    # Contacto
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)

    activa = models.BooleanField(default=True, verbose_name="Activa")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_sede"
        verbose_name = "Sede"
        verbose_name_plural = "Sedes"
        ordering = ["empresa__razon_social", "nombre"]
        unique_together = [("empresa", "codigo")]
        indexes = [
            models.Index(fields=["empresa", "activa"]),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.empresa.razon_social})"

    def save(self, *args, **kwargs):
        # Si se marca como principal, desmarcar las demás de la misma empresa
        if self.es_principal:
            Sede.objects.filter(
                empresa=self.empresa,
                es_principal=True,
            ).exclude(pk=self.pk).update(es_principal=False)
        super().save(*args, **kwargs)


class Departamento(models.Model):
    """Área funcional dentro de la organización."""

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="departamentos",
        verbose_name="Empresa",
        null=True,
        blank=True,
    )
    padre = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subdepartamentos",
        verbose_name="Departamento padre",
    )
    codigo = models.CharField(max_length=20, verbose_name="Código")
    nombre = models.CharField(max_length=150, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    presupuesto_anual = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Presupuesto anual",
    )
    responsable = models.ForeignKey(
        "Empleado",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departamentos_responsable",
        verbose_name="Responsable",
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_departamento"
        verbose_name = "Departamento"
        verbose_name_plural = "Departamentos"
        ordering = ["nombre"]
        unique_together = [("empresa", "codigo")]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
        
class Cargo(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    salario_min = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    salario_max = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_cargo"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


# ═══════════════════════════════════════════════════════════
#  BANCO (Catálogo con códigos Sudeban)
# ═══════════════════════════════════════════════════════════

class Banco(models.Model):
    """
    Catálogo de bancos venezolanos con su código Sudeban de 4 dígitos.
    Los primeros 4 dígitos del número de cuenta (CCC) identifican al banco.
    """
    codigo = models.CharField(
        max_length=4,
        unique=True,
        verbose_name="Código Sudeban",
        help_text="Código de 4 dígitos asignado por Sudeban (ej: 0102)",
    )
    nombre = models.CharField(
        max_length=150,
        verbose_name="Nombre del banco",
    )
    nombre_corto = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Nombre corto",
        help_text="Para mostrar en listados (ej: BDV, Banesco)",
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_banco"
        verbose_name = "Banco"
        verbose_name_plural = "Bancos"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


# ═══════════════════════════════════════════════════════════
#  EMPLEADO (actualizado)
# ═══════════════════════════════════════════════════════════

class Empleado(models.Model):
    ESTATUS_CHOICES = [
        ("activo", "Activo"),
        ("baja", "Baja"),
        ("licencia", "Licencia"),
        ("vacaciones", "Vacaciones"),
    ]

    NACIONALIDAD_CHOICES = [
        ("V", "Venezolano"),
        ("E", "Extranjero"),
        ("P", "Pasaporte"),
    ]

    # ─── Identificación ───────────────────────────────────
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="empleados",
        verbose_name="Empresa",
        help_text="Empresa a la que pertenece el empleado",
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="empleados",
        verbose_name="Sede",
        help_text="Sede donde trabaja físicamente",
    )

    numero_empleado = models.CharField(
        max_length=30,
        verbose_name="Número de empleado",
        help_text="Formato: EMP-0001",
    )

    nacionalidad = models.CharField(
        max_length=1,
        choices=NACIONALIDAD_CHOICES,
        default="V",
        verbose_name="Nacionalidad",
    )
    cedula = models.CharField(
        max_length=20,
        verbose_name="Cédula / Pasaporte",
        help_text="Solo el número, sin la letra",
    )
    rif = models.CharField(
    max_length=20,
    blank=True,
    verbose_name="RIF",
    help_text="Registro de Información Fiscal (si aplica).",
    )   

    # ─── Datos personales ─────────────────────────────────
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    apellido_paterno = models.CharField(max_length=100, verbose_name="Apellido paterno")
    apellido_materno = models.CharField(max_length=100, blank=True, verbose_name="Apellido materno")
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de nacimiento")
    genero = models.CharField(
        max_length=20,
        blank=True,
        choices=[("M", "Masculino"), ("F", "Femenino"), ("O", "Otro")],
        verbose_name="Género",
    )
    estado_civil = models.CharField(
        max_length=30,
        blank=True,
        choices=[
            ("soltero", "Soltero/a"),
            ("casado", "Casado/a"),
            ("divorciado", "Divorciado/a"),
            ("viudo", "Viudo/a"),
            ("concubino", "Concubino/a"),
        ],
        verbose_name="Estado civil",
    )

    # ─── Contacto ─────────────────────────────────────────
    email = models.EmailField(verbose_name="Email")
    telefono = models.CharField(max_length=30, blank=True, verbose_name="Teléfono")
    # telefono_habitacion = models.CharField(max_length=30, blank=True)
    telefono_habitacion = models.CharField(
    max_length=30,
    blank=True,
    null=True,
    verbose_name="Teléfono Habitacion",
)

    # Domicilio
    direccion = models.TextField(blank=True, verbose_name="Dirección")
    ciudad = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=100, blank=True)
    pais = models.CharField(max_length=2, default="VE")

    # ─── Datos laborales ──────────────────────────────────
    cargo = models.ForeignKey(
        "Cargo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="empleados",
        verbose_name="Cargo",
    )
    departamento = models.ForeignKey(
        "Departamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="empleados",
        verbose_name="Departamento",
    )
    jefe = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subordinados",
        verbose_name="Jefe directo",
    )
    fecha_ingreso = models.DateField(verbose_name="Fecha de ingreso")
    fecha_egreso = models.DateField(null=True, blank=True, verbose_name="Fecha de egreso")
    tipo_contrato = models.CharField(
        max_length=30,
        blank=True,
        choices=[
            ("indefinido", "Indefinido"),
            ("temporal", "Temporal"),
            ("obra", "Por obra"),
            ("pasantia", "Pasantía"),
            ("honorarios", "Honorarios"),
        ],
        verbose_name="Tipo de contrato",
    )
    tipo_jornada = models.CharField(
        max_length=30,
        blank=True,
        choices=[
            ("completa", "Jornada completa"),
            ("parcial", "Jornada parcial"),
        ],
        verbose_name="Tipo de jornada",
    )
    estatus = models.CharField(
        max_length=20,
        choices=ESTATUS_CHOICES,
        default="activo",
        verbose_name="Estatus",
    )
    salario_base = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name="Salario base mensual",
    )
    periodicidad_pago = models.CharField(
        max_length=20,
        default="quincenal",
        choices=[
            ("semanal", "Semanal"),
            ("catorcenal", "Catorcenal"),
            ("quincenal", "Quincenal"),
            ("mensual", "Mensual"),
        ],
        verbose_name="Periodicidad de pago",
    )

    # ─── Datos bancarios ──────────────────────────────────
    
    banco = models.ForeignKey(
        Banco,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="empleados",
        verbose_name="Banco",
    )
    cuenta_bancaria = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Número de cuenta",
    )
    clabe = models.CharField(
        max_length=18,
        blank=True,
        null=True,
        verbose_name="CLABE interbancaria",
    )

    # ─── Auditoría ────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="empleados_creados",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="empleados_actualizados",
    )

    class Meta:
        db_table = "rrhh_empleado"
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"
        ordering = ["-fecha_ingreso"]
        # Único por empresa
        unique_together = [
            ("empresa", "numero_empleado"),
            ("empresa", "nacionalidad", "cedula"),
        ]
        indexes = [
            models.Index(fields=["empresa", "estatus"]),
            models.Index(fields=["empresa", "cedula"]),
            models.Index(fields=["sede"]),
            models.Index(fields=["cargo"]),
            models.Index(fields=["departamento"]),
        ]

    def __str__(self):
        return f"{self.numero_empleado} - {self.nombre} {self.apellido_paterno}"

    # ─── Propiedades ──────────────────────────────────────
    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido_paterno} {self.apellido_materno}".strip()

    @property
    def cedula_completa(self):
        """Retorna la cédula formateada: V-12345678"""
        return f"{self.nacionalidad}-{self.cedula}"

    @property
    def edad(self):
        if not self.fecha_nacimiento:
            return None
        from datetime import date
        hoy = date.today()
        return (
            hoy.year
            - self.fecha_nacimiento.year
            - ((hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day))
        )

    @property
    def antiguedad_dias(self):
        from datetime import date
        fin = self.fecha_egreso or date.today()
        return (fin - self.fecha_ingreso).days

# ═══════════════════════════════════════════════════════════
#  PERFIL DE USUARIO CON ROLES
# ═══════════════════════════════════════════════════════════

class Perfil(models.Model):
    """Extiende el User de Django con datos del sistema RRHH."""

    ROL_CHOICES = [
        ("superadmin", "Super Administrador (todas las empresas)"),
        ("admin", "Administrador de empresa"),
        ("rrhh", "Recursos Humanos"),
        ("manager", "Jefe / Manager"),
        ("empleado", "Empleado"),
    ]

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil",
    )
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default="empleado")
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios",
        verbose_name="Empresa",
        help_text="Empresa a la que pertenece el usuario. NULL = acceso global (superadmin).",
    )
    telefono = models.CharField(max_length=30, blank=True)
    cargo = models.CharField(max_length=100, blank=True)
    empleado = models.OneToOneField(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="perfil_usuario",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_perfil"
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"

    def __str__(self):
        return f"{self.usuario.username} ({self.get_rol_display()})"

    @property
    def es_superadmin(self):
        return self.rol == "superadmin" or self.usuario.is_superuser

    @property
    def es_admin(self):
        return self.rol in ("superadmin", "admin") or self.usuario.is_superuser

    @property
    def es_rrhh(self):
        return self.rol in ("superadmin", "admin", "rrhh") or self.usuario.is_superuser

    @property
    def es_manager(self):
        return self.rol in ("superadmin", "admin", "rrhh", "manager") or self.usuario.is_superuser

    @property
    def tiene_acceso_global(self):
        """Puede ver datos de todas las empresas."""
        return self.es_superadmin or self.empresa is None


# ═══════════════════════════════════════════════════════════
#  SIGNAL: crear perfil automáticamente al crear usuario
# ═══════════════════════════════════════════════════════════

@receiver(post_save, sender=User)
def crear_perfil_automatico(sender, instance, created, **kwargs):
    """Crea un Perfil automáticamente cuando se crea un User."""
    if created and not hasattr(instance, "perfil"):
        Perfil.objects.create(
            usuario=instance,
            rol="admin" if instance.is_superuser else "empleado",
        )        
        

# ═══════════════════════════════════════════════════════════
#  PARÁMETROS DE NÓMINA (configuración por empresa/año)
# ═══════════════════════════════════════════════════════════

class ParametroNomina(models.Model):
    """
    Parámetros legales y tasas para el cálculo de nómina.
    Permite tener distintos valores por año (útil cuando cambia el salario mínimo o la UT).
    """

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="parametros_nomina",
        verbose_name="Empresa",
    )
    anio = models.PositiveIntegerField(verbose_name="Año")

    # Salarios y unidades
    salario_minimo = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name="Salario mínimo mensual",
        help_text="En bolívares. Ej: 130.00",
    )
    cestaticket_mensual_usd = models.DecimalField(
        max_digits=15, decimal_places=2,
        default=40,
        verbose_name="Cestaticket mensual (USD)",
        help_text="Monto en USD que se convierte a Bs. según tasa BCV.",
    )
    unidad_tributaria = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name="Unidad Tributaria (UT)",
        help_text="En bolívares. Usada para ISLR.",
    )

    # Tasas IVSS
    ivss_obrero_pct = models.DecimalField(
        max_digits=6, decimal_places=4,
        default=Decimal("0.0400"),
        verbose_name="IVSS obrero (%)",
    )
    ivss_patronal_pct = models.DecimalField(
        max_digits=6, decimal_places=4,
        default=Decimal("0.0900"),
        verbose_name="IVSS patronal (%)",
    )
    ivss_tope_salarios = models.DecimalField(
        max_digits=6, decimal_places=2,
        default=Decimal("5"),
        verbose_name="Tope IVSS (n° salarios mínimos)",
    )

    # Tasas RPE (Paro Forzoso)
    rpe_obrero_pct = models.DecimalField(
        max_digits=6, decimal_places=4,
        default=Decimal("0.0050"),
        verbose_name="Paro Forzoso obrero (%)",
    )
    rpe_patronal_pct = models.DecimalField(
        max_digits=6, decimal_places=4,
        default=Decimal("0.0200"),
        verbose_name="Paro Forzoso patronal (%)",
    )
    rpe_tope_salarios = models.DecimalField(
        max_digits=6, decimal_places=2,
        default=Decimal("10"),
        verbose_name="Tope RPE (n° salarios mínimos)",
    )

    # BANAVIH
    banavih_obrero_pct = models.DecimalField(
        max_digits=6, decimal_places=4,
        default=Decimal("0.0100"),
        verbose_name="BANAVIH obrero (%)",
    )
    banavih_patronal_pct = models.DecimalField(
        max_digits=6, decimal_places=4,
        default=Decimal("0.0200"),
        verbose_name="BANAVIH patronal (%)",
    )

    # INCES
    inces_patronal_pct = models.DecimalField(
        max_digits=6, decimal_places=4,
        default=Decimal("0.0200"),
        verbose_name="INCES patronal (%)",
    )

    # LOPCYMAT
    lopcymat_categoria = models.CharField(
        max_length=5,
        choices=[
            ("I", "Riesgo mínimo (0.75%)"),
            ("II", "Riesgo bajo (1.5%)"),
            ("III", "Riesgo medio (3%)"),
            ("IV", "Riesgo alto (5%)"),
            ("V", "Riesgo máximo (10%)"),
        ],
        default="I",
        verbose_name="Categoría de riesgo LOPCYMAT",
    )

    # Prestaciones
    dias_prestaciones_trimestre = models.PositiveIntegerField(
        default=15, verbose_name="Días de prestaciones por trimestre"
    )
    dias_prestaciones_anio = models.PositiveIntegerField(
        default=30, verbose_name="Días de prestaciones por año"
    )
    dias_adicionales_por_anio = models.PositiveIntegerField(
        default=2, verbose_name="Días adicionales por año"
    )

    # Utilidades
    dias_utilidades_min = models.PositiveIntegerField(
        default=30, verbose_name="Días mínimos de utilidades"
    )
    dias_utilidades_max = models.PositiveIntegerField(
        default=120, verbose_name="Días máximos de utilidades"
    )

    # Vacaciones
    dias_vacaciones_base = models.PositiveIntegerField(
        default=15, verbose_name="Días base de vacaciones"
    )
    dias_vacaciones_max = models.PositiveIntegerField(
        default=30, verbose_name="Días máximos de vacaciones"
    )
    dias_bono_vacacional_base = models.PositiveIntegerField(
        default=15, verbose_name="Días base de bono vacacional"
    )
    dias_bono_vacacional_max = models.PositiveIntegerField(
        default=30, verbose_name="Días máximos de bono vacacional"
    )

    # Aguinaldo
    dias_aguinaldo = models.PositiveIntegerField(
        default=15, verbose_name="Días de aguinaldo por año"
    )

    # Factor de integración
    factor_integracion = models.DecimalField(
        max_digits=6, decimal_places=4,
        default=Decimal("1.0493"),
        verbose_name="Factor de integración",
        help_text="Usado para calcular el Salario Integral.",
    )

    # Tipo de cambio (para cestaticket)
    tasa_bcv_usd = models.DecimalField(
        max_digits=15, decimal_places=4,
        default=Decimal("1.00"),
        verbose_name="Tasa BCV (Bs./USD)",
        help_text="Se actualiza periódicamente según el BCV.",
    )

    activo = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_parametro_nomina"
        verbose_name = "Parámetro de nómina"
        verbose_name_plural = "Parámetros de nómina"
        ordering = ["empresa", "-anio"]
        unique_together = [("empresa", "anio")]

    def __str__(self):
        return f"{self.empresa.razon_social} - {self.anio}"

    @property
    def lopcymat_pct(self):
        """Retorna el porcentaje según la categoría."""
        mapa = {
            "I": Decimal("0.0075"),
            "II": Decimal("0.015"),
            "III": Decimal("0.03"),
            "IV": Decimal("0.05"),
            "V": Decimal("0.10"),
        }
        return mapa.get(self.lopcymat_categoria, Decimal("0.0075"))


# ═══════════════════════════════════════════════════════════
#  CONCEPTO DE NÓMINA
# ═══════════════════════════════════════════════════════════

class ConceptoNomina(models.Model):
    """
    Catálogo de conceptos de nómina (percepciones, deducciones, aportes).
    """

    TIPO_CHOICES = [
        ("percepcion", "Percepción"),
        ("deduccion", "Deducción"),
        ("aporte_patronal", "Aporte patronal"),
    ]

    NATURALEZA_CHOICES = [
        ("gravado", "Gravado (afecta ISLR)"),
        ("exento", "Exento (no afecta ISLR)"),
        ("mixto", "Mixto (parcialmente gravado)"),
    ]

    ORIGEN_CHOICES = [
        ("automatico", "Automático"),
        ("incidencia", "Incidencia"),
        ("manual", "Captura manual"),
        ("formula", "Fórmula"),
    ]

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="conceptos_nomina",
        verbose_name="Empresa",
        null=True,
        blank=True,
        help_text="Deja vacío para conceptos globales del sistema.",
    )
    codigo = models.CharField(max_length=20, verbose_name="Código")
    nombre = models.CharField(max_length=150, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")

    tipo = models.CharField(
        max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo"
    )
    naturaleza = models.CharField(
        max_length=20, choices=NATURALEZA_CHOICES,
        default="gravado", verbose_name="Naturaleza fiscal",
    )
    origen = models.CharField(
        max_length=20, choices=ORIGEN_CHOICES,
        default="automatico", verbose_name="Origen",
    )

    # Reglas de aplicación
    es_fijo = models.BooleanField(
        default=False, verbose_name="¿Es fijo?",
        help_text="Si es fijo, se aplica automáticamente en cada periodo.",
    )
    forma_parte_salario_normal = models.BooleanField(
        default=True,
        verbose_name="¿Forma parte del salario normal?",
        help_text="Afecta el cálculo de prestaciones, utilidades, vacaciones.",
    )
    afecta_isr = models.BooleanField(
        default=True, verbose_name="¿Afecta ISLR?",
    )
    afecta_ivss = models.BooleanField(
        default=True, verbose_name="¿Afecta IVSS?",
    )
    afecta_rpe = models.BooleanField(
        default=True, verbose_name="¿Afecta Paro Forzoso?",
    )
    afecta_banavih = models.BooleanField(
        default=False, verbose_name="¿Afecta BANAVIH?",
    )

    # Fórmula
    formula = models.TextField(
        blank=True,
        verbose_name="Fórmula",
        help_text="Expresión Python para el cálculo. Usa variables: salario_base, "
                  "dias_periodo, horas_extra, etc.",
    )

    # Orden de cálculo
    prioridad = models.PositiveIntegerField(
        default=100, verbose_name="Prioridad",
        help_text="Menor número = se calcula primero.",
    )

    # Exención
    exencion_formula = models.CharField(
        max_length=200, blank=True,
        verbose_name="Fórmula de exención",
        help_text="Ej: '5 * uma_diaria' para horas extra.",
    )

    activo = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_concepto_nomina"
        verbose_name = "Concepto de nómina"
        verbose_name_plural = "Conceptos de nómina"
        ordering = ["prioridad", "codigo"]
        unique_together = [("empresa", "codigo")]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


# ═══════════════════════════════════════════════════════════
#  PERIODO DE NÓMINA
# ═══════════════════════════════════════════════════════════

class PeriodoNomina(models.Model):
    """
    Periodo de nómina (semanal, catorcenal, quincenal, mensual).
    """

    TIPO_CHOICES = [
        ("semanal", "Semanal"),
        ("catorcenal", "Catorcenal"),
        ("quincenal", "Quincenal"),
        ("mensual", "Mensual"),
    ]

    ESTATUS_CHOICES = [
        ("abierto", "Abierto"),
        ("calculado", "Calculado"),
        ("aprobado", "Aprobado"),
        ("pagado", "Pagado"),
        ("cerrado", "Cerrado"),
        ("cancelado", "Cancelado"),
    ]

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="periodos_nomina",
        verbose_name="Empresa",
    )
    tipo = models.CharField(
        max_length=20, choices=TIPO_CHOICES, verbose_name="Tipo",
    )
    numero_periodo = models.PositiveIntegerField(
        verbose_name="Número de periodo", help_text="Ej: 1, 2, 3...",
    )
    anio = models.PositiveIntegerField(verbose_name="Año")

    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de fin")
    fecha_pago = models.DateField(verbose_name="Fecha de pago")

    estatus = models.CharField(
        max_length=20, choices=ESTATUS_CHOICES, default="abierto",
        verbose_name="Estatus",
    )

    # Totales (se llenan al calcular)
    total_percepciones = models.DecimalField(
        max_digits=18, decimal_places=2, default=0,
        verbose_name="Total percepciones",
    )
    total_deducciones = models.DecimalField(
        max_digits=18, decimal_places=2, default=0,
        verbose_name="Total deducciones",
    )
    total_neto = models.DecimalField(
        max_digits=18, decimal_places=2, default=0,
        verbose_name="Total neto",
    )
    total_aportes_patronales = models.DecimalField(
        max_digits=18, decimal_places=2, default=0,
        verbose_name="Total aportes patronales",
    )
    total_costo_empresa = models.DecimalField(
        max_digits=18, decimal_places=2, default=0,
        verbose_name="Costo total empresa",
    )

    empleados_procesados = models.PositiveIntegerField(
        default=0, verbose_name="Empleados procesados",
    )

    # Auditoría
    calculado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="periodos_calculados",
    )
    calculado_at = models.DateTimeField(null=True, blank=True)
    aprobado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="periodos_aprobados",
    )
    aprobado_at = models.DateTimeField(null=True, blank=True)
    cerrado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="periodos_cerrados",
    )
    cerrado_at = models.DateTimeField(null=True, blank=True)

    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_periodo_nomina"
        verbose_name = "Periodo de nómina"
        verbose_name_plural = "Periodos de nómina"
        ordering = ["-fecha_pago"]
        unique_together = [("empresa", "tipo", "anio", "numero_periodo")]
        indexes = [
            models.Index(fields=["empresa", "estatus"]),
            models.Index(fields=["empresa", "-fecha_pago"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} #{self.numero_periodo} ({self.fecha_inicio} - {self.fecha_fin})"

    @property
    def dias_periodo(self):
        """Calcula los días del periodo."""
        if self.tipo == "mensual":
            return 30
        return (self.fecha_fin - self.fecha_inicio).days + 1

    @property
    def puede_calcularse(self):
        return self.estatus in ("abierto", "calculado")

    @property
    def puede_cerrarse(self):
        return self.estatus in ("aprobado", "pagado")


# ═══════════════════════════════════════════════════════════
#  NÓMINA POR EMPLEADO
# ═══════════════════════════════════════════════════════════

class NominaEmpleado(models.Model):
    """
    Cabecera de la nómina de un empleado en un periodo específico.
    """

    ESTATUS_CHOICES = [
        ("calculado", "Calculado"),
        ("revisado", "Revisado"),
        ("pagado", "Pagado"),
        ("con_error", "Con error"),
    ]

    periodo = models.ForeignKey(
        PeriodoNomina,
        on_delete=models.CASCADE,
        related_name="nominas",
        verbose_name="Periodo",
    )
    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.CASCADE,
        related_name="nominas",
        verbose_name="Empleado",
    )

    # Datos base del cálculo
    salario_base = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name="Salario base mensual",
    )
    salario_diario = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name="Salario diario",
    )
    salario_normal = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name="Salario normal",
    )
    salario_integral = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Salario integral",
    )

    # Días
    dias_periodo = models.PositiveIntegerField(verbose_name="Días del periodo")
    dias_trabajados = models.PositiveIntegerField(
        default=0, verbose_name="Días trabajados",
    )
    dias_faltas = models.PositiveIntegerField(default=0, verbose_name="Faltas")
    dias_vacaciones = models.PositiveIntegerField(
        default=0, verbose_name="Días de vacaciones",
    )
    dias_incapacidad = models.PositiveIntegerField(
        default=0, verbose_name="Días de incapacidad",
    )

    # Horas
    horas_extra_diurnas = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name="Horas extra diurnas",
    )
    horas_extra_nocturnas = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name="Horas extra nocturnas",
    )
    horas_nocturnas = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name="Horas nocturnas normales",
    )

    # Totales
    total_percepciones = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Total percepciones",
    )
    total_deducciones = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Total deducciones",
    )
    neto_pagar = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Neto a pagar",
    )

    # Aportes patronales
    total_aportes_patronales = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Aportes patronales",
    )
    costo_total_empresa = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Costo total empresa",
    )

    # Bases para ISLR
    base_islr = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Base ISLR",
    )
    islr_calculado = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="ISLR calculado",
    )

    # Bases para IVSS
    base_ivss = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Base IVSS",
    )
    ivss_obrero = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="IVSS obrero",
    )

    estatus = models.CharField(
        max_length=20, choices=ESTATUS_CHOICES, default="calculado",
        verbose_name="Estatus",
    )
    errores = models.TextField(
        blank=True, verbose_name="Errores",
        help_text="Detalles si hubo errores al calcular.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_nomina_empleado"
        verbose_name = "Nómina por empleado"
        verbose_name_plural = "Nóminas por empleado"
        unique_together = [("periodo", "empleado")]
        indexes = [
            models.Index(fields=["periodo"]),
            models.Index(fields=["empleado"]),
        ]

    def __str__(self):
        return f"{self.empleado.nombre_completo} - {self.periodo}"


# ═══════════════════════════════════════════════════════════
#  DETALLE DE NÓMINA
# ═══════════════════════════════════════════════════════════

class NominaDetalle(models.Model):
    """
    Detalle de la nómina: una línea por concepto aplicado.
    """

    nomina = models.ForeignKey(
        NominaEmpleado,
        on_delete=models.CASCADE,
        related_name="detalles",
        verbose_name="Nómina",
    )
    concepto = models.ForeignKey(
        ConceptoNomina,
        on_delete=models.PROTECT,
        related_name="detalles",
        verbose_name="Concepto",
    )

    # Snapshot del concepto (por si cambia después)
    codigo_concepto = models.CharField(max_length=20, verbose_name="Código")
    nombre_concepto = models.CharField(max_length=150, verbose_name="Nombre")
    tipo = models.CharField(max_length=20, verbose_name="Tipo")
    naturaleza = models.CharField(max_length=20, verbose_name="Naturaleza")

    # Importes
    cantidad = models.DecimalField(
        max_digits=10, decimal_places=2, default=1,
        verbose_name="Cantidad",
    )
    base_calculo = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Base de cálculo",
    )
    importe = models.DecimalField(
        max_digits=15, decimal_places=2,
        verbose_name="Importe",
    )
    gravado = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Gravado (ISLR)",
    )
    exento = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Exento (ISLR)",
    )
    base_ivss = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Base IVSS",
    )

    observaciones = models.CharField(
        max_length=255, blank=True, verbose_name="Observaciones",
    )
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rrhh_nomina_detalle"
        verbose_name = "Detalle de nómina"
        verbose_name_plural = "Detalles de nómina"
        ordering = ["orden", "id"]

    def __str__(self):
        return f"{self.codigo_concepto} - {self.importe}"


# ═══════════════════════════════════════════════════════════
#  INCIDENCIAS DE NÓMINA
# ═══════════════════════════════════════════════════════════

class IncidenciaNomina(models.Model):
    """
    Incidencias que afectan la nómina: faltas, horas extra, retardos, etc.
    Se capturan antes de calcular el periodo.
    """

    TIPO_CHOICES = [
        ("falta", "Falta"),
        ("retardo", "Retardo"),
        ("hora_extra_diurna", "Hora extra diurna"),
        ("hora_extra_nocturna", "Hora extra nocturna"),
        ("hora_nocturna", "Hora nocturna normal"),
        ("vacacion", "Vacaciones"),
        ("incapacidad", "Incapacidad"),
        ("permiso", "Permiso"),
        ("feriado_trabajado", "Feriado trabajado"),
        ("descanso_trabajado", "Descanso trabajado"),
    ]

    ESTATUS_CHOICES = [
        ("pendiente", "Pendiente"),
        ("aprobada", "Aprobada"),
        ("rechazada", "Rechazada"),
        ("aplicada", "Aplicada"),
    ]

    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.CASCADE,
        related_name="incidencias_nomina",
        verbose_name="Empleado",
    )
    periodo = models.ForeignKey(
        PeriodoNomina,
        on_delete=models.CASCADE,
        related_name="incidencias",
        verbose_name="Periodo",
        null=True,
        blank=True,
        help_text="Puede asignarse después al calcular la nómina.",
    )

    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, verbose_name="Tipo")
    fecha = models.DateField(verbose_name="Fecha")
    cantidad = models.DecimalField(
        max_digits=8, decimal_places=2,
        verbose_name="Cantidad",
        help_text="Horas o días, según el tipo.",
    )
    unidad = models.CharField(
        max_length=10,
        choices=[("horas", "Horas"), ("dias", "Días")],
        verbose_name="Unidad",
    )

    motivo = models.TextField(blank=True, verbose_name="Motivo")
    documento_soporte = models.FileField(
        upload_to="rrhh/incidencias/%Y/%m/",
        null=True, blank=True,
        verbose_name="Documento de soporte",
    )

    estatus = models.CharField(
        max_length=20, choices=ESTATUS_CHOICES, default="pendiente",
        verbose_name="Estatus",
    )
    aprobado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="incidencias_aprobadas",
    )
    aprobado_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_incidencia_nomina"
        verbose_name = "Incidencia de nómina"
        verbose_name_plural = "Incidencias de nómina"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["empleado", "periodo"]),
            models.Index(fields=["tipo", "estatus"]),
        ]

    def __str__(self):
        return f"{self.empleado.numero_empleado} - {self.get_tipo_display()} ({self.fecha})"
        
# ═══════════════════════════════════════════════════════════
#  TIPOS DE AUSENCIA
# ═══════════════════════════════════════════════════════════

class TipoAusencia(models.Model):
    """
    Catálogo de tipos de ausencia (vacaciones, incapacidad, etc.).
    """

    CATEGORIA_CHOICES = [
        ("vacaciones", "Vacaciones"),
        ("enfermedad", "Enfermedad / Incapacidad"),
        ("maternidad", "Maternidad / Paternidad"),
        ("permiso", "Permiso especial"),
        ("duelo", "Duelo / Luto"),
        ("estudio", "Estudio / Capacitación"),
        ("personal", "Asuntos personales"),
        ("otro", "Otro"),
    ]

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="tipos_ausencia",
        verbose_name="Empresa",
        null=True,
        blank=True,
        help_text="Deja vacío para tipos globales.",
    )

    codigo = models.CharField(max_length=20, verbose_name="Código")
    nombre = models.CharField(max_length=150, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    categoria = models.CharField(
        max_length=30, choices=CATEGORIA_CHOICES, verbose_name="Categoría",
    )

    # Reglas de negocio
    con_goce_sueldo = models.BooleanField(
        default=True, verbose_name="¿Con goce de sueldo?",
    )
    requiere_aprobacion = models.BooleanField(
        default=True, verbose_name="¿Requiere aprobación?",
    )
    afecta_nomina = models.BooleanField(
        default=True,
        verbose_name="¿Afecta la nómina?",
        help_text="Si es True, se genera una incidencia al aprobar.",
    )
    afecta_saldo_vacaciones = models.BooleanField(
        default=False,
        verbose_name="¿Descuenta del saldo de vacaciones?",
        help_text="Solo aplica para tipos de vacaciones.",
    )
    requiere_comprobante = models.BooleanField(
        default=False,
        verbose_name="¿Requiere comprobante?",
    )

    dias_max_anuales = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Días máximos anuales",
        help_text="Dejar vacío para ilimitado.",
    )
    dias_max_por_solicitud = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Días máximos por solicitud",
    )
    dias_antelacion_minima = models.PositiveIntegerField(
        default=0,
        verbose_name="Días de antelación mínima",
    )

    activo = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_tipo_ausencia"
        verbose_name = "Tipo de ausencia"
        verbose_name_plural = "Tipos de ausencia"
        ordering = ["categoria", "nombre"]
        unique_together = [("empresa", "codigo")]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


# ═══════════════════════════════════════════════════════════
#  SALDO DE VACACIONES
# ═══════════════════════════════════════════════════════════

class SaldoVacaciones(models.Model):
    """
    Saldo de vacaciones de un empleado en un año específico.
    """

    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.CASCADE,
        related_name="saldos_vacaciones",
        verbose_name="Empleado",
    )
    anio = models.PositiveIntegerField(verbose_name="Año")

    # Días
    dias_derecho = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        verbose_name="Días de derecho",
        help_text="Días que le corresponden según LOTTT y su antigüedad.",
    )
    dias_tomados = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        verbose_name="Días tomados",
    )
    dias_pagados = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        verbose_name="Días pagados (no disfrutados)",
    )
    dias_ajuste = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        verbose_name="Ajuste manual",
        help_text="Positivo o negativo. Para correcciones.",
    )

    # Vigencia
    fecha_limite_uso = models.DateField(
        null=True, blank=True,
        verbose_name="Fecha límite de uso",
    )

    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_saldo_vacaciones"
        verbose_name = "Saldo de vacaciones"
        verbose_name_plural = "Saldos de vacaciones"
        ordering = ["-anio", "empleado__apellido_paterno"]
        unique_together = [("empleado", "anio")]
        indexes = [
            models.Index(fields=["empleado", "-anio"]),
        ]

    def __str__(self):
        return f"{self.empleado.nombre_completo} - {self.anio}"

    @property
    def dias_pendientes(self):
        """Días disponibles para tomar."""
        return (
            self.dias_derecho
            - self.dias_tomados
            - self.dias_pagados
            + self.dias_ajuste
        )

    @property
    def dias_disponibles(self):
        """Alias de dias_pendientes."""
        return max(self.dias_pendientes, Decimal("0"))


# ═══════════════════════════════════════════════════════════
#  SOLICITUD DE AUSENCIA
# ═══════════════════════════════════════════════════════════

class SolicitudAusencia(models.Model):
    """
    Solicitud de ausencia de un empleado.
    """

    ESTATUS_CHOICES = [
        ("borrador", "Borrador"),
        ("pendiente", "Pendiente"),
        ("aprobada", "Aprobada"),
        ("rechazada", "Rechazada"),
        ("cancelada", "Cancelada"),
        ("en_disfrute", "En disfrute"),
        ("finalizada", "Finalizada"),
    ]

    empleado = models.ForeignKey(
        Empleado,
        on_delete=models.CASCADE,
        related_name="solicitudes_ausencia",
        verbose_name="Empleado",
    )
    tipo = models.ForeignKey(
        TipoAusencia,
        on_delete=models.PROTECT,
        related_name="solicitudes",
        verbose_name="Tipo de ausencia",
    )

    # Fechas
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de fin")
    dias_solicitados = models.DecimalField(
        max_digits=6, decimal_places=2,
        verbose_name="Días solicitados",
    )
    dias_calendario = models.PositiveIntegerField(
        default=0,
        verbose_name="Días calendario",
    )
    fecha_reincorporacion = models.DateField(
        null=True, blank=True,
        verbose_name="Fecha de reincorporación",
    )

    # Detalles
    motivo = models.TextField(verbose_name="Motivo")
    comprobante = models.FileField(
        upload_to="rrhh/ausencias/comprobantes/%Y/%m/",
        null=True, blank=True,
        verbose_name="Comprobante",
    )

    # Aprobación
    estatus = models.CharField(
        max_length=20, choices=ESTATUS_CHOICES, default="pendiente",
        verbose_name="Estatus",
    )
    aprobador = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="solicitudes_por_aprobar",
        verbose_name="Aprobador",
    )
    fecha_solicitud = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de solicitud",
    )
    fecha_resolucion = models.DateTimeField(
        null=True, blank=True, verbose_name="Fecha de resolución",
    )
    comentario_aprobador = models.TextField(
        blank=True, verbose_name="Comentario del aprobador",
    )

    # Integración con nómina
    incidencia_generada = models.ForeignKey(
        IncidenciaNomina,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="solicitud_origen",
        verbose_name="Incidencia generada",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_solicitud_ausencia"
        verbose_name = "Solicitud de ausencia"
        verbose_name_plural = "Solicitudes de ausencia"
        ordering = ["-fecha_solicitud"]
        indexes = [
            models.Index(fields=["empleado", "estatus"]),
            models.Index(fields=["estatus", "fecha_inicio"]),
            models.Index(fields=["fecha_inicio", "fecha_fin"]),
        ]

    def __str__(self):
        return (
            f"{self.empleado.nombre_completo} - "
            f"{self.tipo.nombre} ({self.fecha_inicio} al {self.fecha_fin})"
        )

    @property
    def dias_habiles(self):
        """Calcula los días hábiles entre fecha_inicio y fecha_fin."""
        from datetime import timedelta

        dias = 0
        fecha = self.fecha_inicio
        while fecha <= self.fecha_fin:
            # Excluir sábados (5) y domingos (6)
            if fecha.weekday() < 5:
                dias += 1
            fecha += timedelta(days=1)
        return dias

    @property
    def puede_cancelar(self):
        """Solo se puede cancelar si no está finalizada ni rechazada."""
        return self.estatus in ("pendiente", "aprobada", "en_disfrute")

    @property
    def esta_en_curso(self):
        """Indica si la ausencia está ocurriendo hoy."""
        from datetime import date
        return self.fecha_inicio <= date.today() <= self.fecha_fin


# ═══════════════════════════════════════════════════════════
#  HISTORIAL DE SALDOS (opcional, para auditoría)
# ═══════════════════════════════════════════════════════════

class MovimientoSaldoVacaciones(models.Model):
    """
    Registro de movimientos del saldo de vacaciones (para auditoría).
    """

    TIPO_CHOICES = [
        ("asignacion", "Asignación inicial"),
        ("solicitud", "Descuento por solicitud"),
        ("ajuste", "Ajuste manual"),
        ("pago", "Pago de días no disfrutados"),
        ("vencimiento", "Vencimiento"),
    ]

    saldo = models.ForeignKey(
        SaldoVacaciones,
        on_delete=models.CASCADE,
        related_name="movimientos",
        verbose_name="Saldo",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    dias = models.DecimalField(
        max_digits=6, decimal_places=2,
        verbose_name="Días (+/-)",
    )
    saldo_anterior = models.DecimalField(max_digits=6, decimal_places=2)
    saldo_nuevo = models.DecimalField(max_digits=6, decimal_places=2)
    solicitud = models.ForeignKey(
        SolicitudAusencia,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="movimientos_saldo",
    )
    motivo = models.CharField(max_length=255, blank=True)
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rrhh_movimiento_saldo_vacaciones"
        verbose_name = "Movimiento de saldo"
        verbose_name_plural = "Movimientos de saldo"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.saldo.empleado} - {self.tipo} ({self.dias})"
        
# ═══════════════════════════════════════════════════════════
#  CONFIGURACIÓN DE VACACIONES (por empresa)
# ═══════════════════════════════════════════════════════════

class ConfiguracionVacaciones(models.Model):
    """
    Configuración de vacaciones por empresa.

    Permite definir reglas más ventajosas que la LOTTT (Art. 190 y 192)
    cuando exista un contrato colectivo, o ajustar la política interna
    sin tocar el código.

    Si `aplica_contrato_colectivo = True`, los campos `cc_*` sobreescriben
    los valores base de LOTTT.
    """
    empresa = models.OneToOneField(
        Empresa,
        on_delete=models.CASCADE,
        related_name="configuracion_vacaciones",
        verbose_name="Empresa",
    )

    # ─── Reglas LOTTT (defaults) ──────────────────────────
    dias_base_vacaciones = models.PositiveIntegerField(
        default=15,
        verbose_name="Días base de vacaciones",
        help_text="LOTTT: 15 días por el primer año.",
    )
    dias_base_bono_vacacional = models.PositiveIntegerField(
        default=15,
        verbose_name="Días base de bono vacacional",
        help_text="LOTTT: 15 días por el primer año.",
    )
    dias_max_vacaciones = models.PositiveIntegerField(
        default=30,
        verbose_name="Días máximos de vacaciones",
    )
    dias_max_bono_vacacional = models.PositiveIntegerField(
        default=30,
        verbose_name="Días máximos de bono vacacional",
    )
    incremento_anual_vacaciones = models.PositiveIntegerField(
        default=1,
        verbose_name="Incremento anual de vacaciones",
        help_text="Días que se suman por cada año adicional de servicio.",
    )
    incremento_anual_bono = models.PositiveIntegerField(
        default=1,
        verbose_name="Incremento anual de bono vacacional",
    )

    # ─── Contrato colectivo (opcional) ────────────────────
    aplica_contrato_colectivo = models.BooleanField(
        default=False,
        verbose_name="¿Aplica contrato colectivo?",
        help_text="Si está activo, los campos siguientes sobreescriben los de LOTTT.",
    )
    nombre_contrato_colectivo = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nombre del contrato colectivo",
    )
    cc_dias_vacaciones = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Días base vacaciones (CC)",
    )
    cc_dias_bono_vacacional = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Días base bono vacacional (CC)",
    )
    cc_incremento_anual_vacaciones = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Incremento anual vacaciones (CC)",
    )
    cc_incremento_anual_bono = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Incremento anual bono vacacional (CC)",
    )
    cc_dias_max_vacaciones = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Días máximos vacaciones (CC)",
    )
    cc_dias_max_bono = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Días máximos bono vacacional (CC)",
    )

    # ─── Vencimiento ──────────────────────────────────────
    meses_vencimiento = models.PositiveIntegerField(
        default=12,
        verbose_name="Meses para vencimiento",
        help_text="LOTTT: 12 meses. Configurable por empresa.",
    )

    # ─── Vacaciones colectivas ────────────────────────────
    permite_vacaciones_colectivas = models.BooleanField(
        default=True,
        verbose_name="¿Permite vacaciones colectivas?",
    )
    dias_colectivos_max = models.PositiveIntegerField(
        default=15,
        verbose_name="Días máximos de vacaciones colectivas",
        help_text="LOTTT Art. 191: hasta 15 días hábiles continuos.",
    )

    # ─── Antelación ───────────────────────────────────────
    dias_antelacion_solicitud = models.PositiveIntegerField(
        default=15,
        verbose_name="Días de antelación para solicitar",
        help_text="Días mínimos entre la solicitud y el inicio de las vacaciones.",
    )

    activa = models.BooleanField(default=True, verbose_name="Activa")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_configuracion_vacaciones"
        verbose_name = "Configuración de vacaciones"
        verbose_name_plural = "Configuraciones de vacaciones"

    def __str__(self):
        return f"Config. vacaciones - {self.empresa.razon_social}"

    # ─── Helpers: valores efectivos (LOTTT o CC) ──────────

    @property
    def valor_dias_vacaciones(self):
        """Días base de vacaciones (CC si aplica, si no LOTTT)."""
        if self.aplica_contrato_colectivo and self.cc_dias_vacaciones:
            return self.cc_dias_vacaciones
        return self.dias_base_vacaciones

    @property
    def valor_dias_bono_vacacional(self):
        if self.aplica_contrato_colectivo and self.cc_dias_bono_vacacional:
            return self.cc_dias_bono_vacacional
        return self.dias_base_bono_vacacional

    @property
    def valor_incremento_anual_vacaciones(self):
        if self.aplica_contrato_colectivo and self.cc_incremento_anual_vacaciones is not None:
            return self.cc_incremento_anual_vacaciones
        return self.incremento_anual_vacaciones

    @property
    def valor_incremento_anual_bono(self):
        if self.aplica_contrato_colectivo and self.cc_incremento_anual_bono is not None:
            return self.cc_incremento_anual_bono
        return self.incremento_anual_bono

    @property
    def valor_dias_max_vacaciones(self):
        if self.aplica_contrato_colectivo and self.cc_dias_max_vacaciones:
            return self.cc_dias_max_vacaciones
        return self.dias_max_vacaciones

    @property
    def valor_dias_max_bono(self):
        if self.aplica_contrato_colectivo and self.cc_dias_max_bono:
            return self.cc_dias_max_bono
        return self.dias_max_bono_vacacional


# ═══════════════════════════════════════════════════════════
#  VACACIONES COLECTIVAS
# ═══════════════════════════════════════════════════════════

class VacacionColectiva(models.Model):
    """
    Vacaciones colectivas: todo el personal (o un subconjunto) en las mismas fechas.

    Al aplicarse, genera una `SolicitudAusencia` por cada empleado activo
    del alcance definido, y descuenta los días del saldo correspondiente.
    """
    ESTATUS_CHOICES = [
        ("borrador", "Borrador"),
        ("aplicada", "Aplicada"),
        ("cancelada", "Cancelada"),
    ]

    ALCANCE_CHOICES = [
        ("empresa", "Toda la empresa"),
        ("sede", "Solo una sede"),
        ("departamento", "Solo un departamento"),
    ]

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="vacaciones_colectivas",
        verbose_name="Empresa",
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre",
        help_text="Ej: 'Vacaciones colectivas 2026'",
    )

    # Alcance
    alcance = models.CharField(
        max_length=20,
        choices=ALCANCE_CHOICES,
        default="empresa",
        verbose_name="Alcance",
    )
    sede = models.ForeignKey(
        Sede,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="vacaciones_colectivas",
        verbose_name="Sede",
    )
    departamento = models.ForeignKey(
        Departamento,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="vacaciones_colectivas",
        verbose_name="Departamento",
    )

    # Fechas
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de fin")
    dias_habiles = models.PositiveIntegerField(
        verbose_name="Días hábiles",
        help_text="Se calcula automáticamente al guardar.",
    )

    # Tipo de ausencia a usar (por defecto: el de vacaciones)
    tipo_ausencia = models.ForeignKey(
        TipoAusencia,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="vacaciones_colectivas",
        verbose_name="Tipo de ausencia",
        help_text="Si se deja vacío, se usará el primer tipo con categoría 'vacaciones'.",
    )

    # Estatus y trazabilidad
    estatus = models.CharField(
        max_length=20,
        choices=ESTATUS_CHOICES,
        default="borrador",
        verbose_name="Estatus",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    # Auditoría
    aplicada_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="vacaciones_colectivas_aplicadas",
    )
    aplicada_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="vacaciones_colectivas_creadas",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rrhh_vacacion_colectiva"
        verbose_name = "Vacación colectiva"
        verbose_name_plural = "Vacaciones colectivas"
        ordering = ["-fecha_inicio"]
        indexes = [
            models.Index(fields=["empresa", "estatus"]),
            models.Index(fields=["fecha_inicio", "fecha_fin"]),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.fecha_inicio} al {self.fecha_fin})"

    @property
    def total_solicitudes(self):
        """Cuenta cuántas solicitudes se generaron."""
        return self.solicitudes.count()

    @property
    def total_empleados(self):
        """Cuenta cuántos empleados están en el alcance."""
        return self._empleados_queryset().count()

    def _empleados_queryset(self):
        """Queryset de empleados según el alcance."""
        qs = Empleado.objects.filter(
            empresa=self.empresa,
            estatus="activo",
        )
        if self.alcance == "sede" and self.sede_id:
            qs = qs.filter(sede_id=self.sede_id)
        elif self.alcance == "departamento" and self.departamento_id:
            qs = qs.filter(departamento_id=self.departamento_id)
        return qs        
        