# contabilidad/urls.py
from django.urls import path
from . import views

app_name = "contabilidad"

urlpatterns = [
    # ─── Comprobantes ───
    path("comprobantes/", views.comprobante_lista, name="comprobante_lista"),
    path("comprobantes/nuevo/", views.comprobante_nuevo, name="comprobante_nuevo"),
    path("comprobantes/<int:comprobante_id>/", views.comprobante_detalle, name="comprobante_detalle"),
    path("comprobantes/<int:comprobante_id>/contabilizar/", views.comprobante_contabilizar, name="comprobante_contabilizar"),

    # ─── Libros y estados ───
    path("libro-diario/", views.libro_diario, name="libro_diario"),
    path("libro-mayor/", views.libro_mayor, name="libro_mayor"),
    path("balance-comprobacion/", views.balance_comprobacion, name="balance_comprobacion"),
    path("estado-resultados/", views.estado_resultados, name="estado_resultados"),
    path("balance-general/", views.balance_general, name="balance_general"),
    path("dashboard/", views.dashboard_contable, name="dashboard_contable"),

    # ─── Integración con nómina ───
    path("configuracion-nomina/", views.configuracion_nomina, name="configuracion_nomina"),
    path("nomina/<int:periodo_id>/generar-asiento/", views.generar_asiento_nomina_view, name="generar_asiento_nomina"),

    # ─── Activos fijos ───
    path("depreciaciones/", views.depreciacion_lista, name="depreciacion_lista"),

    # ─── Presupuesto (Fase 3) ───
    path("presupuestos/", views.presupuesto_lista, name="presupuesto_lista"),
    path("presupuestos/<int:presupuesto_id>/", views.presupuesto_detalle, name="presupuesto_detalle"),
    path("presupuestos/<int:presupuesto_id>/vs-real/", views.presupuesto_vs_real, name="presupuesto_vs_real"),
    path("presupuestos/<int:presupuesto_id>/vs-real/export/", views.presupuesto_vs_real_export, name="presupuesto_vs_real_export"),
    path("presupuestos/<int:presupuesto_id>/dashboard/", views.dashboard_gerencial, name="dashboard_gerencial"),

    # ─── Costos (Fase 4) ───
    path("costos/ordenes/", views.costos_ordenes_lista, name="costos_ordenes_lista"),
    path("costos/sincronizar/", views.costos_sincronizar, name="costos_sincronizar"),

    # ─── CIF (Sprint 2.5) ───
    path("cif/", views.cif_reporte, name="cif_reporte"),
    path("cif/export/", views.cif_reporte_export, name="cif_reporte_export"),
    path("cif/configuracion/", views.cif_configuracion, name="cif_configuracion"),
    path("cif/centro/<int:centro_costo_id>/", views.cif_centro_detalle, name="cif_centro_detalle"),

    # ─── Libros SENIAT (Sprint 3) ───
    path("libros/compras/", views.libro_compras, name="libro_compras"),
    path("libros/compras/export/", views.libro_compras_export, name="libro_compras_export"),
    path("libros/compras/txt/", views.libro_compras_txt, name="libro_compras_txt"),
    path("libros/ventas/", views.libro_ventas, name="libro_ventas"),
    path("libros/ventas/export/", views.libro_ventas_export, name="libro_ventas_export"),
    path("libros/ventas/txt/", views.libro_ventas_txt, name="libro_ventas_txt"),

    # ─── Facturas fiscales ───
    path("facturas/", views.factura_fiscal_lista, name="factura_fiscal_lista"),
    path("facturas/nueva/", views.factura_fiscal_nueva, name="factura_fiscal_nueva"),
    path("facturas/<int:factura_id>/", views.factura_fiscal_detalle, name="factura_fiscal_detalle"),
    path("facturas/<int:factura_id>/confirmar/", views.factura_fiscal_confirmar, name="factura_fiscal_confirmar"),
]