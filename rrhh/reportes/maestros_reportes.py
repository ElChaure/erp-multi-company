"""
Reportes maestros: listados de catálogos (empresas, sedes, departamentos,
cargos, empleados, conceptos, parámetros, incidencias).

Todas las funciones devuelven listas de dicts listos para serializar.
"""
from decimal import Decimal

from django.db.models import Count, Sum, Q

from ..models import (
    Empresa, Sede, Departamento, Cargo,
    Empleado, ConceptoNomina, ParametroNomina, IncidenciaNomina,
)


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _empresa_qs(empresa_id=None):
    """Filtra empresas por ID si se especifica."""
    qs = Empresa.objects.all()
    if empresa_id:
        qs = qs.filter(id=empresa_id)
    return qs.order_by("razon_social")


# ═══════════════════════════════════════════════════════════
#  1. EMPRESAS
# ═══════════════════════════════════════════════════════════

def reporte_empresas(empresa_id=None, tipo=None, activa=None):
    """
    Reporte maestro de empresas.

    Args:
        empresa_id: filtrar por una empresa específica
        tipo: filtrar por tipo (matriz, filial, holding, externa)
        activa: filtrar por activa (True/False/None)

    Returns:
        lista de dicts con:
            - id, rif, razon_social, nombre_comercial
            - tipo, tipo_display
            - padre_nombre
            - telefono, email, sitio_web
            - direccion, ciudad, estado, pais
            - moneda, zona_horaria
            - sedes_count, departamentos_count, empleados_count
            - activa
    """
    qs = _empresa_qs(empresa_id)

    if tipo:
        qs = qs.filter(tipo=tipo)
    if activa is not None:
        qs = qs.filter(activa=activa)

    qs = qs.annotate(
        sedes_count=Count("sedes", distinct=True),
        departamentos_count=Count("departamentos", distinct=True),
        empleados_count=Count("empleados", distinct=True),
    ).select_related("padre")

    resultado = []
    for empresa in qs:
        resultado.append({
            "id": empresa.id,
            "rif": empresa.rif,
            "razon_social": empresa.razon_social,
            "nombre_comercial": empresa.nombre_comercial or "",
            "tipo": empresa.tipo,
            "tipo_display": empresa.get_tipo_display(),
            "padre_id": empresa.padre_id,
            "padre_nombre": empresa.padre.razon_social if empresa.padre else "",
            "telefono": empresa.telefono or "",
            "email": empresa.email or "",
            "sitio_web": empresa.sitio_web or "",
            "direccion": empresa.direccion or "",
            "ciudad": empresa.ciudad or "",
            "estado": empresa.estado or "",
            "pais": empresa.pais,
            "moneda": empresa.moneda,
            "zona_horaria": empresa.zona_horaria,
            "sedes_count": empresa.sedes_count,
            "departamentos_count": empresa.departamentos_count,
            "empleados_count": empresa.empleados_count,
            "activa": empresa.activa,
            "created_at": empresa.created_at,
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  2. SEDES
# ═══════════════════════════════════════════════════════════

def reporte_sedes(empresa_id=None, tipo=None, activa=None, sede_id=None):
    """
    Reporte maestro de sedes.
    """
    qs = Sede.objects.select_related("empresa").all()

    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)
    if sede_id:
        qs = qs.filter(id=sede_id)
    if tipo:
        qs = qs.filter(tipo=tipo)
    if activa is not None:
        qs = qs.filter(activa=activa)

    qs = qs.annotate(
        empleados_count=Count("empleados", distinct=True),
    ).order_by("empresa__razon_social", "nombre")

    resultado = []
    for sede in qs:
        resultado.append({
            "id": sede.id,
            "codigo": sede.codigo,
            "nombre": sede.nombre,
            "empresa_id": sede.empresa_id,
            "empresa_nombre": sede.empresa.razon_social,
            "empresa_rif": sede.empresa.rif,
            "tipo": sede.tipo,
            "tipo_display": sede.get_tipo_display(),
            "es_principal": sede.es_principal,
            "direccion": sede.direccion or "",
            "ciudad": sede.ciudad or "",
            "estado": sede.estado or "",
            "pais": sede.pais,
            "codigo_postal": sede.codigo_postal or "",
            "telefono": sede.telefono or "",
            "email": sede.email or "",
            "empleados_count": sede.empleados_count,
            "activa": sede.activa,
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  3. DEPARTAMENTOS
# ═══════════════════════════════════════════════════════════

def reporte_departamentos(empresa_id=None, activo=None, padre_id=None,
                          departamento_id=None):
    """
    Reporte maestro de departamentos (con jerarquía).
    """
    qs = Departamento.objects.select_related(
        "empresa", "padre", "responsable"
    ).all()

    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)
    if departamento_id:
        qs = qs.filter(id=departamento_id)
    if padre_id:
        qs = qs.filter(padre_id=padre_id)
    if activo is not None:
        qs = qs.filter(activo=activo)

    qs = qs.annotate(
        empleados_count=Count("empleados", distinct=True),
        subdepartamentos_count=Count("subdepartamentos", distinct=True),
    ).order_by("empresa__razon_social", "nombre")

    resultado = []
    for depto in qs:
        resultado.append({
            "id": depto.id,
            "codigo": depto.codigo,
            "nombre": depto.nombre,
            "descripcion": depto.descripcion or "",
            "empresa_id": depto.empresa_id,
            "empresa_nombre": depto.empresa.razon_social if depto.empresa else "",
            "padre_id": depto.padre_id,
            "padre_nombre": depto.padre.nombre if depto.padre else "",
            "responsable_id": depto.responsable_id,
            "responsable_nombre": (
                depto.responsable.nombre_completo if depto.responsable else ""
            ),
            "presupuesto_anual": depto.presupuesto_anual,
            "empleados_count": depto.empleados_count,
            "subdepartamentos_count": depto.subdepartamentos_count,
            "activo": depto.activo,
            "created_at": depto.created_at,
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  4. CARGOS
# ═══════════════════════════════════════════════════════════

def reporte_cargos(activo=None, cargo_id=None):
    """
    Reporte maestro de cargos.
    """
    qs = Cargo.objects.all()

    if cargo_id:
        qs = qs.filter(id=cargo_id)
    if activo is not None:
        qs = qs.filter(activo=activo)

    qs = qs.annotate(
        empleados_count=Count("empleados", distinct=True),
    ).order_by("nombre")

    resultado = []
    for cargo in qs:
        # Calcular rango salarial y porcentaje
        rango = None
        rango_pct = None
        if cargo.salario_min and cargo.salario_max:
            rango = cargo.salario_max - cargo.salario_min
            if cargo.salario_min > 0:
                rango_pct = round((rango / cargo.salario_min) * 100, 2)

        resultado.append({
            "id": cargo.id,
            "codigo": cargo.codigo,
            "nombre": cargo.nombre,
            "descripcion": cargo.descripcion or "",
            "salario_min": cargo.salario_min,
            "salario_max": cargo.salario_max,
            "rango_salarial": rango,
            "rango_salarial_pct": rango_pct,
            "empleados_count": cargo.empleados_count,
            "activo": cargo.activo,
            "created_at": cargo.created_at,
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  5. EMPLEADOS / TRABAJADORES
# ═══════════════════════════════════════════════════════════

def reporte_empleados(
    empresa_id=None,
    estatus=None,
    departamento_id=None,
    cargo_id=None,
    sede_id=None,
    nacionalidad=None,
    tipo_contrato=None,
    fecha_ingreso_desde=None,
    fecha_ingreso_hasta=None,
    empleado_id=None,
):
    """
    Reporte maestro de empleados. Filtrable por múltiples criterios.
    """
    qs = Empleado.objects.select_related(
        "empresa", "sede", "departamento", "cargo", "jefe"
    ).all()

    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)
    if empleado_id:
        qs = qs.filter(id=empleado_id)
    if estatus:
        if isinstance(estatus, str):
            estatus = [estatus]
        qs = qs.filter(estatus__in=estatus)
    if departamento_id:
        qs = qs.filter(departamento_id=departamento_id)
    if cargo_id:
        qs = qs.filter(cargo_id=cargo_id)
    if sede_id:
        qs = qs.filter(sede_id=sede_id)
    if nacionalidad:
        qs = qs.filter(nacionalidad=nacionalidad)
    if tipo_contrato:
        qs = qs.filter(tipo_contrato=tipo_contrato)
    if fecha_ingreso_desde:
        qs = qs.filter(fecha_ingreso__gte=fecha_ingreso_desde)
    if fecha_ingreso_hasta:
        qs = qs.filter(fecha_ingreso__lte=fecha_ingreso_hasta)

    qs = qs.order_by("empresa__razon_social", "apellido_paterno", "nombre")

    resultado = []
    for emp in qs:
        resultado.append({
            # Identificación
            "id": emp.id,
            "numero_empleado": emp.numero_empleado,
            "nacionalidad": emp.nacionalidad,
            "cedula": emp.cedula,
            "cedula_completa": emp.cedula_completa,
            # Nombre
            "nombre": emp.nombre,
            "apellido_paterno": emp.apellido_paterno,
            "apellido_materno": emp.apellido_materno or "",
            "nombre_completo": emp.nombre_completo,
            # Datos personales
            "fecha_nacimiento": emp.fecha_nacimiento,
            "genero": emp.genero or "",
            "estado_civil": emp.estado_civil or "",
            # Contacto
            "email": emp.email,
            "telefono": emp.telefono or "",
            "telefono_habitacion": emp.telefono_habitacion or "",
            "direccion": emp.direccion or "",
            "ciudad": emp.ciudad or "",
            "estado": emp.estado or "",
            "pais": emp.pais,
            # Organización
            "empresa_id": emp.empresa_id,
            "empresa_nombre": emp.empresa.razon_social,
            "empresa_rif": emp.empresa.rif,
            "sede_id": emp.sede_id,
            "sede_nombre": emp.sede.nombre if emp.sede else "",
            "departamento_id": emp.departamento_id,
            "departamento_nombre": emp.departamento.nombre if emp.departamento else "",
            "cargo_id": emp.cargo_id,
            "cargo_nombre": emp.cargo.nombre if emp.cargo else "",
            "jefe_id": emp.jefe_id,
            "jefe_nombre": emp.jefe.nombre_completo if emp.jefe else "",
            # Datos laborales
            "fecha_ingreso": emp.fecha_ingreso,
            "fecha_egreso": emp.fecha_egreso,
            "tipo_contrato": emp.tipo_contrato or "",
            "tipo_jornada": emp.tipo_jornada or "",
            "estatus": emp.estatus,
            "estatus_display": emp.get_estatus_display(),
            "salario_base": emp.salario_base,
            "salario_diario": round(emp.salario_base / 30, 2) if emp.salario_base else None,
            "periodicidad_pago": emp.periodicidad_pago or "",
            # Bancarios
            "banco": emp.banco or "",
            "cuenta_bancaria": emp.cuenta_bancaria or "",
            "clabe": emp.clabe or "",
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  6. CONCEPTOS DE NÓMINA
# ═══════════════════════════════════════════════════════════

def reporte_conceptos(empresa_id=None, tipo=None, activo=None,
                      naturaleza=None, concepto_id=None):
    """
    Reporte maestro de conceptos de nómina.
    """
    qs = ConceptoNomina.objects.select_related("empresa").all()

    if concepto_id:
        qs = qs.filter(id=concepto_id)
    if empresa_id:
        # Incluir globales + los de la empresa
        qs = qs.filter(
            Q(empresa__isnull=True) | Q(empresa_id=empresa_id)
        )
    if tipo:
        qs = qs.filter(tipo=tipo)
    if activo is not None:
        qs = qs.filter(activo=activo)
    if naturaleza:
        qs = qs.filter(naturaleza=naturaleza)

    qs = qs.order_by("prioridad", "codigo")

    resultado = []
    for concepto in qs:
        resultado.append({
            "id": concepto.id,
            "empresa_id": concepto.empresa_id,
            "empresa_nombre": (
                concepto.empresa.razon_social if concepto.empresa else "Global"
            ),
            "codigo": concepto.codigo,
            "nombre": concepto.nombre,
            "descripcion": concepto.descripcion or "",
            "tipo": concepto.tipo,
            "tipo_display": concepto.get_tipo_display(),
            "naturaleza": concepto.naturaleza,
            "naturaleza_display": concepto.get_naturaleza_display(),
            "origen": concepto.origen,
            "origen_display": concepto.get_origen_display(),
            "es_fijo": concepto.es_fijo,
            "forma_parte_salario_normal": concepto.forma_parte_salario_normal,
            "afecta_isr": concepto.afecta_isr,
            "afecta_ivss": concepto.afecta_ivss,
            "afecta_rpe": concepto.afecta_rpe,
            "afecta_banavih": concepto.afecta_banavih,
            "formula": concepto.formula or "",
            "exencion_formula": concepto.exencion_formula or "",
            "prioridad": concepto.prioridad,
            "activo": concepto.activo,
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  7. PARÁMETROS DE NÓMINA
# ═══════════════════════════════════════════════════════════

def reporte_parametros(empresa_id=None, anio=None, activo=None):
    """
    Reporte maestro de parámetros de nómina.
    """
    qs = ParametroNomina.objects.select_related("empresa").all()

    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)
    if anio:
        qs = qs.filter(anio=anio)
    if activo is not None:
        qs = qs.filter(activo=activo)

    qs = qs.order_by("-anio", "empresa__razon_social")

    resultado = []
    for p in qs:
        resultado.append({
            "id": p.id,
            "empresa_id": p.empresa_id,
            "empresa_nombre": p.empresa.razon_social,
            "anio": p.anio,
            "salario_minimo": p.salario_minimo,
            "cestaticket_mensual_usd": p.cestaticket_mensual_usd,
            "unidad_tributaria": p.unidad_tributaria,
            "tasa_bcv_usd": p.tasa_bcv_usd,
            # IVSS
            "ivss_obrero_pct": p.ivss_obrero_pct,
            "ivss_patronal_pct": p.ivss_patronal_pct,
            "ivss_tope_salarios": p.ivss_tope_salarios,
            # RPE
            "rpe_obrero_pct": p.rpe_obrero_pct,
            "rpe_patronal_pct": p.rpe_patronal_pct,
            "rpe_tope_salarios": p.rpe_tope_salarios,
            # BANAVIH
            "banavih_obrero_pct": p.banavih_obrero_pct,
            "banavih_patronal_pct": p.banavih_patronal_pct,
            # INCES
            "inces_patronal_pct": p.inces_patronal_pct,
            # LOPCYMAT
            "lopcymat_categoria": p.lopcymat_categoria,
            "lopcymat_pct": p.lopcymat_pct,
            # Prestaciones y vacaciones
            "dias_prestaciones_trimestre": p.dias_prestaciones_trimestre,
            "dias_prestaciones_anio": p.dias_prestaciones_anio,
            "dias_adicionales_por_anio": p.dias_adicionales_por_anio,
            "dias_utilidades_min": p.dias_utilidades_min,
            "dias_utilidades_max": p.dias_utilidades_max,
            "dias_vacaciones_base": p.dias_vacaciones_base,
            "dias_vacaciones_max": p.dias_vacaciones_max,
            "dias_bono_vacacional_base": p.dias_bono_vacacional_base,
            "dias_bono_vacacional_max": p.dias_bono_vacacional_max,
            "dias_aguinaldo": p.dias_aguinaldo,
            "factor_integracion": p.factor_integracion,
            "activo": p.activo,
        })

    return resultado


# ═══════════════════════════════════════════════════════════
#  8. INCIDENCIAS DE NÓMINA
# ═══════════════════════════════════════════════════════════

def reporte_incidencias(
    empresa_id=None,
    tipo=None,
    estatus=None,
    fecha_desde=None,
    fecha_hasta=None,
    empleado_id=None,
    periodo_id=None,
):
    """
    Reporte maestro de incidencias de nómina.
    """
    qs = IncidenciaNomina.objects.select_related(
        "empleado", "periodo", "aprobado_por"
    ).all()

    if empresa_id:
        qs = qs.filter(empleado__empresa_id=empresa_id)
    if tipo:
        if isinstance(tipo, str):
            tipo = [tipo]
        qs = qs.filter(tipo__in=tipo)
    if estatus:
        if isinstance(estatus, str):
            estatus = [estatus]
        qs = qs.filter(estatus__in=estatus)
    if fecha_desde:
        qs = qs.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__lte=fecha_hasta)
    if empleado_id:
        qs = qs.filter(empleado_id=empleado_id)
    if periodo_id:
        qs = qs.filter(periodo_id=periodo_id)

    qs = qs.order_by("-fecha", "empleado__apellido_paterno")

    resultado = []
    for inc in qs:
        resultado.append({
            "id": inc.id,
            "empleado_id": inc.empleado_id,
            "empleado_numero": inc.empleado.numero_empleado,
            "empleado_nombre": inc.empleado.nombre_completo,
            "empleado_cedula": inc.empleado.cedula_completa,
            "empresa_nombre": inc.empleado.empresa.razon_social,
            "periodo_id": inc.periodo_id,
            "periodo_display": str(inc.periodo) if inc.periodo else "",
            "tipo": inc.tipo,
            "tipo_display": inc.get_tipo_display(),
            "fecha": inc.fecha,
            "cantidad": inc.cantidad,
            "unidad": inc.unidad,
            "motivo": inc.motivo or "",
            "estatus": inc.estatus,
            "estatus_display": inc.get_estatus_display(),
            "aprobado_por": inc.aprobado_por.username if inc.aprobado_por else "",
            "aprobado_at": inc.aprobado_at,
        })

    return resultado