"""
Modelos del Portal del Empleado (autoservicio vía API REST).

Este modelo NO reemplaza al Perfil. Conviven:
    - Perfil (rol: superadmin/admin/rrhh/manager/empleado) → accesos a Django admin y vistas HTML
    - CuentaEmpleado (rol único: empleado) → accesos al portal API vía JWT
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class CuentaEmpleado(models.Model):
    """
    Cuenta de autoservicio para un empleado.

    Permite que el empleado acceda al portal del empleado vía API REST
    (con JWT) y consulte sus recibos, saldos de vacaciones, etc.

    Se vincula 1:1 con un Empleado y con un User (de Django).
    """
    empleado = models.OneToOneField(
        "rrhh.Empleado",
        on_delete=models.CASCADE,
        related_name="cuenta_empleado",
        verbose_name="Empleado",
    )
    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="cuenta_empleado",
        verbose_name="Usuario",
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activa",
        help_text="Si está inactiva, no puede loguearse.",
    )
    # Para auto-activado: email_verificado=True por defecto (decisión de diseño)
    email_verificado = models.BooleanField(
        default=True,
        verbose_name="Email verificado",
    )
    # Último login (se actualiza al loguearse)
    ultimo_login = models.DateTimeField(
        null=True, blank=True, verbose_name="Último login",
    )
    ultimo_login_ip = models.GenericIPAddressField(
        null=True, blank=True, verbose_name="IP último login",
    )
    # Último identificador usado para login (cédula, email, username, etc.)
    # Se usa para autocompletar en el frontend
    ultimo_identificador_usado = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Último identificador usado",
        help_text="Se guarda para autocompletar en el próximo login.",
    )
    # Auditoría
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="cuentas_empleado_creadas",
        verbose_name="Creada por",
        help_text="Null si la creó el propio empleado (autoregistro).",
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de creación",
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True, verbose_name="Fecha de actualización",
    )

    class Meta:
        db_table = "rrhh_cuenta_empleado"
        verbose_name = "Cuenta de empleado"
        verbose_name_plural = "Cuentas de empleados"
        ordering = ["-fecha_creacion"]
        indexes = [
            models.Index(fields=["activo", "-ultimo_login"]),
        ]

    def __str__(self):
        return f"{self.empleado.numero_empleado} - {self.usuario.username}"

    def registrar_login(self, ip=None, identificador=None):
        """
        Marca el login con fecha, IP y opcionalmente el identificador usado.
        """
        self.ultimo_login = timezone.now()
        update_fields = ["ultimo_login", "fecha_actualizacion"]
        
        if ip:
            self.ultimo_login_ip = ip
            update_fields.append("ultimo_login_ip")
        
        if identificador:
            self.ultimo_identificador_usado = identificador
            update_fields.append("ultimo_identificador_usado")
        
        self.save(update_fields=update_fields)