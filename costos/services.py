# costos/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal

from contabilidad.models import PeriodoContable
from contabilidad.services import contabilizar_asiento, resolver_cuenta_contable
from contabilidad.constants import ORIGEN_COSTOS

from .engine import calcular_costo_orden
from .sincronizacion import sincronizar_costos_mes


# ─────────────────────────────────────────────────────────────
#  MAPEO TIPO DE COSTO → CAMPO DE CONFIGURACIÓN
#  Permite iterar los 3 tipos sin if/elif repetidos.
# ─────────────────────────────────────────────────────────────
_TIPOS_COSTO = [
    {
        "campo_config": "cuenta_costo_mp",
        "campo_monto": "costo_materia_prima",
        "etiqueta": "Materia Prima (MP)",
        "descripcion_linea": "Costo MP",
    },
    {
        "campo_config": "cuenta_costo_mod",
        "campo_monto": "costo_mano_obra",
        "etiqueta": "Mano de Obra Directa (MOD)",
        "descripcion_linea": "Costo MOD",
    },
    {
        "campo_config": "cuenta_costo_cif",
        "campo_monto": "costo_indirecto",
        "etiqueta": "Costos Indirectos de Fabricación (CIF)",
        "descripcion_linea": "Costo CIF",
    },
]


@transaction.atomic
def consolidar_costo_orden(orden, periodo, usuario=None):
    """
    Calcula el costo de la orden y actualiza los campos de la orden.
    Retorna el diccionario con los costos calculados.
    """
    if orden.estado == "CANCELADO":
        raise ValidationError("No se puede costear una orden cancelada.")

    if orden.estado == "BORRADOR":
        raise ValidationError(
            "Debe cambiar el estado de la orden a 'En Proceso' o 'Finalizado' antes de costear."
        )

    # 1. Calcular costos
    costos = calcular_costo_orden(orden, periodo)

    # 2. Guardar en la orden
    orden.costo_materia_prima = costos["costo_materia_prima"]
    orden.costo_mano_obra = costos["costo_mano_obra"]
    orden.costo_indirecto = costos["costo_indirecto"]
    orden.costo_total = costos["costo_total"]
    orden.costo_unitario = costos["costo_unitario"]
    orden.save(update_fields=[
        "costo_materia_prima", "costo_mano_obra",
        "costo_indirecto", "costo_total", "costo_unitario",
    ])

    return costos


@transaction.atomic
def generar_asiento_costo_orden(orden, periodo_contable, usuario=None):
    """
    Genera un asiento contable multilínea al costear una orden de producción.

    Estructura del asiento:
        DÉBITO  Inventario de Productos Terminados  ← costo_total
        CRÉDITO Costo MP                            ← costo_materia_prima
        CRÉDITO Costo MOD                           ← costo_mano_obra
        CRÉDITO Costo CIF                           ← costo_indirecto

    Reglas:
    - Solo se incluyen líneas de crédito cuyo monto sea > 0.
    - Cada cuenta se resuelve respetando ConfiguracionContableCostos y,
      si no hay config, cae al fallback de constants.py (5101/5102/5103).
    - Si falta una cuenta necesaria (con monto > 0), se lanza un error
      indicando cuál configurar.
    - Si la orden tiene centro_costo, todas las líneas se le asignan.
    """
    # ─── Validar monto total ───
    if not orden.costo_total or orden.costo_total <= 0:
        raise ValidationError(
            "El costo total de la orden es cero. No se puede generar el asiento."
        )

    # ─── Resolver cuenta de inventario (débito) ───
    cuenta_inventario = resolver_cuenta_contable(
        orden.empresa, "cuenta_inventario_pt"
    )
    if not cuenta_inventario:
        raise ValidationError(
            "No se pudo resolver la cuenta de Inventario de Productos Terminados. "
            "Verifica la configuración contable de costos o crea la cuenta 110303 en el Plan de Cuentas."
        )

    # ─── Construir líneas de crédito por tipo de costo ───
    lineas_credito = []
    faltantes = []

    for tipo in _TIPOS_COSTO:
        monto = getattr(orden, tipo["campo_monto"], Decimal("0")) or Decimal("0")
        if monto <= 0:
            # Si no hay monto para este tipo, no se requiere cuenta.
            continue

        cuenta = resolver_cuenta_contable(orden.empresa, tipo["campo_config"])
        if not cuenta:
            faltantes.append(f"{tipo['etiqueta']} (campo '{tipo['campo_config']}')")
            continue

        lineas_credito.append({
            "cuenta_id": cuenta.id,
            "debito": Decimal("0"),
            "credito": monto,
            "descripcion": f"{tipo['descripcion_linea']} - Orden {orden.numero}",
        })

    if faltantes:
        raise ValidationError(
            "No se pudieron resolver las siguientes cuentas de costo: "
            + ", ".join(faltantes)
            + ". Configúralas en el admin (Configuración Contable de Costos) "
            "o crea las cuentas 5101 / 5102 / 5103 en el Plan de Cuentas."
        )

    if not lineas_credito:
        # Caso raro: costo_total > 0 pero ningún subtipo tiene monto.
        # No debería pasar si la orden fue costeada correctamente, pero
        # por seguridad lanzamos un error claro.
        raise ValidationError(
            "La orden tiene costo total pero no tiene desglose de MP/MOD/CIF. "
            "Vuelve a costear la orden con 'Costear' antes de generar el asiento."
        )

    # ─── Validar cuadre con la cuenta de inventario ───
    total_credito = sum(l["credito"] for l in lineas_credito)
    if abs(total_credito - orden.costo_total) > Decimal("0.01"):
        raise ValidationError(
            f"El desglose de costos ({total_credito}) no coincide con el costo total "
            f"de la orden ({orden.costo_total}). "
            "Vuelve a costear la orden antes de generar el asiento."
        )

    # ─── Construir línea de débito ───
    linea_debito = {
        "cuenta_id": cuenta_inventario.id,
        "debito": orden.costo_total,
        "credito": Decimal("0"),
        "descripcion": f"Costeo Orden {orden.numero} - {orden.nombre}",
    }

    lineas = [linea_debito] + lineas_credito

    # ─── Contabilizar ───
    asiento = contabilizar_asiento(
        empresa=orden.empresa,
        periodo=periodo_contable,
        fecha=orden.fecha_fin or orden.fecha_inicio,
        concepto=f"Costeo de Orden de Producción {orden.numero}",
        lineas_data=lineas,
        usuario=usuario,
        origen_modulo=ORIGEN_COSTOS,
        origen_id=str(orden.id),
    )

    return asiento


@transaction.atomic
def sincronizar_todos_los_costos(empresa, anio, mes, usuario=None):
    """
    Sincroniza los costos reales de todos los recursos para un período.
    """
    periodo = PeriodoContable.objects.filter(
        ejercicio__empresa=empresa,
        anio=anio,
        mes=mes,
    ).first()
    if not periodo:
        raise ValidationError(f"No existe período contable para {anio}-{mes:02d}.")

    return sincronizar_costos_mes(empresa, periodo)