"""
Generador de Constancia de Trabajo en PDF.

Uso:
    from rrhh.documentos.generadores.constancia_trabajo import generar_constancia_pdf
    pdf_bytes = generar_constancia_pdf(documento)
"""

import base64
from datetime import date as date_cls
from io import BytesIO

from django.template.loader import render_to_string
from xhtml2pdf import pisa

from rrhh.utils.fechas import fecha_larga


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def _cargar_imagen_base64(imagen_field):
    """Carga una ImageField como base64 (sin prefijo data:)."""
    if not imagen_field:
        return None
    try:
        with imagen_field.open("rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def _parsear_fecha(valor):
    """Convierte string ISO o date a date. Default: hoy."""
    if isinstance(valor, date_cls):
        return valor
    if isinstance(valor, str):
        try:
            return date_cls.fromisoformat(valor)
        except (ValueError, TypeError):
            pass
    return date_cls.today()


def _preparar_contexto(documento):
    """Construye el contexto para el template."""
    empleado = documento.empleado
    empresa = documento.empresa
    params = documento.parametros or {}

    # Parsear fecha de emisión (viene como ISO string)
    fecha_emision = _parsear_fecha(params.get("fecha_emision"))

    # Datos básicos
    context = {
        "documento": documento,
        "empleado": empleado,
        "empresa": empresa,
        "numero_control": documento.numero_control,
        # Logo y firma
        "logo_base64": _cargar_imagen_base64(empresa.logo),
        "firma_base64": _cargar_imagen_base64(getattr(empresa, "firma_agente_retencion", None)),
        "sello_base64": _cargar_imagen_base64(getattr(empresa, "sello_empresa", None)),
        # Datos del emisor
        "nombre_firmante": getattr(empresa, "nombre_agente_retencion", "") or "",
        "cargo_firmante": getattr(empresa, "cargo_agente_retencion", "") or "",
        # Parámetros personalizables
        "con_salario": params.get("con_salario", False),
        "destinatario": params.get("destinatario", "A quien pueda interesar"),
        "ciudad": params.get("ciudad", empresa.ciudad or ""),
        "fecha_emision": fecha_emision,  # ← date
    }

    # Fecha larga
    context["fecha_emision_larga"] = fecha_larga(fecha_emision)

    # Salario (solo si aplica)
    if context["con_salario"]:
        context["salario_monto"] = empleado.salario_base
        context["salario_periodicidad"] = "mensual"

    return context


# ═══════════════════════════════════════════════════════════
# GENERADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════

def generar_constancia_pdf(documento):
    """
    Genera el PDF de la Constancia de Trabajo.

    Args:
        documento: instancia de DocumentoEmitido con tipo="constancia_trabajo"

    Returns:
        bytes del PDF
    """
    context = _preparar_contexto(documento)

    html_string = render_to_string(
        "documentos/constancia_trabajo.html",
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