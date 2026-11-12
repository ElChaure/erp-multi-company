"""
Generador de Planilla ARC en PDF.

Uso:
    from rrhh.documentos.generadores.planilla_arc import generar_arc_pdf
    pdf_bytes = generar_arc_pdf(documento)
"""

import base64
from io import BytesIO

from django.template.loader import render_to_string
from xhtml2pdf import pisa

from rrhh.documentos.services import datos_arc_por_anio
from rrhh.utils.numeros import numero_a_letras, formatear_numero


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def _cargar_imagen_base64(imagen_field):
    """Carga una ImageField como base64."""
    if not imagen_field:
        return None
    try:
        with imagen_field.open("rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def _preparar_contexto(documento):
    """Construye el contexto para el template."""
    empleado = documento.empleado
    empresa = documento.empresa
    params = documento.parametros or {}
    anio_fiscal = params.get("anio_fiscal", documento.anio)

    # Obtener datos del año
    datos = datos_arc_por_anio(empleado, anio_fiscal)

    # Monto en letras (total devengado)
    monto_en_letras = numero_a_letras(float(datos["total_devengado"]))

    context = {
        "documento": documento,
        "empleado": empleado,
        "empresa": empresa,
        "numero_control": documento.numero_control,
        # Logo, firma y sello
        "logo_base64": _cargar_imagen_base64(empresa.logo),
        "firma_base64": _cargar_imagen_base64(getattr(empresa, "firma_agente_retencion", None)),
        "sello_base64": _cargar_imagen_base64(getattr(empresa, "sello_empresa", None)),
        # Datos del emisor
        "nombre_firmante": getattr(empresa, "nombre_agente_retencion", "") or "",
        "cargo_firmante": getattr(empresa, "cargo_agente_retencion", "") or "",
        # Datos fiscales
        "anio_fiscal": anio_fiscal,
        "periodo_inicio": f"01/01/{anio_fiscal}",
        "periodo_fin": f"31/12/{anio_fiscal}",
        # Datos de la tabla
        "filas": datos["filas"],
        "total_devengado": datos["total_devengado"],
        "total_retenido": datos["total_retenido"],
        "monto_en_letras": monto_en_letras,
        "total_sso": datos["total_sso"],
        "total_spf": datos["total_spf"],
        "total_lph": datos["total_lph"],
        "total_otros": datos["total_otros"],
        # Filtro por cargo (opcional)
        "cargo_filtro": params.get("cargo_filtro"),
    }

    return context


# ═══════════════════════════════════════════════════════════
# GENERADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════

def generar_arc_pdf(documento):
    """
    Genera el PDF de la Planilla ARC.

    Args:
        documento: instancia de DocumentoEmitido con tipo="arc"

    Returns:
        bytes del PDF
    """
    context = _preparar_contexto(documento)

    html_string = render_to_string(
        "documentos/planilla_arc.html",
        context,
    )

    buffer = BytesIO()
    pisa_status = pisa.CreatePDF(
        src=html_string,
        dest=buffer,
        encoding="UTF-8",
    )

    if pisa_status.err:
        raise RuntimeError(
            f"Error al generar PDF con xhtml2pdf: {pisa_status.err}"
        )

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes