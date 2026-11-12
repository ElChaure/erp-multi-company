"""
Definición de columnas para cada reporte.

Cada columna es un dict con:
    - key: campo del dato
    - label: encabezado
    - width: ancho en px
    - format: 'currency', 'number', 'integer', 'percent', 'date', 'datetime'
    - align: 'left', 'center', 'right'
    - total: True si se debe sumar al final
"""


# ═══════════════════════════════════════════════════════════
#  MAESTROS
# ═══════════════════════════════════════════════════════════

COLUMNAS_EMPRESAS = [
    {"key": "rif", "label": "RIF", "width": 90},
    {"key": "razon_social", "label": "Razón social", "width": 180},
    {"key": "nombre_comercial", "label": "Nombre comercial", "width": 150},
    {"key": "tipo_display", "label": "Tipo", "width": 90, "align": "center"},
    {"key": "padre_nombre", "label": "Empresa matriz", "width": 150},
    {"key": "ciudad", "label": "Ciudad", "width": 100},
    {"key": "pais", "label": "País", "width": 50, "align": "center"},
    {"key": "moneda", "label": "Moneda", "width": 60, "align": "center"},
    {"key": "sedes_count", "label": "Sedes", "width": 60, "align": "center", "format": "integer"},
    {"key": "empleados_count", "label": "Empleados", "width": 70, "align": "center", "format": "integer"},
    {"key": "activa", "label": "Activa", "width": 60, "align": "center"},
]

COLUMNAS_SEDES = [
    {"key": "codigo", "label": "Código", "width": 70},
    {"key": "nombre", "label": "Nombre", "width": 150},
    {"key": "empresa_nombre", "label": "Empresa", "width": 150},
    {"key": "tipo_display", "label": "Tipo", "width": 80, "align": "center"},
    {"key": "ciudad", "label": "Ciudad", "width": 100},
    {"key": "estado", "label": "Estado", "width": 100},
    {"key": "telefono", "label": "Teléfono", "width": 100},
    {"key": "empleados_count", "label": "Empleados", "width": 70, "align": "center", "format": "integer"},
    {"key": "activa", "label": "Activa", "width": 60, "align": "center"},
]

COLUMNAS_DEPARTAMENTOS = [
    {"key": "codigo", "label": "Código", "width": 70},
    {"key": "nombre", "label": "Nombre", "width": 150},
    {"key": "empresa_nombre", "label": "Empresa", "width": 140},
    {"key": "padre_nombre", "label": "Depto padre", "width": 120},
    {"key": "responsable_nombre", "label": "Responsable", "width": 130},
    {"key": "presupuesto_anual", "label": "Presupuesto", "width": 100, "format": "currency"},
    {"key": "empleados_count", "label": "Empleados", "width": 70, "align": "center", "format": "integer"},
    {"key": "subdepartamentos_count", "label": "Sub-deptos", "width": 70, "align": "center", "format": "integer"},
    {"key": "activo", "label": "Activo", "width": 60, "align": "center"},
]

COLUMNAS_CARGOS = [
    {"key": "codigo", "label": "Código", "width": 80},
    {"key": "nombre", "label": "Nombre", "width": 180},
    {"key": "salario_min", "label": "Salario mín.", "width": 100, "format": "currency"},
    {"key": "salario_max", "label": "Salario máx.", "width": 100, "format": "currency"},
    {"key": "rango_salarial", "label": "Rango", "width": 100, "format": "currency"},
    {"key": "rango_salarial_pct", "label": "Rango %", "width": 70, "align": "center"},
    {"key": "empleados_count", "label": "Empleados", "width": 70, "align": "center", "format": "integer"},
    {"key": "activo", "label": "Activo", "width": 60, "align": "center"},
]

COLUMNAS_EMPLEADOS = [
    {"key": "numero_empleado", "label": "N°", "width": 70},
    {"key": "cedula_completa", "label": "Cédula", "width": 90},
    {"key": "nombre_completo", "label": "Nombre completo", "width": 180},
    {"key": "empresa_nombre", "label": "Empresa", "width": 140},
    {"key": "sede_nombre", "label": "Sede", "width": 110},
    {"key": "departamento_nombre", "label": "Departamento", "width": 120},
    {"key": "cargo_nombre", "label": "Cargo", "width": 130},
    {"key": "fecha_ingreso", "label": "Ingreso", "width": 80, "format": "date"},
    {"key": "salario_base", "label": "Salario", "width": 100, "format": "currency", "total": True},
    {"key": "estatus", "label": "Estatus", "width": 70, "align": "center"},
]

COLUMNAS_CONCEPTOS = [
    {"key": "codigo", "label": "Código", "width": 70},
    {"key": "nombre", "label": "Nombre", "width": 170},
    {"key": "tipo_display", "label": "Tipo", "width": 100, "align": "center"},
    {"key": "naturaleza_display", "label": "Naturaleza", "width": 110, "align": "center"},
    {"key": "es_fijo", "label": "Fijo", "width": 50, "align": "center"},
    {"key": "afecta_isr", "label": "ISLR", "width": 50, "align": "center"},
    {"key": "afecta_ivss", "label": "IVSS", "width": 50, "align": "center"},
    {"key": "prioridad", "label": "Prioridad", "width": 70, "align": "center", "format": "integer"},
    {"key": "activo", "label": "Activo", "width": 60, "align": "center"},
]

COLUMNAS_PARAMETROS = [
    {"key": "empresa_nombre", "label": "Empresa", "width": 150},
    {"key": "anio", "label": "Año", "width": 50, "align": "center"},
    {"key": "salario_minimo", "label": "Salario mínimo", "width": 100, "format": "currency"},
    {"key": "unidad_tributaria", "label": "UT", "width": 80, "format": "currency"},
    {"key": "tasa_bcv_usd", "label": "Tasa BCV", "width": 80, "format": "number"},
    {"key": "cestaticket_mensual_usd", "label": "Cestaticket USD", "width": 100, "format": "number"},
    {"key": "ivss_obrero_pct", "label": "IVSS obrero %", "width": 80, "align": "center"},
    {"key": "ivss_patronal_pct", "label": "IVSS patronal %", "width": 80, "align": "center"},
    {"key": "rpe_obrero_pct", "label": "RPE obrero %", "width": 80, "align": "center"},
    {"key": "lopcymat_categoria", "label": "LOPCYMAT", "width": 70, "align": "center"},
    {"key": "activo", "label": "Activo", "width": 60, "align": "center"},
]

COLUMNAS_INCIDENCIAS = [
    {"key": "empleado_numero", "label": "N°", "width": 70},
    {"key": "empleado_nombre", "label": "Empleado", "width": 180},
    {"key": "empresa_nombre", "label": "Empresa", "width": 140},
    {"key": "tipo_display", "label": "Tipo", "width": 120, "align": "center"},
    {"key": "fecha", "label": "Fecha", "width": 80, "format": "date"},
    {"key": "cantidad", "label": "Cantidad", "width": 70, "align": "right", "format": "number", "total": True},
    {"key": "unidad", "label": "Unidad", "width": 60, "align": "center"},
    {"key": "estatus_display", "label": "Estatus", "width": 90, "align": "center"},
]

COLUMNAS_COSTO_DEPARTAMENTO = [
    {"key": "departamento_nombre", "label": "Departamento", "width": 180},
    {"key": "empleados_unicos", "label": "Empleados", "width": 80, "align": "center", "format": "integer"},
    {"key": "nominas_count", "label": "Nóminas", "width": 70, "align": "center", "format": "integer"},
    {"key": "total_percepciones", "label": "Percepciones", "width": 120, "format": "currency", "total": True},
    {"key": "total_deducciones", "label": "Deducciones", "width": 120, "format": "currency", "total": True},
    {"key": "total_neto", "label": "Neto", "width": 120, "format": "currency", "total": True},
    {"key": "total_aportes_patronales", "label": "Aportes patronales", "width": 130, "format": "currency", "total": True},
    {"key": "costo_total_empresa", "label": "Costo empresa", "width": 130, "format": "currency", "total": True},
]

COLUMNAS_COSTO_CARGO = [
    {"key": "cargo_codigo", "label": "Código", "width": 80},
    {"key": "cargo_nombre", "label": "Cargo", "width": 180},
    {"key": "empleados_unicos", "label": "Empleados", "width": 80, "align": "center", "format": "integer"},
    {"key": "total_percepciones", "label": "Percepciones", "width": 120, "format": "currency", "total": True},
    {"key": "total_deducciones", "label": "Deducciones", "width": 120, "format": "currency", "total": True},
    {"key": "total_neto", "label": "Neto", "width": 120, "format": "currency", "total": True},
    {"key": "costo_total_empresa", "label": "Costo empresa", "width": 130, "format": "currency", "total": True},
]

COLUMNAS_RETENCIONES_ISLR = [
    {"key": "numero_empleado", "label": "N°", "width": 70},
    {"key": "cedula", "label": "Cédula", "width": 90},
    {"key": "nombre", "label": "Empleado", "width": 180},
    {"key": "cargo", "label": "Cargo", "width": 140},
    {"key": "nominas_count", "label": "Nóminas", "width": 70, "align": "center", "format": "integer"},
    {"key": "base_islr", "label": "Base ISLR", "width": 120, "format": "currency", "total": True},
    {"key": "islr_retenido", "label": "ISLR retenido", "width": 120, "format": "currency", "total": True},
]

COLUMNAS_APORTES_ENTES = [
    {"key": "codigo_concepto", "label": "Código", "width": 80},
    {"key": "nombre_concepto", "label": "Concepto", "width": 200},
    {"key": "empleados_count", "label": "Empleados", "width": 80, "align": "center", "format": "integer"},
    {"key": "total", "label": "Total", "width": 120, "format": "currency", "total": True},
]

COLUMNAS_RESUMEN_PERIODOS = [
    {"key": "tipo_display", "label": "Tipo", "width": 90},
    {"key": "numero_periodo", "label": "N°", "width": 50, "align": "center", "format": "integer"},
    {"key": "anio", "label": "Año", "width": 50, "align": "center"},
    {"key": "fecha_inicio", "label": "Inicio", "width": 80, "format": "date"},
    {"key": "fecha_fin", "label": "Fin", "width": 80, "format": "date"},
    {"key": "fecha_pago", "label": "Pago", "width": 80, "format": "date"},
    {"key": "estatus_display", "label": "Estatus", "width": 90, "align": "center"},
    {"key": "empleados_procesados", "label": "Empleados", "width": 70, "align": "center", "format": "integer"},
    {"key": "total_percepciones", "label": "Percepciones", "width": 120, "format": "currency", "total": True},
    {"key": "total_deducciones", "label": "Deducciones", "width": 120, "format": "currency", "total": True},
    {"key": "total_neto", "label": "Neto", "width": 120, "format": "currency", "total": True},
    {"key": "total_costo_empresa", "label": "Costo empresa", "width": 130, "format": "currency", "total": True},
]

# ═══════════════════════════════════════════════════════════
#  AUSENCIAS
# ═══════════════════════════════════════════════════════════

COLUMNAS_SALDOS_VACACIONES = [
    {"key": "numero_empleado", "label": "N°", "width": 70},
    {"key": "cedula", "label": "Cédula", "width": 90},
    {"key": "nombre", "label": "Empleado", "width": 180},
    {"key": "departamento", "label": "Departamento", "width": 130},
    {"key": "cargo", "label": "Cargo", "width": 130},
    {"key": "anio", "label": "Año", "width": 50, "align": "center"},
    {"key": "dias_derecho", "label": "Derecho", "width": 70, "align": "right", "format": "number"},
    {"key": "dias_tomados", "label": "Tomados", "width": 70, "align": "right", "format": "number"},
    {"key": "dias_pagados", "label": "Pagados", "width": 70, "align": "right", "format": "number"},
    {"key": "dias_pendientes", "label": "Pendientes", "width": 80, "align": "right", "format": "number"},
    {"key": "fecha_limite_uso", "label": "Vence", "width": 80, "format": "date"},
]

COLUMNAS_SOLICITUDES_AUSENCIA = [
    {"key": "id", "label": "ID", "width": 50, "align": "center"},
    {"key": "numero_empleado", "label": "N°", "width": 70},
    {"key": "nombre", "label": "Empleado", "width": 180},
    {"key": "departamento", "label": "Departamento", "width": 120},
    {"key": "tipo", "label": "Tipo", "width": 130},
    {"key": "fecha_inicio", "label": "Desde", "width": 80, "format": "date"},
    {"key": "fecha_fin", "label": "Hasta", "width": 80, "format": "date"},
    {"key": "dias_solicitados", "label": "Días", "width": 60, "align": "right", "format": "number", "total": True},
    {"key": "estatus_display", "label": "Estatus", "width": 90, "align": "center"},
    {"key": "aprobador", "label": "Aprobador", "width": 150},
]

COLUMNAS_PROXIMAS_AUSENCIAS = [
    {"key": "numero_empleado", "label": "N°", "width": 70},
    {"key": "nombre", "label": "Empleado", "width": 180},
    {"key": "departamento", "label": "Departamento", "width": 130},
    {"key": "tipo", "label": "Tipo", "width": 130},
    {"key": "fecha_inicio", "label": "Inicio", "width": 80, "format": "date"},
    {"key": "fecha_fin", "label": "Fin", "width": 80, "format": "date"},
    {"key": "dias_solicitados", "label": "Días", "width": 60, "align": "right", "format": "number", "total": True},
    {"key": "dias_hasta_inicio", "label": "Días para iniciar", "width": 100, "align": "center", "format": "integer"},
]

COLUMNAS_AUSENCIAS_DEPARTAMENTO = [
    {"key": "departamento_nombre", "label": "Departamento", "width": 200},
    {"key": "empleados_unicos", "label": "Empleados", "width": 80, "align": "center", "format": "integer"},
    {"key": "solicitudes_count", "label": "Solicitudes", "width": 80, "align": "center", "format": "integer"},
    {"key": "dias_totales", "label": "Días totales", "width": 100, "align": "right", "format": "number", "total": True},
    {"key": "dias_promedio", "label": "Promedio", "width": 90, "align": "right", "format": "number"},
]

COLUMNAS_AUSENCIAS_TIPO = [
    {"key": "tipo_nombre", "label": "Tipo", "width": 200},
    {"key": "categoria", "label": "Categoría", "width": 120, "align": "center"},
    {"key": "empleados_unicos", "label": "Empleados", "width": 80, "align": "center", "format": "integer"},
    {"key": "solicitudes_count", "label": "Solicitudes", "width": 80, "align": "center", "format": "integer"},
    {"key": "dias_totales", "label": "Días totales", "width": 100, "align": "right", "format": "number", "total": True},
    {"key": "dias_promedio", "label": "Promedio", "width": 90, "align": "right", "format": "number"},
]

# ═══════════════════════════════════════════════════════════
#  AUDITORÍA
# ═══════════════════════════════════════════════════════════

COLUMNAS_AUDITORIA = [
    {"key": "fecha", "label": "Fecha", "width": 120, "format": "datetime"},
    {"key": "usuario", "label": "Usuario", "width": 100},
    {"key": "usuario_nombre", "label": "Nombre", "width": 150},
    {"key": "accion_display", "label": "Acción", "width": 100, "align": "center"},
    {"key": "tabla", "label": "Tabla", "width": 130},
    {"key": "registro_id", "label": "ID", "width": 60, "align": "center", "format": "integer"},
    {"key": "registro_repr", "label": "Registro", "width": 180},
    {"key": "descripcion", "label": "Descripción", "width": 250},
    {"key": "ip", "label": "IP", "width": 110},
]

COLUMNAS_AUDITORIA_USUARIO = [
    {"key": "usuario", "label": "Usuario", "width": 100},
    {"key": "nombre_completo", "label": "Nombre completo", "width": 180},
    {"key": "total_acciones", "label": "Total", "width": 70, "align": "center", "format": "integer", "total": True},
    {"key": "creaciones", "label": "Creaciones", "width": 80, "align": "center", "format": "integer", "total": True},
    {"key": "actualizaciones", "label": "Actualizaciones", "width": 100, "align": "center", "format": "integer", "total": True},
    {"key": "eliminaciones", "label": "Eliminaciones", "width": 90, "align": "center", "format": "integer", "total": True},
    {"key": "logins", "label": "Logins", "width": 70, "align": "center", "format": "integer", "total": True},
    {"key": "ultima_actividad", "label": "Última actividad", "width": 130, "format": "datetime"},
]

COLUMNAS_AUDITORIA_TABLA = [
    {"key": "tabla", "label": "Tabla", "width": 180},
    {"key": "total", "label": "Total", "width": 70, "align": "center", "format": "integer", "total": True},
    {"key": "creaciones", "label": "Creaciones", "width": 90, "align": "center", "format": "integer", "total": True},
    {"key": "actualizaciones", "label": "Actualizaciones", "width": 110, "align": "center", "format": "integer", "total": True},
    {"key": "eliminaciones", "label": "Eliminaciones", "width": 100, "align": "center", "format": "integer", "total": True},
]

COLUMNAS_AUDITORIA_ACCION = [
    {"key": "accion_display", "label": "Acción", "width": 150},
    {"key": "accion", "label": "Código", "width": 100, "align": "center"},
    {"key": "total", "label": "Total", "width": 90, "align": "center", "format": "integer", "total": True},
]

COLUMNAS_AUDITORIA_DIARIA = [
    {"key": "dia", "label": "Día", "width": 100, "format": "date"},
    {"key": "total", "label": "Acciones", "width": 90, "align": "center", "format": "integer", "total": True},
]
