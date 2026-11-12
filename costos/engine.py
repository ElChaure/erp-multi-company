# costos/engine.py
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum
from .models import RecursoCosto, OrdenConsumoReal, OrdenReceta

def calcular_costo_unitario_recurso(recurso, periodo):
    """
    Calcula el costo por unidad (hora, kilo, etc.) de un recurso en un período.
    Prioriza el costo real registrado en RecursoCosto.
    """
    try:
        costo_real = RecursoCosto.objects.get(recurso=recurso, periodo=periodo)
        return costo_real.costo_unitario
    except RecursoCosto.DoesNotExist:
        return Decimal("0.000000")

def calcular_costo_orden(orden, periodo):
    """
    Calcula el costo total de una orden de producción basándose en:
    1. Los consumos reales registrados (OrdenConsumoReal).
    2. Si no hay consumos reales, usa la receta estimada (OrdenReceta).
    
    Retorna un diccionario con los totales por tipo de recurso y el total general.
    """
    from .constants import TIPO_RECURSO_MAQUINA, TIPO_RECURSO_MANO_OBRA, TIPO_RECURSO_INSUMO

    costo_mp = Decimal("0")  # Materia Prima (Insumos)
    costo_mo = Decimal("0")  # Mano de Obra
    costo_cif = Decimal("0") # Costos Indirectos (Máquinas)
    
    # 1. Intentar con consumos reales
    consumos = OrdenConsumoReal.objects.filter(orden=orden).select_related("recurso")
    
    if consumos.exists():
        for consumo in consumos:
            # Si el consumo real no tiene costo unitario cargado, lo buscamos en el período
            costo_unit = consumo.costo_unitario_real
            if costo_unit == 0:
                costo_unit = calcular_costo_unitario_recurso(consumo.recurso, periodo)
            
            costo_total_recurso = consumo.cantidad_real * costo_unit
            
            # Clasificar según el tipo de recurso
            if consumo.recurso.tipo == TIPO_RECURSO_INSUMO:
                costo_mp += costo_total_recurso
            elif consumo.recurso.tipo == TIPO_RECURSO_MANO_OBRA:
                costo_mo += costo_total_recurso
            elif consumo.recurso.tipo == TIPO_RECURSO_MAQUINA:
                costo_cif += costo_total_recurso
                
    # 2. Si no hay consumos reales, usar la receta estimada (BOM)
    else:
        recetas = OrdenReceta.objects.filter(orden=orden).select_related("recurso")
        for receta in recetas:
            costo_unit = receta.costo_unitario_estimado
            if costo_unit == 0:
                costo_unit = calcular_costo_unitario_recurso(receta.recurso, periodo)
            
            costo_total_recurso = receta.cantidad_estimada * costo_unit
            
            if receta.recurso.tipo == TIPO_RECURSO_INSUMO:
                costo_mp += costo_total_recurso
            elif receta.recurso.tipo == TIPO_RECURSO_MANO_OBRA:
                costo_mo += costo_total_recurso
            elif receta.recurso.tipo == TIPO_RECURSO_MAQUINA:
                costo_cif += costo_total_recurso

    costo_total = costo_mp + costo_mo + costo_cif
    costo_unitario = Decimal("0")
    if orden.cantidad_producida and orden.cantidad_producida > 0:
        costo_unitario = costo_total / orden.cantidad_producida

    return {
        "costo_materia_prima": costo_mp,
        "costo_mano_obra": costo_mo,
        "costo_indirecto": costo_cif,
        "costo_total": costo_total,
        "costo_unitario": costo_unitario.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
    }