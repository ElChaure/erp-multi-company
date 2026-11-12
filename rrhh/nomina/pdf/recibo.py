"""
Generador de recibos de pago en PDF usando xhtml2pdf.

Uso:
    from rrhh.nomina.pdf.recibo import generar_recibo_pdf
    pdf_bytes = generar_recibo_pdf(nomina)
"""
import base64
from io import BytesIO

from django.template.loader import render_to_string

# Usar xhtml2pdf
from xhtml2pdf import pisa

# Número a letras (movido a rrhh.utils.numeros)
from rrhh.utils.numeros import numero_a_letras


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _cargar_logo_base64(empresa):
    """
    Carga el logo de la empresa y lo convierte a base64.

    Returns:
        String base64 sin el prefijo data:image, o None si no hay logo.
    """
    if not empresa.logo:
        return None

    try:
        with empresa.logo.open("rb") as f:
            contenido = f.read()
        return base64.b64encode(contenido).decode("utf-8")
    except Exception:
        return None


def _separar_detalles(nomina):
    """Separa los detalles en percepciones, deducciones y aportes."""
    percepciones = []
    deducciones = []
    aportes = []

    for detalle in nomina.detalles.all().order_by("orden"):
        item = {
            "codigo_concepto": detalle.codigo_concepto,
            "nombre_concepto": detalle.nombre_concepto,
            "cantidad": detalle.cantidad,
            "base_calculo": detalle.base_calculo,
            "importe": detalle.importe,
        }
        if detalle.tipo == "percepcion":
            percepciones.append(item)
        elif detalle.tipo == "deduccion":
            deducciones.append(item)
        elif detalle.tipo == "aporte_patronal":
            aportes.append(item)

    return percepciones, deducciones, aportes


def generar_recibo_pdf(nomina):
    """
    Genera el PDF del recibo de pago.

    Args:
        nomina: instancia de NominaEmpleado

    Returns:
        bytes del PDF
    """
    empleado = nomina.empleado
    periodo = nomina.periodo
    empresa = empleado.empresa

    # Cargar logo
    logo_base64 = _cargar_logo_base64(empresa)

    # Inicial de la empresa para el fallback
    nombre_empresa = empresa.nombre_comercial or empresa.razon_social
    empresa_initial = nombre_empresa[0].upper() if nombre_empresa else "?"

    # Separar detalles
    percepciones, deducciones, aportes = _separar_detalles(nomina)

    # Calcular neto en letras
    neto_en_letras = numero_a_letras(float(nomina.neto_pagar))

    # Contexto del template
    context = {
        "nomina": nomina,
        "empleado": empleado,
        "periodo": periodo,
        "empresa": empresa,
        "logo_base64": logo_base64,
        "empresa_initial": empresa_initial,
        "percepciones": percepciones,
        "deducciones": deducciones,
        "aportes": aportes,
        "neto_en_letras": neto_en_letras,
    }

    # Renderizar HTML
    html_string = render_to_string("recibo_pago.html", context)

    # Generar PDF con xhtml2pdf
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