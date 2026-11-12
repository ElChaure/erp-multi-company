from django.contrib import admin
from .models import (
    Recurso, RecursoCosto, Actividad, ActividadRecurso,
    OrdenProduccion, OrdenReceta, OrdenConsumoReal,
)


@admin.register(Recurso)
class RecursoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "empresa", "tipo", "unidad_medida", "activo")
    list_filter = ("empresa", "tipo", "activo")
    search_fields = ("codigo", "nombre")
    autocomplete_fields = ["activo_fijo", "empleado"]


@admin.register(RecursoCosto)
class RecursoCostoAdmin(admin.ModelAdmin):
    list_display = ("recurso", "periodo", "costo_total_periodo", "costo_unitario")
    list_filter = ("recurso__empresa", "periodo")
    search_fields = ("recurso__codigo", "recurso__nombre")
    readonly_fields = ("costo_unitario",)


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "empresa", "centro_costo", "activo")
    list_filter = ("empresa", "activo")
    search_fields = ("codigo", "nombre")
    autocomplete_fields = ["centro_costo"]


@admin.register(ActividadRecurso)
class ActividadRecursoAdmin(admin.ModelAdmin):
    list_display = ("actividad", "recurso", "cantidad_estimada")
    list_filter = ("actividad__empresa", "actividad")
    search_fields = ("actividad__codigo", "actividad__nombre", "recurso__nombre")
    autocomplete_fields = ["actividad", "recurso"]


class OrdenRecetaInline(admin.TabularInline):
    model = OrdenReceta
    extra = 1
    autocomplete_fields = ["recurso"]


class OrdenConsumoRealInline(admin.TabularInline):
    model = OrdenConsumoReal
    extra = 0
    autocomplete_fields = ["recurso"]
    readonly_fields = ()


@admin.register(OrdenProduccion)
class OrdenProduccionAdmin(admin.ModelAdmin):
    list_display = ("numero", "nombre", "empresa", "estado", "fecha_inicio", "costo_total")
    list_filter = ("empresa", "estado")
    search_fields = ("numero", "nombre")
    inlines = [OrdenRecetaInline, OrdenConsumoRealInline]
    readonly_fields = ("costo_total", "costo_unitario")


@admin.register(OrdenReceta)
class OrdenRecetaAdmin(admin.ModelAdmin):
    list_display = ("orden", "recurso", "cantidad_estimada")
    list_filter = ("orden__empresa", "orden__estado")
    search_fields = ("orden__numero", "recurso__nombre")
    autocomplete_fields = ["orden", "recurso"]


@admin.register(OrdenConsumoReal)
class OrdenConsumoRealAdmin(admin.ModelAdmin):
    list_display = ("orden", "recurso", "cantidad_real", "costo_unitario_real", "fecha_consumo")
    list_filter = ("orden__empresa", "orden__estado")
    search_fields = ("orden__numero", "recurso__nombre")
    autocomplete_fields = ["orden", "recurso"]