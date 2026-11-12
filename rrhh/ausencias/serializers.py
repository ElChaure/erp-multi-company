"""
Serializers para el módulo de ausencias.
"""
from rest_framework import serializers

from ..models import (
    TipoAusencia, SaldoVacaciones, SolicitudAusencia,
    MovimientoSaldoVacaciones,
)


# ═══════════════════════════════════════════════════════════
#  TIPOS DE AUSENCIA
# ═══════════════════════════════════════════════════════════

class TipoAusenciaSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoAusencia
        fields = ["id", "codigo", "nombre", "categoria"]


class TipoAusenciaSerializer(serializers.ModelSerializer):
    categoria_display = serializers.CharField(
        source="get_categoria_display", read_only=True,
    )

    class Meta:
        model = TipoAusencia
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


# ═══════════════════════════════════════════════════════════
#  SALDO DE VACACIONES
# ═══════════════════════════════════════════════════════════

class MovimientoSaldoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(
        source="get_tipo_display", read_only=True,
    )
    usuario_nombre = serializers.CharField(
        source="usuario.username", read_only=True,
    )
    anio = serializers.IntegerField(
        source="saldo.anio", read_only=True,
    )
    solicitud_fechas = serializers.SerializerMethodField()

    class Meta:
        model = MovimientoSaldoVacaciones
        fields = [
            "id", "anio", "tipo", "tipo_display", "dias",
            "saldo_anterior", "saldo_nuevo",
            "motivo", "usuario_nombre", "created_at",
            "solicitud_fechas",
        ]

    def get_solicitud_fechas(self, obj):
        if not obj.solicitud:
            return None
        return {
            "inicio": obj.solicitud.fecha_inicio.isoformat(),
            "fin": obj.solicitud.fecha_fin.isoformat(),
        }

class SaldoVacacionesSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.CharField(
        source="empleado.nombre_completo", read_only=True,
    )
    empleado_numero = serializers.CharField(
        source="empleado.numero_empleado", read_only=True,
    )
    empleado_cedula = serializers.CharField(
        source="empleado.cedula_completa", read_only=True,
    )
    dias_pendientes = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True,
    )
    dias_disponibles = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True,
    )
    movimientos = MovimientoSaldoSerializer(many=True, read_only=True)

    class Meta:
        model = SaldoVacaciones
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]

class SaldoVacacionesSimpleSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.CharField(
        source="empleado.nombre_completo", read_only=True,
    )
    dias_pendientes = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True,
    )

    class Meta:
        model = SaldoVacaciones
        fields = [
            "id", "empleado", "empleado_nombre", "anio",
            "dias_derecho", "dias_tomados", "dias_pagados",
            "dias_ajuste", "dias_pendientes",
        ]


# ═══════════════════════════════════════════════════════════
#  SOLICITUD DE AUSENCIA
# ═══════════════════════════════════════════════════════════

class SolicitudAusenciaListSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.CharField(
        source="empleado.nombre_completo", read_only=True,
    )
    empleado_numero = serializers.CharField(
        source="empleado.numero_empleado", read_only=True,
    )
    empleado_cedula = serializers.CharField(
        source="empleado.cedula_completa", read_only=True,
    )
    tipo_nombre = serializers.CharField(source="tipo.nombre", read_only=True)
    tipo_categoria = serializers.CharField(source="tipo.categoria", read_only=True)
    estatus_display = serializers.CharField(
        source="get_estatus_display", read_only=True,
    )
    aprobador_nombre = serializers.CharField(
        source="aprobador.nombre_completo", read_only=True,
    )

    class Meta:
        model = SolicitudAusencia
        fields = [
            "id", "empleado", "empleado_nombre", "empleado_numero",
            "empleado_cedula", "tipo", "tipo_nombre", "tipo_categoria",
            "fecha_inicio", "fecha_fin", "dias_solicitados",
            "dias_calendario", "estatus", "estatus_display",
            "aprobador", "aprobador_nombre", "fecha_solicitud",
        ]


class SolicitudAusenciaSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.CharField(
        source="empleado.nombre_completo", read_only=True,
    )
    empleado_numero = serializers.CharField(
        source="empleado.numero_empleado", read_only=True,
    )
    empleado_cedula = serializers.CharField(
        source="empleado.cedula_completa", read_only=True,
    )
    tipo_nombre = serializers.CharField(source="tipo.nombre", read_only=True)
    tipo_detalle = TipoAusenciaSimpleSerializer(source="tipo", read_only=True)
    estatus_display = serializers.CharField(
        source="get_estatus_display", read_only=True,
    )
    aprobador_nombre = serializers.CharField(
        source="aprobador.nombre_completo", read_only=True,
    )

    class Meta:
        model = SolicitudAusencia
        fields = "__all__"
        read_only_fields = [
            "id", "dias_calendario", "fecha_reincorporacion",
            "aprobador", "fecha_solicitud", "fecha_resolucion",
            "comentario_aprobador", "incidencia_generada",
            "created_at", "updated_at",
        ]


class CrearSolicitudAusenciaSerializer(serializers.Serializer):
    """Serializer para crear una solicitud (payload de entrada)."""
    empleado_id = serializers.IntegerField()
    tipo_id = serializers.IntegerField()
    fecha_inicio = serializers.DateField()
    fecha_fin = serializers.DateField()
    dias_solicitados = serializers.DecimalField(max_digits=6, decimal_places=2)
    motivo = serializers.CharField()

    def validate(self, attrs):
        from ..models import Empleado, TipoAusencia
        from . import services

        try:
            empleado = Empleado.objects.get(pk=attrs["empleado_id"])
        except Empleado.DoesNotExist:
            raise serializers.ValidationError({"empleado_id": "Empleado no encontrado."})

        try:
            tipo = TipoAusencia.objects.get(pk=attrs["tipo_id"])
        except TipoAusencia.DoesNotExist:
            raise serializers.ValidationError({"tipo_id": "Tipo de ausencia no encontrado."})

        # Validar con el servicio
        try:
            services.validar_solicitud(
                empleado=empleado,
                tipo=tipo,
                fecha_inicio=attrs["fecha_inicio"],
                fecha_fin=attrs["fecha_fin"],
                dias_solicitados=attrs["dias_solicitados"],
            )
        except Exception as e:
            raise serializers.ValidationError(str(e))

        attrs["empleado"] = empleado
        attrs["tipo"] = tipo
        return attrs