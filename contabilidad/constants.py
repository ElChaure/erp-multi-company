# contabilidad/constants.py

# ═══════════════════════════════════════════════════════════
#  NATURALEZA DE LAS CUENTAS
# ═══════════════════════════════════════════════════════════

NATURALEZA_DEUDORA = "D"
NATURALEZA_ACREEDORA = "A"
NATURALEZA_CHOICES = [
    (NATURALEZA_DEUDORA, "Deudora"),
    (NATURALEZA_ACREEDORA, "Acreedora"),
]


# ═══════════════════════════════════════════════════════════
#  TIPOS DE CUENTA
# ═══════════════════════════════════════════════════════════

TIPO_ACTIVO = "ACTIVO"
TIPO_PASIVO = "PASIVO"
TIPO_PATRIMONIO = "PATRIMONIO"
TIPO_INGRESO = "INGRESO"
TIPO_GASTO = "GASTO"
TIPO_COSTO = "COSTO"

TIPO_CUENTA_CHOICES = [
    (TIPO_ACTIVO, "Activo"),
    (TIPO_PASIVO, "Pasivo"),
    (TIPO_PATRIMONIO, "Patrimonio"),
    (TIPO_INGRESO, "Ingreso"),
    (TIPO_GASTO, "Gasto"),
    (TIPO_COSTO, "Costo de Producción"),
]


# ═══════════════════════════════════════════════════════════
#  TIPOS DE CENTRO DE COSTO
# ═══════════════════════════════════════════════════════════

CC_PRODUCTIVO = "PRODUCTIVO"
CC_SERVICIO = "SERVICIO"
CC_ADMINISTRATIVO = "ADMINISTRATIVO"

CC_TIPO_CHOICES = [
    (CC_PRODUCTIVO, "Productivo (Línea/Máquina)"),
    (CC_SERVICIO, "Servicio (Apoyo)"),
    (CC_ADMINISTRATIVO, "Administrativo"),
]


# ═══════════════════════════════════════════════════════════
#  CÓDIGOS DE CUENTAS CONTABLES PREDETERMINADOS
# ═══════════════════════════════════════════════════════════
#
# Estos códigos son los que el seed estándar (seed_plan_cuentas)
# crea para cada empresa. Los servicios de integración los usan
# como fallback cuando no hay una configuración explícita.
# ═══════════════════════════════════════════════════════════

# ── Nómina ────────────────────────────────────────────────
CUENTA_SUELDOS_POR_PAGAR = "210102"

# ── Costos de producción ──────────────────────────────────
CUENTA_INVENTARIO_PT = "110303"
CUENTA_COSTO_MP = "5101"
CUENTA_COSTO_MOD = "5102"
CUENTA_COSTO_CIF = "5103"

# DEPRECATED: alias de CUENTA_COSTO_MOD.
CUENTA_COSTO_PRODUCCION = CUENTA_COSTO_MOD

# ── Nómina: prefijos de búsqueda alternativos ────────────
NOMBRE_SUELDOS_POR_PAGAR = ("sueldo", "pagar")


# ═══════════════════════════════════════════════════════════
#  ESTADOS DE COMPROBANTE / ASIENTO
# ═══════════════════════════════════════════════════════════

ESTADO_CONTABILIZADO = "contabilizado"
ESTADO_ANULADO = "anulado"


# ═══════════════════════════════════════════════════════════
#  ORÍGENES DE MÓDULO (para Asiento.origen_modulo)
# ═══════════════════════════════════════════════════════════

ORIGEN_NOMINA = "nomina"
ORIGEN_COSTOS = "costos"
ORIGEN_ACTIVOS = "activos"
ORIGEN_COMPROBANTE_BORRADOR = "comprobante_borrador"


# ═══════════════════════════════════════════════════════════
#  CONFIGURACIÓN DE REPARTO DE CIF  (Sprint 2.5)
# ═══════════════════════════════════════════════════════════
#
# Driver = base de asignación que se usa para repartir los CIF
# entre los centros de costo productivos.
#
# El "pivot" es el CC de referencia (coeficiente = 1). El resto
# de los CC se calculan como driver_cc / driver_pivot.
# ═══════════════════════════════════════════════════════════

# ── Tipos de driver ──────────────────────────────────────
DRIVER_AREA = "AREA"
DRIVER_HORAS_MAQUINA = "HORAS_MAQUINA"
DRIVER_HORAS_HOMBRE = "HORAS_HOMBRE"
DRIVER_UNIDADES = "UNIDADES"
DRIVER_COSTO_DIRECTO = "COSTO_DIRECTO"
DRIVER_PERSONALIZADO = "PERSONALIZADO"

DRIVER_CIF_CHOICES = [
    (DRIVER_AREA, "Área física (cm²)"),
    (DRIVER_HORAS_MAQUINA, "Horas-máquina"),
    (DRIVER_HORAS_HOMBRE, "Horas-hombre"),
    (DRIVER_UNIDADES, "Unidades producidas"),
    (DRIVER_COSTO_DIRECTO, "Costo directo (MP + MOD)"),
    (DRIVER_PERSONALIZADO, "Personalizado (manual)"),
]

# ── Métodos de cálculo ───────────────────────────────────
METODO_PROPORCIONAL = "PROPORCIONAL"
METODO_DIRECTO = "DIRECTO"

METODO_CIF_CHOICES = [
    (METODO_PROPORCIONAL, "Proporcional (coef. = driver / base_pivot)"),
    (METODO_DIRECTO, "Directo (coef. = 1 para todos los CC)"),
]

# ── Etiquetas legibles (para reportes) ───────────────────
DRIVER_LABELS = {
    DRIVER_AREA: "Área (cm²)",
    DRIVER_HORAS_MAQUINA: "Horas-máquina",
    DRIVER_HORAS_HOMBRE: "Horas-hombre",
    DRIVER_UNIDADES: "Unidades",
    DRIVER_COSTO_DIRECTO: "Costo directo",
    DRIVER_PERSONALIZADO: "Manual",
}