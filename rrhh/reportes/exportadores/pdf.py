"""
Generador de PDF a partir de listas de dicts.

Uso:
    from rrhh.reportes.exportadores.pdf import generar_pdf
    pdf_bytes = generar_pdf(
        titulo="Listado de Empleados",
        columnas=[...],
        datos=[...],
        empresa=empresa,
        metadata={...},
        orientacion="landscape",
    )
"""
import base64
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from django.template.loader import render_to_string

try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
except ImportError:
    XHTML2PDF_AVAILABLE = False


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _cargar_logo_base64(empresa):
    """Carga el logo de la empresa y lo convierte a base64."""
    if not empresa:
        return None
    if not hasattr(empresa, "logo") or not empresa.logo:
        return None

    try:
        with empresa.logo.open("rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def _formatear_valor(valor, formato=None):
    """Formatea un valor según el tipo especificado."""
    if valor is None or valor == "":
        return "—"

    # Decimal → float
    if isinstance(valor, Decimal):
        valor = float(valor)

    if formato == "currency":
        try:
            return f"Bs. {float(valor):,.2f}"
        except (ValueError, TypeError):
            return str(valor)

    if formato == "number":
        try:
            return f"{float(valor):,.2f}"
        except (ValueError, TypeError):
            return str(valor)

    if formato == "integer":
        try:
            return f"{int(valor):,}"
        except (ValueError, TypeError):
            return str(valor)

    if formato == "percent":
        try:
            return f"{float(valor):.2f}%"
        except (ValueError, TypeError):
            return str(valor)

    if formato == "date":
        if isinstance(valor, (date, datetime)):
            return valor.strftime("%d/%m/%Y")
        return str(valor)

    if formato == "datetime":
        if isinstance(valor, (date, datetime)):
            return valor.strftime("%d/%m/%Y %H:%M")
        return str(valor)

    if isinstance(valor, bool):
        return "Sí" if valor else "No"

    if isinstance(valor, (date, datetime)):
        return valor.strftime("%d/%m/%Y")

    return str(valor)


def _calcular_totales(columnas, datos):
    """
    Calcula los totales de las columnas marcadas con `total: True`.

    Returns:
        dict con key → total formateado
    """
    totales = {}
    for col in columnas:
        if not col.get("total"):
            continue

        key = col["key"]
        total = 0
        for fila in datos:
            val = fila.get(key)
            if val is None:
                continue
            try:
                total += float(val)
            except (ValueError, TypeError):
                pass

        # Formatear
        formato = col.get("format")
        if formato == "currency":
            totales[key] = f"Bs. {total:,.2f}"
        elif formato == "integer":
            totales[key] = f"{int(total):,}"
        elif formato == "number":
            totales[key] = f"{total:,.2f}"
        else:
            totales[key] = f"{total:,.2f}"

    return totales


# ═══════════════════════════════════════════════════════════
#  GENERADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════

def generar_pdf(
    titulo,
    columnas,
    datos,
    empresa=None,
    metadata=None,
    subtitulo="",
    orientacion="portrait",
):
    """
    Genera un PDF con el reporte.

    Args:
        titulo: Título del reporte
        columnas: lista de dicts con keys:
            - key: nombre del campo
            - label: encabezado
            - width: ancho en px (opcional)
            - format: 'currency', 'number', 'integer', 'percent', 'date', 'datetime'
            - align: 'left', 'center', 'right'
            - total: True si se debe sumar
        datos: lista de dicts
        empresa: instancia de Empresa (para el logo)
        metadata: dict con info de filtros aplicados
        subtitulo: texto adicional bajo el título
        orientacion: 'portrait' o 'landscape'

    Returns:
        bytes del PDF

    Raises:
        RuntimeError: si xhtml2pdf no está instalado o falla
    """
    if not XHTML2PDF_AVAILABLE:
        raise RuntimeError(
            "xhtml2pdf no está instalado. Ejecuta: pip install xhtml2pdf"
        )

    # ─── Preprocesar columnas ────────────────────────────
    columnas_procesadas = []
    for col in columnas:
        col_copy = dict(col)
        col_copy.setdefault("width", 80)
        col_copy.setdefault("align", "left")
        columnas_procesadas.append(col_copy)

    # ─── Preprocesar datos (formatear valores) ───────────
    datos_formateados = []
    for fila in datos:
        nueva_fila = {}
        for col in columnas_procesadas:
            valor = fila.get(col["key"])
            nueva_fila[col["key"]] = _formatear_valor(valor, col.get("format"))
        datos_formateados.append(nueva_fila)

    # ─── Calcular totales ────────────────────────────────
    totales = _calcular_totales(columnas_procesadas, datos)
    tiene_totales = bool(totales)

    # ─── Preparar logo y empresa ─────────────────────────
    logo_base64 = _cargar_logo_base64(empresa)

    empresa_initial = "?"
    if empresa:
        nombre = empresa.nombre_comercial or empresa.razon_social or ""
        empresa_initial = nombre[0].upper() if nombre else "?"

    # ─── Construir contexto ──────────────────────────────
    context = {
        "titulo": titulo,
        "subtitulo": subtitulo,
        "columnas": columnas_procesadas,
        "datos": datos_formateados,
        "empresa": empresa,
        "logo_base64": logo_base64,
        "empresa_initial": empresa_initial,
        "metadata": metadata or {},
        "totales": totales,
        "tiene_totales": tiene_totales,
        "orientacion": orientacion,
    }

    # ─── Renderizar HTML ─────────────────────────────────
    html_string = render_to_string("reporte_generico.html", context)

    # ─── Generar PDF ─────────────────────────────────────
    buffer = BytesIO()
    pisa_status = pisa.CreatePDF(
        src=html_string,
        dest=buffer,
        encoding="UTF-8",
    )

    if pisa_status.err:
        raise RuntimeError(
            f"Error al generar PDF con xhtml2pdf: código {pisa_status.err}"
        )

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes