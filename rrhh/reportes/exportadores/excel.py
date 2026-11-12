"""
Generador de archivos Excel a partir de listas de dicts.

Uso:
    from rrhh.reportes.exportadores.excel import generar_excel
    excel_bytes = generar_excel(
        titulo="Listado de Empleados",
        columnas=[...],
        datos=[...],
        metadata={...},
    )
"""
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ═══════════════════════════════════════════════════════════
#  ESTILOS
# ═══════════════════════════════════════════════════════════

COLOR_HEADER = "1E40AF"
COLOR_SUBHEADER = "EFF6FF"
COLOR_TOTAL = "F0FDF4"
COLOR_BORDER = "D1D5DB"

FUENTE_HEADER = Font(bold=True, color="FFFFFF", size=11)
FUENTE_TITULO = Font(bold=True, size=14, color="111827")
FUENTE_SUBTITULO = Font(italic=True, size=9, color="6B7280")
FUENTE_TOTAL = Font(bold=True, size=10, color="059669")

RELLENO_HEADER = PatternFill("solid", fgColor=COLOR_HEADER)
RELLENO_SUBHEADER = PatternFill("solid", fgColor=COLOR_SUBHEADER)
RELLENO_TOTAL = PatternFill("solid", fgColor=COLOR_TOTAL)

BORDE = Border(
    left=Side(style="thin", color=COLOR_BORDER),
    right=Side(style="thin", color=COLOR_BORDER),
    top=Side(style="thin", color=COLOR_BORDER),
    bottom=Side(style="thin", color=COLOR_BORDER),
)


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _get_value(obj, key, default=""):
    """Extrae valor de un dict por clave, soportando claves anidadas."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _formatear_valor(valor, formato=None):
    """Convierte un valor al formato apropiado para Excel."""
    if valor is None:
        return ""

    if isinstance(valor, Decimal):
        valor = float(valor)

    if isinstance(valor, (date, datetime)):
        return valor

    if isinstance(valor, bool):
        return "Sí" if valor else "No"

    return valor


def _formato_numero(formato):
    """Retorna el formato de número de Excel."""
    formatos = {
        "currency": '"Bs." #,##0.00',
        "number": "#,##0.00",
        "integer": "#,##0",
        "percent": "0.00%",
        "date": "DD/MM/YYYY",
        "datetime": "DD/MM/YYYY HH:MM",
    }
    return formatos.get(formato)


# ═══════════════════════════════════════════════════════════
#  GENERADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════

def generar_excel(titulo, columnas, datos, metadata=None):
    """
    Genera un archivo Excel con encabezados y datos.

    Returns:
        bytes del archivo .xlsx
    """
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]

    num_columnas = len(columnas)

    # Fila 1: Título
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_columnas)
    celda_titulo = ws.cell(row=1, column=1, value=titulo)
    celda_titulo.font = FUENTE_TITULO
    celda_titulo.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    # Fila 2: Metadata
    fila_metadata = 2
    if metadata:
        partes = [f"{k}: {v}" for k, v in metadata.items()]
        texto_metadata = "  |  ".join(partes)
    else:
        texto_metadata = f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"

    ws.merge_cells(start_row=fila_metadata, start_column=1, end_row=fila_metadata, end_column=num_columnas)
    celda_meta = ws.cell(row=fila_metadata, column=1, value=texto_metadata)
    celda_meta.font = FUENTE_SUBTITULO
    celda_meta.alignment = Alignment(horizontal="right", vertical="center")
    ws.row_dimensions[fila_metadata].height = 18

    # Encabezados
    fila_header = fila_metadata + 2

    for col_idx, col in enumerate(columnas, start=1):
        celda = ws.cell(row=fila_header, column=col_idx, value=col.get("label", col["key"]))
        celda.font = FUENTE_HEADER
        celda.fill = RELLENO_HEADER
        celda.alignment = Alignment(horizontal="center", vertical="center")
        celda.border = BORDE

        ancho = col.get("width", 18)
        ws.column_dimensions[get_column_letter(col_idx)].width = ancho

    ws.row_dimensions[fila_header].height = 22

    # Datos
    fila_inicio_datos = fila_header + 1

    for row_idx, item in enumerate(datos, start=fila_inicio_datos):
        for col_idx, col in enumerate(columnas, start=1):
            valor = _get_value(item, col["key"])
            valor = _formatear_valor(valor, col.get("format"))

            celda = ws.cell(row=row_idx, column=col_idx, value=valor)
            celda.border = BORDE

            formato = _formato_numero(col.get("format"))
            if formato:
                celda.number_format = formato

            align = col.get("align", "left")
            if col.get("format") in ("currency", "number", "integer", "percent"):
                align = "right"
            celda.alignment = Alignment(horizontal=align, vertical="center", wrap_text=False)

    # Fila de totales
    fila_totales = fila_inicio_datos + len(datos)
    columnas_con_total = [c for c in columnas if c.get("total")]

    if columnas_con_total:
        ws.cell(row=fila_totales, column=1, value="TOTALES").font = FUENTE_TOTAL

        for col_idx, col in enumerate(columnas, start=1):
            if col.get("total"):
                key = col["key"]
                total = sum(
                    float(_get_value(d, key) or 0)
                    for d in datos
                    if _get_value(d, key) is not None
                )
                celda = ws.cell(row=fila_totales, column=col_idx, value=total)
                celda.font = FUENTE_TOTAL
                celda.fill = RELLENO_TOTAL
                celda.number_format = _formato_numero(col.get("format")) or "#,##0.00"
                celda.alignment = Alignment(horizontal="right", vertical="center")
                celda.border = BORDE

    ws.freeze_panes = ws.cell(row=fila_inicio_datos, column=1)

    if datos:
        ws.auto_filter.ref = (
            f"A{fila_header}:"
            f"{get_column_letter(num_columnas)}{fila_header + len(datos)}"
        )

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()