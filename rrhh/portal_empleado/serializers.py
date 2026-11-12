"""
Serializers del Portal del Empleado.
"""
import re
from datetime import date

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from rrhh.models import (
    Empleado,
    NominaEmpleado,
    NominaDetalle,
    SaldoVacaciones,
    MovimientoSaldoVacaciones,
    SolicitudAusencia,
)
from .models import CuentaEmpleado


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def _normalizar_numero_empleado(numero_raw):
    """
    Normaliza el número de empleado.
    Ej: "EMP-0001", "emp-1", "EMP0001" → "EMP-0001"
    """
    if not numero_raw:
        return ""

    numero = numero_raw.strip().upper()

    # Si empieza con "EMP" y tiene número
    if numero.startswith("EMP"):
        match = re.match(r"^EMP[-\s]?0*(\d+)$", numero)
        if match:
            num = int(match.group(1))
            return f"EMP-{num:04d}"

    # Si es solo número, asumir que es un EMP
    if numero.isdigit():
        return f"EMP-{int(numero):04d}"

    return numero


def _normalizar_cedula(cedula_raw):
    """Quita prefijos (V-, E-), puntos y espacios de una cédula."""
    if not cedula_raw:
        return ""
    return (
        cedula_raw.strip()
        .replace("V-", "")
        .replace("E-", "")
        .replace("V", "")
        .replace("E", "")
        .replace(".", "")
        .replace("-", "")
        .replace(" ", "")
        .strip()
    )


# ═══════════════════════════════════════════════════════════
# LECTURA — CUENTA Y PERFIL
# ═══════════════════════════════════════════════════════════

class CuentaEmpleadoSerializer(serializers.ModelSerializer):
    """Serializer de lectura de CuentaEmpleado."""
    empleado_id = serializers.IntegerField(source="empleado.id", read_only=True)
    empleado_numero = serializers.CharField(source="empleado.numero_empleado", read_only=True)
    empleado_nombre = serializers.CharField(source="empleado.nombre_completo", read_only=True)
    empleado_email = serializers.EmailField(source="empleado.email", read_only=True)
    username = serializers.CharField(source="usuario.username", read_only=True)

    class Meta:
        model = CuentaEmpleado
        fields = [
            "id",
            "empleado_id",
            "empleado_numero",
            "empleado_nombre",
            "empleado_email",
            "username",
            "activo",
            "email_verificado",
            "ultimo_login",
            "fecha_creacion",
        ]


class PerfilEmpleadoSerializer(serializers.ModelSerializer):
    """
    Serializer del perfil del empleado (para GET /perfil/).
    El empleado solo puede ver sus propios datos.
    """
    cargo = serializers.CharField(source="cargo.nombre", read_only=True)
    departamento = serializers.CharField(source="departamento.nombre", read_only=True)
    sede = serializers.CharField(source="sede.nombre", read_only=True)
    empresa = serializers.CharField(source="empresa.razon_social", read_only=True)
    cedula_completa = serializers.CharField(read_only=True)
    antiguedad_dias = serializers.IntegerField(read_only=True)

    class Meta:
        model = Empleado
        fields = [
            "id",
            "numero_empleado",
            "nombre",
            "apellido_paterno",
            "apellido_materno",
            "cedula_completa",
            "email",
            "telefono",
            "telefono_habitacion",
            "direccion",
            "ciudad",
            "estado",
            "fecha_ingreso",
            "antiguedad_dias",
            "cargo",
            "departamento",
            "sede",
            "empresa",
            "estatus",
        ]


class PerfilEmpleadoUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer para que el empleado actualice sus datos personales.
    Solo permite editar: email, telefono, telefono_habitacion, direccion, ciudad, estado.
    """
    class Meta:
        model = Empleado
        fields = [
            "email",
            "telefono",
            "telefono_habitacion",
            "direccion",
            "ciudad",
            "estado",
        ]

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("El email es obligatorio.")
        return value.lower().strip()


# ═══════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════

class LoginFlexibleSerializer(serializers.Serializer):
    """
    Login flexible: acepta cédula, número de empleado, email o username.
    """
    identifier = serializers.CharField(
        max_length=150,
        help_text="Cédula, número de empleado, email o username.",
    )
    password = serializers.CharField(write_only=True)


class LoginUsernameSerializer(serializers.Serializer):
    """
    Login tradicional por username (compatibilidad).
    """
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class RegistroSerializer(serializers.Serializer):
    """
    Autoregistro del empleado.
    Valida que exista un Empleado con la cédula + número de empleado.
    """
    cedula = serializers.CharField(max_length=20)
    numero_empleado = serializers.CharField(max_length=30)
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, min_length=6)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({
                "password_confirm": "Las contraseñas no coinciden."
            })

        # Normalizar
        cedula_limpia = _normalizar_cedula(attrs["cedula"])
        numero_normalizado = _normalizar_numero_empleado(attrs["numero_empleado"])

        # Buscar empleado (probamos con el normalizado y con el original)
        empleado = None
        for numero in (numero_normalizado, attrs["numero_empleado"].strip(),
                       attrs["numero_empleado"].strip().upper()):
            empleado = Empleado.objects.filter(
                cedula=cedula_limpia,
                numero_empleado=numero,
                estatus="activo",
            ).first()
            if empleado:
                break

        if not empleado:
            raise serializers.ValidationError({
                "detail": "No encontramos un empleado activo con esos datos. "
                          "Verificá la cédula y el número de empleado, o contactá a RRHH."
            })

        # Verificar que no tenga ya una cuenta
        if hasattr(empleado, "cuenta_empleado"):
            raise serializers.ValidationError({
                "detail": "Este empleado ya tiene una cuenta creada. "
                          "Si olvidaste tu contraseña, contactá a RRHH."
            })

        # Validar password
        try:
            validate_password(attrs["password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})

        attrs["empleado"] = empleado
        attrs["cedula_limpia"] = cedula_limpia
        attrs["numero_normalizado"] = numero_normalizado
        return attrs


class CambioPasswordSerializer(serializers.Serializer):
    """Cambio de contraseña del empleado logueado."""
    password_actual = serializers.CharField(write_only=True)
    password_nuevo = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, min_length=6)

    def validate(self, attrs):
        if attrs["password_nuevo"] != attrs["password_confirm"]:
            raise serializers.ValidationError({
                "password_confirm": "Las contraseñas no coinciden."
            })
        if attrs["password_actual"] == attrs["password_nuevo"]:
            raise serializers.ValidationError({
                "password_nuevo": "La nueva contraseña debe ser diferente a la actual."
            })
        try:
            validate_password(attrs["password_nuevo"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password_nuevo": list(e.messages)})
        return attrs


class VerificarEmpleadoSerializer(serializers.Serializer):
    """
    Verifica si un empleado puede registrarse.
    """
    cedula = serializers.CharField(max_length=20)
    numero_empleado = serializers.CharField(max_length=30)


# ═══════════════════════════════════════════════════════════
# RECIBOS
# ═══════════════════════════════════════════════════════════

class PeriodoResumenSerializer(serializers.Serializer):
    """Resumen del periodo de nómina al que pertenece un recibo."""
    id = serializers.IntegerField()
    tipo = serializers.CharField()
    numero_periodo = serializers.IntegerField()
    anio = serializers.IntegerField()
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField()
    fecha_pago = serializers.DateField()


class ReciboListaSerializer(serializers.ModelSerializer):
    """Serializer para el listado de recibos (resumido)."""
    periodo = PeriodoResumenSerializer(read_only=True)
    periodo_label = serializers.SerializerMethodField()

    class Meta:
        model = NominaEmpleado
        fields = [
            "id",
            "periodo",
            "periodo_label",
            "salario_base",
            "dias_trabajados",
            "total_percepciones",
            "total_deducciones",
            "neto_pagar",
            "estatus",
        ]

    def get_periodo_label(self, obj):
        return f"{obj.periodo.get_tipo_display()} {obj.periodo.numero_periodo}/{obj.periodo.anio}"


class NominaDetalleSerializer(serializers.ModelSerializer):
    """Serializer de las líneas del recibo."""
    class Meta:
        model = NominaDetalle
        fields = [
            "id",
            "concepto",
            "tipo",
            "cantidad",
            "monto",
            "es_aporte_patronal",
        ]


class ReciboDetalleSerializer(serializers.ModelSerializer):
    """Serializer completo del recibo, con todos los detalles."""
    periodo = PeriodoResumenSerializer(read_only=True)
    detalles = NominaDetalleSerializer(many=True, read_only=True)
    periodo_label = serializers.SerializerMethodField()
    empleado_nombre = serializers.CharField(source="empleado.nombre_completo", read_only=True)
    empleado_numero = serializers.CharField(source="empleado.numero_empleado", read_only=True)
    empleado_cedula = serializers.CharField(source="empleado.cedula_completa", read_only=True)

    class Meta:
        model = NominaEmpleado
        fields = [
            "id",
            "periodo",
            "periodo_label",
            "empleado_nombre",
            "empleado_numero",
            "empleado_cedula",
            "salario_base",
            "salario_diario",
            "salario_normal",
            "salario_integral",
            "dias_periodo",
            "dias_trabajados",
            "dias_faltas",
            "dias_vacaciones",
            "dias_incapacidad",
            "horas_extra_diurnas",
            "horas_extra_nocturnas",
            "horas_nocturnas",
            "total_percepciones",
            "total_deducciones",
            "neto_pagar",
            "total_aportes_patronales",
            "costo_total_empresa",
            "base_islr",
            "islr_calculado",
            "base_ivss",
            "ivss_obrero",
            "estatus",
            "detalles",
        ]

    def get_periodo_label(self, obj):
        return f"{obj.periodo.get_tipo_display()} {obj.periodo.numero_periodo}/{obj.periodo.anio}"


# ═══════════════════════════════════════════════════════════
# VACACIONES
# ═══════════════════════════════════════════════════════════

class SaldoVacacionesSerializer(serializers.ModelSerializer):
    """Saldo de vacaciones de un año."""
    dias_pendientes = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True
    )
    esta_vencido = serializers.SerializerMethodField()
    dias_para_vencer = serializers.SerializerMethodField()

    class Meta:
        model = SaldoVacaciones
        fields = [
            "id",
            "anio",
            "dias_derecho",
            "dias_tomados",
            "dias_pagados",
            "dias_ajuste",
            "dias_pendientes",
            "fecha_limite_uso",
            "esta_vencido",
            "dias_para_vencer",
        ]

    def get_esta_vencido(self, obj):
        if not obj.fecha_limite_uso:
            return False
        return obj.fecha_limite_uso < date.today()

    def get_dias_para_vencer(self, obj):
        if not obj.fecha_limite_uso:
            return None
        return (obj.fecha_limite_uso - date.today()).days


class MovimientoVacacionesSerializer(serializers.ModelSerializer):
    """Movimiento del historial de saldo."""
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    usuario_nombre = serializers.SerializerMethodField()
    saldo_anio = serializers.IntegerField(source="saldo.anio", read_only=True)

    class Meta:
        model = MovimientoSaldoVacaciones
        fields = [
            "id",
            "saldo_anio",
            "tipo",
            "tipo_display",
            "dias",
            "saldo_anterior",
            "saldo_nuevo",
            "motivo",
            "usuario_nombre",
            "created_at",
        ]

    def get_usuario_nombre(self, obj):
        if not obj.usuario:
            return "Sistema"
        return obj.usuario.get_full_name() or obj.usuario.username


class SolicitudAusenciaPortalSerializer(serializers.ModelSerializer):
    """Solicitud de ausencia vista por el empleado."""
    tipo_nombre = serializers.CharField(source="tipo.nombre", read_only=True)
    estatus_display = serializers.CharField(source="get_estatus_display", read_only=True)
    aprobador_nombre = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudAusencia
        fields = [
            "id",
            "tipo_nombre",
            "fecha_inicio",
            "fecha_fin",
            "dias_solicitados",
            "dias_calendario",
            "fecha_reincorporacion",
            "motivo",
            "estatus",
            "estatus_display",
            "fecha_solicitud",
            "fecha_resolucion",
            "comentario_aprobador",
            "aprobador_nombre",
        ]

    def get_aprobador_nombre(self, obj):
        if not obj.aprobador:
            return None
        return obj.aprobador.nombre_completo


class CrearSolicitudSerializer(serializers.Serializer):
    """
    Serializer para crear una solicitud de vacaciones desde el portal.
    Solo necesita fecha_inicio y fecha_fin. El resto lo calcula el backend.
    """
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField()
    motivo = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["fecha_inicio"] > attrs["fecha_fin"]:
            raise serializers.ValidationError({
                "fecha_fin": "La fecha de fin debe ser posterior o igual a la de inicio."
            })
        return attrs