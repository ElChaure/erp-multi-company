from rest_framework import serializers
from django.contrib.auth.models import User

from .models import (
    # Core
    Empresa, Sede, Cargo, Departamento,
    # Empleado
    Empleado, Perfil,
    # Nómina
    ParametroNomina, ConceptoNomina, PeriodoNomina,
    NominaEmpleado, NominaDetalle, IncidenciaNomina,
    Banco,
)


# ═══════════════════════════════════════════════════════════
#  EMPRESA
# ═══════════════════════════════════════════════════════════

class EmpresaSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = ["id", "rif", "razon_social", "nombre_comercial"]


class EmpresaSerializer(serializers.ModelSerializer):
    sedes_count = serializers.IntegerField(source="sedes.count", read_only=True)
    empleados_count = serializers.IntegerField(source="empleados.count", read_only=True)
    padre_nombre = serializers.CharField(source="padre.razon_social", read_only=True)

    class Meta:
        model = Empresa
        fields = [
            "id", "tipo", "padre", "padre_nombre",
            "rif", "razon_social", "nombre_comercial",
            "telefono", "email", "sitio_web",
            "direccion", "ciudad", "estado", "pais",
            "moneda", "zona_horaria", "logo",
            "activa", "sedes_count", "empleados_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ═══════════════════════════════════════════════════════════
#  SEDE
# ═══════════════════════════════════════════════════════════

class SedeSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sede
        fields = ["id", "codigo", "nombre", "es_principal"]


class SedeSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source="empresa.razon_social", read_only=True)
    empleados_count = serializers.IntegerField(source="empleados.count", read_only=True)

    class Meta:
        model = Sede
        fields = [
            "id", "empresa", "empresa_nombre",
            "tipo", "es_principal",
            "codigo", "nombre",
            "direccion", "ciudad", "estado", "pais", "codigo_postal",
            "telefono", "email",
            "activa", "empleados_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ═══════════════════════════════════════════════════════════
#  CARGO
# ═══════════════════════════════════════════════════════════

class CargoSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cargo
        fields = ["id", "codigo", "nombre"]


class CargoSerializer(serializers.ModelSerializer):
    empleados_count = serializers.IntegerField(source="empleados.count", read_only=True)

    class Meta:
        model = Cargo
        fields = [
            "id", "codigo", "nombre", "descripcion",
            "salario_min", "salario_max", "activo",
            "empleados_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "empleados_count", "created_at", "updated_at"]


# ═══════════════════════════════════════════════════════════
#  DEPARTAMENTO
# ═══════════════════════════════════════════════════════════

class DepartamentoSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Departamento
        fields = ["id", "codigo", "nombre"]


class DepartamentoSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source="empresa.razon_social", read_only=True)
    padre_nombre = serializers.CharField(source="padre.nombre", read_only=True)
    empleados_count = serializers.IntegerField(source="empleados.count", read_only=True)

    class Meta:
        model = Departamento
        fields = [
            "id", "empresa", "empresa_nombre",
            "padre", "padre_nombre",
            "codigo", "nombre", "descripcion",
            "presupuesto_anual", "responsable",
            "activo", "empleados_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "empleados_count", "created_at", "updated_at"]

# ═══════════════════════════════════════════════════════════
#  BANCO
# ═══════════════════════════════════════════════════════════


class BancoSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banco
        fields = ["id", "codigo", "nombre", "nombre_corto"]


# ═══════════════════════════════════════════════════════════
#  EMPLEADO
# ═══════════════════════════════════════════════════════════

class EmpleadoListSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(read_only=True)
    cedula_completa = serializers.CharField(read_only=True)
    cargo = CargoSimpleSerializer(read_only=True)
    departamento = DepartamentoSimpleSerializer(read_only=True)
    sede = SedeSimpleSerializer(read_only=True)
    banco = BancoSimpleSerializer(read_only=True)

    class Meta:
        model = Empleado
        fields = [
            "id",
            "numero_empleado",
            "nombre_completo",
            "cedula_completa",
            "email",
            "telefono",
            "cargo",
            "departamento",
            "sede",
            "fecha_ingreso",
            "salario_base",
            "banco", 
            "cuenta_bancaria",
            "estatus",
        ]


class EmpleadoSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(read_only=True)
    cedula_completa = serializers.CharField(read_only=True)
    cargo = CargoSimpleSerializer(read_only=True)
    departamento = DepartamentoSimpleSerializer(read_only=True)
    empresa = EmpresaSimpleSerializer(read_only=True)
    sede = SedeSimpleSerializer(read_only=True)
    banco = BancoSimpleSerializer(read_only=True)
    banco_id = serializers.PrimaryKeyRelatedField(
        queryset=Banco.objects.all(),
        source="banco",
        write_only=True,
        required=False,
        allow_null=True,
    )
    
    # Campos de escritura
    empresa_id = serializers.PrimaryKeyRelatedField(
        queryset=Empresa.objects.all(),
        source="empresa",
        write_only=True,
    )
    sede_id = serializers.PrimaryKeyRelatedField(
        queryset=Sede.objects.all(),
        source="sede",
        write_only=True,
        required=False,
        allow_null=True,
    )
    cargo_id = serializers.PrimaryKeyRelatedField(
        queryset=Cargo.objects.all(),
        source="cargo",
        write_only=True,
        required=False,
        allow_null=True,
    )
    departamento_id = serializers.PrimaryKeyRelatedField(
        queryset=Departamento.objects.all(),
        source="departamento",
        write_only=True,
        required=False,
        allow_null=True,
    )
    jefe_id = serializers.PrimaryKeyRelatedField(
        queryset=Empleado.objects.all(),
        source="jefe",
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Empleado
        fields = [
            "id",
            "empresa", "empresa_id",
            "sede", "sede_id",
            "numero_empleado",
            "nacionalidad", "cedula", "cedula_completa",
            "nombre", "apellido_paterno", "apellido_materno",
            "nombre_completo",
            "fecha_nacimiento", "genero", "estado_civil",
            "email", "telefono", "telefono_habitacion",
            "direccion", "ciudad", "estado", "pais",
            "cargo", "cargo_id",
            "departamento", "departamento_id",
            "jefe", "jefe_id",
            "fecha_ingreso", "fecha_egreso",
            "tipo_contrato", "tipo_jornada", "estatus",
            "salario_base", "periodicidad_pago",
            "banco", "banco_id",
            "cuenta_bancaria", "clabe",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at",
            "nombre_completo", "cedula_completa",
        ]

    def validate_numero_empleado(self, value):
        import re
        if not re.match(r"^EMP-\d{4}$", value):
            raise serializers.ValidationError(
                "El número debe tener el formato EMP-0001."
            )
        return value

    def validate_salario_base(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "El salario debe ser mayor a cero."
            )
        return value

    def validate_cedula(self, value):
        return value.replace(".", "").replace(" ", "").strip()


# ═══════════════════════════════════════════════════════════
#  USUARIO Y PERFIL
# ═══════════════════════════════════════════════════════════

class PerfilSerializer(serializers.ModelSerializer):
    rol_display = serializers.CharField(source="get_rol_display", read_only=True)
    empresa_nombre = serializers.CharField(source="empresa.razon_social", read_only=True)

    class Meta:
        model = Perfil
        fields = [
            "id", "rol", "rol_display",
            "empresa", "empresa_nombre",
            "telefono", "cargo",
        ]


class UsuarioSerializer(serializers.ModelSerializer):
    perfil = PerfilSerializer(read_only=True)
    nombre_completo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email",
            "first_name", "last_name", "nombre_completo",
            "is_active", "is_staff",
            "perfil", "last_login", "date_joined",
        ]
        read_only_fields = ["id", "last_login", "date_joined"]

    def get_nombre_completo(self, obj):
        return obj.get_full_name() or obj.username


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )


# ═══════════════════════════════════════════════════════════
#  NÓMINA - PARÁMETROS
# ═══════════════════════════════════════════════════════════

class ParametroNominaSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source="empresa.razon_social", read_only=True)
    lopcymat_pct = serializers.DecimalField(
        max_digits=6, decimal_places=4, read_only=True,
    )

    class Meta:
        model = ParametroNomina
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


# ═══════════════════════════════════════════════════════════
#  NÓMINA - CONCEPTOS
# ═══════════════════════════════════════════════════════════

class ConceptoNominaSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    naturaleza_display = serializers.CharField(
        source="get_naturaleza_display", read_only=True,
    )
    origen_display = serializers.CharField(
        source="get_origen_display", read_only=True,
    )

    class Meta:
        model = ConceptoNomina
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]


class ConceptoNominaSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConceptoNomina
        fields = ["id", "codigo", "nombre", "tipo", "naturaleza"]


# ═══════════════════════════════════════════════════════════
#  NÓMINA - PERIODOS
# ═══════════════════════════════════════════════════════════

class PeriodoNominaSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source="empresa.razon_social", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    estatus_display = serializers.CharField(source="get_estatus_display", read_only=True)
    dias_periodo = serializers.IntegerField(read_only=True)

    class Meta:
        model = PeriodoNomina
        fields = "__all__"
        read_only_fields = [
            "id",
            "total_percepciones", "total_deducciones", "total_neto",
            "total_aportes_patronales", "total_costo_empresa",
            "empleados_procesados",
            "calculado_por", "calculado_at",
            "aprobado_por", "aprobado_at",
            "cerrado_por", "cerrado_at",
            "created_at", "updated_at",
        ]


class PeriodoNominaSimpleSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    estatus_display = serializers.CharField(source="get_estatus_display", read_only=True)
    dias_periodo = serializers.IntegerField(read_only=True)

    class Meta:
        model = PeriodoNomina
        fields = [
            "id", "empresa", "tipo", "tipo_display",
            "numero_periodo", "anio",
            "fecha_inicio", "fecha_fin", "fecha_pago",
            "estatus", "estatus_display",
            "dias_periodo",
            "total_percepciones", "total_deducciones", "total_neto",
            "total_aportes_patronales", "total_costo_empresa",
            "empleados_procesados",
        ]


# ═══════════════════════════════════════════════════════════
#  NÓMINA - EMPLEADO
# ═══════════════════════════════════════════════════════════

class NominaDetalleSerializer(serializers.ModelSerializer):
    class Meta:
        model = NominaDetalle
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


class NominaEmpleadoSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.CharField(
        source="empleado.nombre_completo", read_only=True,
    )
    empleado_numero = serializers.CharField(
        source="empleado.numero_empleado", read_only=True,
    )
    empleado_cedula = serializers.CharField(
        source="empleado.cedula_completa", read_only=True,
    )
    periodo_display = serializers.CharField(
        source="periodo.__str__", read_only=True,
    )
    detalles = NominaDetalleSerializer(many=True, read_only=True)

    class Meta:
        model = NominaEmpleado
        fields = "__all__"
        read_only_fields = [
            "id",
            "total_percepciones", "total_deducciones", "neto_pagar",
            "total_aportes_patronales", "costo_total_empresa",
            "islr_calculado", "ivss_obrero",
            "created_at", "updated_at",
        ]


class NominaEmpleadoListSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.CharField(
        source="empleado.nombre_completo", read_only=True,
    )
    empleado_numero = serializers.CharField(
        source="empleado.numero_empleado", read_only=True,
    )
    empleado_cedula = serializers.CharField(
        source="empleado.cedula_completa", read_only=True,
    )

    class Meta:
        model = NominaEmpleado
        fields = [
            "id", "empleado", "empleado_numero",
            "empleado_nombre", "empleado_cedula",
            "dias_periodo", "dias_trabajados", "dias_faltas",
            "total_percepciones", "total_deducciones",
            "neto_pagar", "estatus",
        ]


# ═══════════════════════════════════════════════════════════
#  NÓMINA - INCIDENCIAS
# ═══════════════════════════════════════════════════════════

class IncidenciaNominaSerializer(serializers.ModelSerializer):
    empleado_nombre = serializers.CharField(
        source="empleado.nombre_completo", read_only=True,
    )
    empleado_numero = serializers.CharField(
        source="empleado.numero_empleado", read_only=True,
    )
    tipo_display = serializers.CharField(
        source="get_tipo_display", read_only=True,
    )
    estatus_display = serializers.CharField(
        source="get_estatus_display", read_only=True,
    )

    class Meta:
        model = IncidenciaNomina
        fields = "__all__"
        read_only_fields = [
            "id", "created_at", "updated_at",
            "aprobado_por", "aprobado_at",
        ]
        
# ═══════════════════════════════════════════════════════════
#  PORTAL DEL EMPLEADO — RECIBOS
# ═══════════════════════════════════════════════════════════

class MiReciboListSerializer(serializers.ModelSerializer):
    """
    Serializer para el listado de recibos del empleado logueado.
    Solo expone los campos relevantes para la vista del portal.
    """
    periodo_tipo_display = serializers.CharField(
        source="periodo.get_tipo_display", read_only=True,
    )
    periodo_numero = serializers.IntegerField(
        source="periodo.numero_periodo", read_only=True,
    )
    periodo_anio = serializers.IntegerField(
        source="periodo.anio", read_only=True,
    )
    periodo_estatus_display = serializers.CharField(
        source="periodo.get_estatus_display", read_only=True,
    )
    fecha_inicio = serializers.DateField(
        source="periodo.fecha_inicio", read_only=True,
    )
    fecha_fin = serializers.DateField(
        source="periodo.fecha_fin", read_only=True,
    )
    fecha_pago = serializers.DateField(
        source="periodo.fecha_pago", read_only=True,
    )

    class Meta:
        model = NominaEmpleado
        fields = [
            "id",
            "periodo_tipo_display",
            "periodo_numero",
            "periodo_anio",
            "periodo_estatus_display",
            "fecha_inicio",
            "fecha_fin",
            "fecha_pago",
            "dias_periodo",
            "dias_trabajados",
            "total_percepciones",
            "total_deducciones",
            "neto_pagar",
        ]        