"""
Servicios del módulo de documentos:
 - Generación de números de control
 - Registro de documentos emitidos
 - Recuperación de datos para los PDFs
"""

from decimal import Decimal

from django.db import transaction
from django.db.models import Max, Sum
from django.utils import timezone

from rrhh.models import NominaEmpleado, NominaDetalle
from .models import DocumentoEmitido


# ═══════════════════════════════════════════════════════════
# CORRELATIVOS
# ═══════════════════════════════════════════════════════════

PREFIJOS = {
    "constancia_trabajo": "CT",
    "arc": "ARC",
}


def generar_numero_control(tipo, anio):
    """
    Genera el próximo número de control para un tipo y año.
    Formato: {PREFIJO}-{AÑO}-{SECUENCIAL:04d}
    Ejemplo: CT-2026-0001, ARC-2026-0042
    """
    prefijo = PREFIJOS.get(tipo, "DOC")
    patron = f"{prefijo}-{anio}-"

    ultimo = (
        DocumentoEmitido.objects
        .filter(tipo=tipo, anio=anio)
        .filter(numero_control__startswith=patron)
        .aggregate(max_num=Max("numero_control"))["max_num"]
    )

    if ultimo:
        try:
            secuencial = int(ultimo.split("-")[-1]) + 1
        except (ValueError, IndexError):
            secuencial = 1
    else:
        secuencial = 1

    return f"{prefijo}-{anio}-{secuencial:04d}"


# ═══════════════════════════════════════════════════════════
# REGISTRO
# ═══════════════════════════════════════════════════════════

@transaction.atomic
def registrar_documento(tipo, empleado, usuario, parametros):
    """
    Registra un documento emitido, generando su número de control.

    Args:
        tipo: "constancia_trabajo" o "arc"
        empleado: instancia de Empleado
        usuario: User que emite
        parametros: dict con los parámetros de emisión

    Returns:
        DocumentoEmitido instancia
    """
    anio = timezone.now().year
    numero_control = generar_numero_control(tipo, anio)

    documento = DocumentoEmitido.objects.create(
        tipo=tipo,
        numero_control=numero_control,
        anio=anio,
        empleado=empleado,
        empresa=empleado.empresa,
        emitido_por=usuario,
        parametros=parametros,
    )
    return documento


def registrar_descarga(documento):
    """Incrementa el contador de descargas."""
    documento.descargas += 1
    documento.ultima_descarga = timezone.now()
    documento.save(update_fields=["descargas", "ultima_descarga"])


# ═══════════════════════════════════════════════════════════
# DATOS PARA EL ARC
# ═══════════════════════════════════════════════════════════

# Códigos de conceptos que necesitamos identificar
CODIGO_ISLR = "060"
CODIGO_SSO = "050"       # IVSS obrero
CODIGO_SPF = "051"       # Paro forzoso obrero
CODIGO_LPH = "052"       # BANAVIH obrero


def datos_arc_por_anio(empleado, anio):
    """
    Recopila los datos mensuales de un empleado para el ARC.

    Args:
        empleado: instancia de Empleado
        anio: año fiscal (int)

    Returns:
        dict con:
            - filas: lista de 12 dicts (uno por mes)
            - total_devengado: Decimal
            - total_retenido: Decimal
            - total_sso: Decimal
            - total_spf: Decimal
            - total_lph: Decimal
            - total_otros: Decimal
    """
    from rrhh.utils.fechas import mes_en_letras

    filas = []
    acumulado_dev = Decimal("0")
    acumulado_ret = Decimal("0")

    for mes in range(1, 13):
        # Buscar la nómina del mes
        nominas_mes = NominaEmpleado.objects.filter(
            empleado=empleado,
            periodo__anio=anio,
            periodo__fecha_fin__month=mes,
            periodo__estatus__in=["aprobado", "cerrado"],
        )

        devengado_mes = Decimal("0")
        retenido_mes = Decimal("0")

        for nomina in nominas_mes:
            # Devengado = total percepciones (incluye cestaticket)
            devengado_mes += nomina.total_percepciones or Decimal("0")
            # Retenido ISLR
            retenido_mes += nomina.islr_calculado or Decimal("0")

        acumulado_dev += devengado_mes
        acumulado_ret += retenido_mes

        # % ISLR efectivo del mes
        pct_islr = Decimal("0")
        if devengado_mes > 0:
            pct_islr = (retenido_mes / devengado_mes * 100).quantize(Decimal("0.01"))

        filas.append({
            "mes": mes,
            "mes_nombre": mes_en_letras(mes, mayusculas=False).upper(),
            "devengado": devengado_mes,
            "pct_islr": pct_islr,
            "retencion": retenido_mes,
            "acumulado_devengado": acumulado_dev,
            "acumulado_retencion": acumulado_ret,
        })

    # Totales por concepto (SSO, SPF, LPH)
    totales = (
        NominaDetalle.objects
        .filter(
            nomina__empleado=empleado,
            nomina__periodo__anio=anio,
            nomina__periodo__estatus__in=["aprobado", "cerrado"],
            codigo_concepto__in=[CODIGO_SSO, CODIGO_SPF, CODIGO_LPH],
        )
        .values("codigo_concepto")
        .annotate(total=Sum("importe"))
    )

    totales_dict = {item["codigo_concepto"]: item["total"] for item in totales}

    return {
        "filas": filas,
        "total_devengado": acumulado_dev,
        "total_retenido": acumulado_ret,
        "total_sso": totales_dict.get(CODIGO_SSO, Decimal("0")),
        "total_spf": totales_dict.get(CODIGO_SPF, Decimal("0")),
        "total_lph": totales_dict.get(CODIGO_LPH, Decimal("0")),
        "total_otros": Decimal("0"),  # reservado para futuros conceptos
    }