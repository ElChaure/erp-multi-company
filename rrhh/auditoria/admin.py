"""
Admin de auditoría. Solo lectura, con filtros y búsqueda.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import Auditoria, Accion


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = (
        "fecha",
        "usuario",
        "accion_badge",
        "tabla",
        "registro_id",
        "registro_repr_corto",
        "ip",
    )
    list_filter = (
        "accion",
        "tabla",
        "fecha",
        "usuario",
        "empresa_id",
    )
    search_fields = (
        "tabla",
        "registro_id",
        "registro_repr",
        "descripcion",
        "usuario__username",
        "usuario__email",
        "ip",
    )
    readonly_fields = (
        "usuario", "empresa_id", "tabla", "registro_id", "registro_repr",
        "accion", "valores_anteriores_pretty", "valores_nuevos_pretty",
        "campos_modificados", "ip", "user_agent", "url", "metodo_http",
        "descripcion", "metadata", "fecha",
    )
    date_hierarchy = "fecha"
    list_per_page = 50
    ordering = ["-fecha"]

    fieldsets = (
        ("Identificación", {
            "fields": ("usuario", "empresa_id", "tabla", "registro_id", "registro_repr")
        }),
        ("Acción", {
            "fields": ("accion", "descripcion", "campos_modificados")
        }),
        ("Cambios", {
            "fields": ("valores_anteriores_pretty", "valores_nuevos_pretty"),
        }),
        ("Contexto", {
            "fields": ("ip", "user_agent", "url", "metodo_http"),
            "classes": ("collapse",),
        }),
        ("Metadata", {
            "fields": ("metadata", "fecha"),
            "classes": ("collapse",),
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="Acción")
    def accion_badge(self, obj):
        colores = {
            "create": "#059669",
            "update": "#2563eb",
            "delete": "#dc2626",
            "login": "#0891b2",
            "logout": "#6b7280",
            "login_failed": "#dc2626",
            "export": "#7c3aed",
            "approve": "#059669",
            "reject": "#dc2626",
            "cancel": "#d97706",
        }
        color = colores.get(obj.accion, "#6b7280")
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;'
            'border-radius:10px;font-size:11px;">{}</span>',
            color,
            obj.get_accion_display(),
        )

    @admin.display(description="Registro")
    def registro_repr_corto(self, obj):
        if obj.registro_repr:
            return obj.registro_repr[:60]
        return "—"

    @admin.display(description="Valores anteriores")
    def valores_anteriores_pretty(self, obj):
        if not obj.valores_anteriores:
            return "—"
        import json
        return format_html(
            '<pre style="background:#f9fafb;padding:10px;border-radius:4px;'
            'max-height:400px;overflow:auto;font-size:12px;">{}</pre>',
            json.dumps(obj.valores_anteriores, indent=2, ensure_ascii=False),
        )

    @admin.display(description="Valores nuevos")
    def valores_nuevos_pretty(self, obj):
        if not obj.valores_nuevos:
            return "—"
        import json
        return format_html(
            '<pre style="background:#f0fdf4;padding:10px;border-radius:4px;'
            'max-height:400px;overflow:auto;font-size:12px;">{}</pre>',
            json.dumps(obj.valores_nuevos, indent=2, ensure_ascii=False),
        )