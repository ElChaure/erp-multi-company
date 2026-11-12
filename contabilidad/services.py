# contabilidad/services.py
from django.db import transaction
from django.db.models import Q, Sum, Max
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from .models import (
    Asiento,
    AsientoLinea,
    SaldoCuenta,
    PlanCuenta,
    PeriodoContable,
    ConfiguracionContableCostos,
    ConfiguracionCIF,
    CentroCostoCIF,
    ConfiguracionIVA,
    FacturaFiscal,
)
from .engine import calcular_totales_lineas, validar_asiento, calcular_saldo_final
from .constants import (
    CUENTA_SUELDOS_POR_PAGAR,
    CUENTA_INVENTARIO_PT,
    CUENTA_COSTO_MP,
    CUENTA_COSTO_MOD,
    CUENTA_COSTO_CIF,
    NOMBRE_SUELDOS_POR_PAGAR,
    NATURALEZA_DEUDORA,
    ORIGEN_NOMINA,
    DRIVER_AREA,
    DRIVER_HORAS_MAQUINA,
    DRIVER_HORAS_HOMBRE,
    DRIVER_UNIDADES,
    DRIVER_COSTO_DIRECTO,
    DRIVER_PERSONALIZADO,
    METODO_PROPORCIONAL,
)


# ============================================================
#  RESOLUCIÓN DE CUENTAS CONTABLES
# ============================================================

_CAMPOS_CONFIG_COSTOS = {
    "cuenta_inventario_pt": {
        "codigo_fallback": CUENTA_INVENTARIO_PT,
        "nombre_fallback": None,
    },
    "cuenta_costo_mp": {
        "codigo_fallback": CUENTA_COSTO_MP,
        "nombre_fallback": None,
    },
    "cuenta_costo_mod": {
        "codigo_fallback": CUENTA_COSTO_MOD,
        "nombre_fallback": None,
    },
    "cuenta_costo_cif": {
        "codigo_fallback": CUENTA_COSTO_CIF,
        "nombre_fallback": None,
    },
    "cuenta_sueldos_por_pagar": {
        "codigo_fallback": CUENTA_SUELDOS_POR_PAGAR,
        "nombre_fallback": NOMBRE_SUELDOS_POR_PAGAR,
    },
}

_ALIAS_CAMPOS_LEGACY = {
    "cuenta_costo_produccion": "cuenta_costo_mod",
}


def resolver_cuenta_contable(
    empresa,
    campo_config,
    codigo_fallback=None,
    nombre_fallback=None,
    incluir_agrupadoras=False,
):
    """Resuelve una cuenta contable con prioridad config → código → nombre."""
    campo_config = _ALIAS_CAMPOS_LEGACY.get(campo_config, campo_config)

    defaults = _CAMPOS_CONFIG_COSTOS.get(campo_config, {})
    if codigo_fallback is None:
        codigo_fallback = defaults.get("codigo_fallback")
    if nombre_fallback is None:
        nombre_fallback = defaults.get("nombre_fallback")

    try:
        config = ConfiguracionContableCostos.objects.select_related(
            campo_config
        ).get(empresa=empresa)
        cuenta_config = getattr(config, campo_config, None)
        if cuenta_config and cuenta_config.activa:
            if incluir_agrupadoras or not cuenta_config.es_agrupadora:
                return cuenta_config
    except ConfiguracionContableCostos.DoesNotExist:
        pass

    if codigo_fallback:
        qs = PlanCuenta.objects.filter(
            empresa=empresa,
            codigo__startswith=codigo_fallback,
            activa=True,
        )
        if not incluir_agrupadoras:
            qs = qs.filter(es_agrupadora=False)
        cuenta = qs.order_by("codigo").first()
        if cuenta:
            return cuenta

    if nombre_fallback:
        qs = PlanCuenta.objects.filter(empresa=empresa, activa=True)
        if not incluir_agrupadoras:
            qs = qs.filter(es_agrupadora=False)
        for palabra in nombre_fallback:
            qs = qs.filter(nombre__icontains=palabra)
        cuenta = qs.order_by("codigo").first()
        if cuenta:
            return cuenta

    return None


def _obtener_cuenta_sueldos_por_pagar(empresa):
    return resolver_cuenta_contable(
        empresa,
        campo_config="cuenta_sueldos_por_pagar",
        codigo_fallback=CUENTA_SUELDOS_POR_PAGAR,
        nombre_fallback=NOMBRE_SUELDOS_POR_PAGAR,
    )


# ============================================================
#  CONTABILIZACIÓN
# ============================================================

@transaction.atomic
def contabilizar_asiento(
    empresa,
    periodo,
    fecha,
    concepto,
    lineas_data,
    usuario=None,
    origen_modulo="",
    origen_id="",
):
    """Crea un asiento contable y actualiza los saldos de las cuentas."""
    periodo_abierto = periodo.estado == "abierto"

    errores = validar_asiento(lineas_data, periodo_abierto)
    if errores:
        raise ValidationError(errores)

    totales = calcular_totales_lineas(lineas_data)

    ultimo_numero = Asiento.objects.filter(
        empresa=empresa,
    ).aggregate(max_num=Max("numero"))["max_num"]

    try:
        siguiente = int(ultimo_numero) + 1 if ultimo_numero else 1
    except (ValueError, TypeError):
        siguiente = 1

    while Asiento.objects.filter(empresa=empresa, numero=str(siguiente).zfill(6)).exists():
        siguiente += 1

    numero = str(siguiente).zfill(6)

    asiento = Asiento.objects.create(
        empresa=empresa,
        periodo=periodo,
        fecha=fecha,
        numero=numero,
        concepto=concepto,
        total_debito=totales["total_debito"],
        total_credito=totales["total_credito"],
        estado="contabilizado",
        origen_modulo=origen_modulo,
        origen_id=origen_id,
    )

    for data in lineas_data:
        cuenta = PlanCuenta.objects.get(id=data["cuenta_id"])

        if cuenta.es_agrupadora:
            raise ValidationError(
                f"La cuenta {cuenta.codigo} es agrupadora y no permite movimientos directos."
            )

        linea = AsientoLinea.objects.create(
            asiento=asiento,
            cuenta=cuenta,
            centro_costo_id=data.get("centro_costo_id"),
            debito=Decimal(str(data.get("debito", 0))),
            credito=Decimal(str(data.get("credito", 0))),
            descripcion=data.get("descripcion", ""),
        )

        _actualizar_saldo_cuenta(asiento, linea)

    return asiento


def _actualizar_saldo_cuenta(asiento, linea):
    """Actualiza la tabla de SaldoCuenta."""
    saldo, created = SaldoCuenta.objects.get_or_create(
        empresa=asiento.empresa,
        periodo=asiento.periodo,
        cuenta=linea.cuenta,
        centro_costo=linea.centro_costo,
        defaults={
            "saldo_inicial": Decimal("0"),
            "debitos_periodo": Decimal("0"),
            "creditos_periodo": Decimal("0"),
            "saldo_final": Decimal("0"),
        },
    )

    if created:
        saldo_anterior = SaldoCuenta.objects.filter(
            empresa=asiento.empresa,
            cuenta=linea.cuenta,
            centro_costo=linea.centro_costo,
            periodo__anio__lt=asiento.periodo.anio,
        ).order_by("-periodo__anio", "-periodo__mes").first()

        if saldo_anterior:
            saldo.saldo_inicial = saldo_anterior.saldo_final

    saldo.debitos_periodo += linea.debito
    saldo.creditos_periodo += linea.credito

    saldo.saldo_final = calcular_saldo_final(
        saldo_inicial=saldo.saldo_inicial,
        debitos=saldo.debitos_periodo,
        creditos=saldo.creditos_periodo,
        naturaleza=linea.cuenta.naturaleza,
    )

    saldo.save()


# ============================================================
#  INTEGRACIÓN CON NÓMINA
# ============================================================

def generar_asiento_nomina(empresa, periodo_nomina, usuario=None):
    """Genera un asiento contable automático desde un período de nómina cerrado."""
    from datetime import date
    from rrhh.models import PeriodoNomina, NominaDetalle
    from .models import ConfiguracionContableNomina

    existente = Asiento.objects.filter(
        empresa=empresa,
        origen_modulo=ORIGEN_NOMINA,
        origen_id=str(periodo_nomina.id),
        estado="contabilizado",
    ).first()
    if existente:
        raise ValidationError(
            f"Ya existe un asiento contabilizado para este período de nómina "
            f"(N° {existente.numero})."
        )

    if periodo_nomina.estatus not in ("aprobado", "pagado", "cerrado"):
        raise ValidationError(
            f"El período de nómina está en estado "
            f"'{periodo_nomina.get_estatus_display()}'. "
            "Solo se puede contabilizar si está Aprobado, Pagado o Cerrado."
        )

    fecha_ref = periodo_nomina.fecha_pago or periodo_nomina.fecha_fin
    periodo_contable = PeriodoContable.objects.filter(
        ejercicio__empresa=empresa,
        anio=fecha_ref.year,
        mes=fecha_ref.month,
        estado="abierto",
    ).first()
    if not periodo_contable:
        raise ValidationError(
            f"No hay período contable abierto para {fecha_ref.year}-{fecha_ref.month:02d}. "
            "Crea o abre el período en Contabilidad."
        )

    detalles = NominaDetalle.objects.filter(
        nomina__periodo=periodo_nomina,
    ).values(
        "concepto__id", "concepto__codigo", "concepto__nombre", "concepto__tipo",
    ).annotate(
        total_importe=Sum("importe"),
    ).order_by("concepto__prioridad", "concepto__codigo")

    if not detalles.exists():
        raise ValidationError("No hay detalles de nómina para contabilizar.")

    conceptos_ids = [d["concepto__id"] for d in detalles]
    configs = {
        c.concepto_id: c
        for c in ConfiguracionContableNomina.objects.filter(
            empresa=empresa, concepto_id__in=conceptos_ids
        ).select_related("cuenta", "cuenta_pasivo")
    }

    faltantes = [
        d["concepto__codigo"] + " - " + d["concepto__nombre"]
        for d in detalles if d["concepto__id"] not in configs
    ]
    if faltantes:
        raise ValidationError(
            "Faltan configurar cuentas contables para: " + ", ".join(faltantes)
        )

    lineas = []

    for d in detalles:
        config = configs[d["concepto__id"]]
        monto = d["total_importe"] or Decimal("0")
        if monto == 0:
            continue

        tipo = d["concepto__tipo"]
        descripcion = f"{d['concepto__codigo']} - {d['concepto__nombre']}"

        if tipo == "percepcion":
            lineas.append({
                "cuenta_id": config.cuenta_id,
                "debito": monto,
                "credito": Decimal("0"),
                "descripcion": descripcion,
            })
        elif tipo == "deduccion":
            lineas.append({
                "cuenta_id": config.cuenta_id,
                "debito": Decimal("0"),
                "credito": monto,
                "descripcion": descripcion,
            })
        elif tipo == "aporte_patronal":
            lineas.append({
                "cuenta_id": config.cuenta_id,
                "debito": monto,
                "credito": Decimal("0"),
                "descripcion": f"Gasto patronal: {descripcion}",
            })
            if config.cuenta_pasivo_id:
                lineas.append({
                    "cuenta_id": config.cuenta_pasivo_id,
                    "debito": Decimal("0"),
                    "credito": monto,
                    "descripcion": f"Pasivo patronal: {descripcion}",
                })
            else:
                lineas.append({
                    "cuenta_id": config.cuenta_id,
                    "debito": Decimal("0"),
                    "credito": monto,
                    "descripcion": f"Contrapartida: {descripcion}",
                })

    if not lineas:
        raise ValidationError("No se generaron líneas para el asiento.")

    totales_parciales = calcular_totales_lineas(lineas)
    diferencia = totales_parciales["total_debito"] - totales_parciales["total_credito"]

    if abs(diferencia) > Decimal("0.005"):
        cuenta_pagar = _obtener_cuenta_sueldos_por_pagar(empresa)
        if not cuenta_pagar:
            raise ValidationError(
                f"No se pudo determinar la cuenta para 'Sueldos por Pagar' "
                f"(código {CUENTA_SUELDOS_POR_PAGAR} o nombre con "
                f"{NOMBRE_SUELDOS_POR_PAGAR}). "
                "Configura la cuenta en el admin (Configuración Contable de Costos) "
                "o crea la cuenta en el Plan de Cuentas."
            )

        if diferencia > 0:
            lineas.append({
                "cuenta_id": cuenta_pagar.id,
                "debito": Decimal("0"),
                "credito": diferencia,
                "descripcion": "Sueldos netos por pagar",
            })
        else:
            lineas.append({
                "cuenta_id": cuenta_pagar.id,
                "debito": abs(diferencia),
                "credito": Decimal("0"),
                "descripcion": "Ajuste por Sueldos por Pagar",
            })

    totales_check = calcular_totales_lineas(lineas)
    if not totales_check["cuadra"]:
        raise ValidationError(
            f"El asiento no cuadra. Diferencia: {totales_check['diferencia']}. "
            f"Revisa la configuración contable de los conceptos de nómina."
        )

    concepto = (
        f"Nómina {periodo_nomina.get_tipo_display()} "
        f"#{periodo_nomina.numero_periodo} ({periodo_nomina.anio}) - "
        f"Pago {fecha_ref.strftime('%d/%m/%Y')}"
    )
    asiento = contabilizar_asiento(
        empresa=empresa,
        periodo=periodo_contable,
        fecha=fecha_ref,
        concepto=concepto,
        lineas_data=lineas,
        usuario=usuario,
        origen_modulo=ORIGEN_NOMINA,
        origen_id=str(periodo_nomina.id),
    )

    asiento.periodo_nomina = periodo_nomina
    asiento.save(update_fields=["periodo_nomina"])

    return asiento


# ============================================================
#  CÁLCULO DE CIF POR CENTRO DE COSTO  (Sprint 2.5b)
# ============================================================

def _valor_driver(cdc, driver):
    """Devuelve el valor del driver para un CentroCostoCIF."""
    mapa = {
        DRIVER_AREA: cdc.area_cm2,
        DRIVER_HORAS_MAQUINA: cdc.horas_maquina_mes,
        DRIVER_HORAS_HOMBRE: cdc.horas_hombre_mes,
        DRIVER_UNIDADES: cdc.unidades_mes,
        DRIVER_COSTO_DIRECTO: cdc.costo_directo_mes,
    }
    return mapa.get(driver) or Decimal("0")


def _calcular_coeficiente(cdc, config):
    """Calcula el coeficiente de reparto de un CentroCostoCIF."""
    if cdc.coeficiente_manual is not None:
        return cdc.coeficiente_manual

    if config.driver == DRIVER_PERSONALIZADO:
        return Decimal("0")

    if config.metodo == "DIRECTO":
        return Decimal("1")

    base_pivot = config.base_pivot or Decimal("0")
    if base_pivot <= 0:
        return Decimal("0")

    valor = _valor_driver(cdc, config.driver)
    return valor / base_pivot


def calcular_cif_por_centro(empresa, monto_total_cif, periodo=None):
    """Calcula el reparto de CIF entre los centros de costo de una empresa."""
    monto_total_cif = Decimal(str(monto_total_cif or 0))

    try:
        config = ConfiguracionCIF.objects.select_related(
            "centro_pivot", "empresa"
        ).get(empresa=empresa, activa=True)
    except ConfiguracionCIF.DoesNotExist:
        return {
            "configuracion": None,
            "driver": None,
            "metodo": None,
            "base_pivot": Decimal("0"),
            "centro_pivot": None,
            "monto_total_cif": monto_total_cif,
            "centros": [],
            "total_asignado": Decimal("0"),
            "hay_configuracion": False,
        }

    centros_cif = config.centros.select_related(
        "centro_costo"
    ).filter(centro_costo__activo=True).order_by("centro_costo__codigo")

    resultado_centros = []
    suma_coeficientes = Decimal("0")

    for cdc in centros_cif:
        coef = _calcular_coeficiente(cdc, config)
        suma_coeficientes += coef
        resultado_centros.append({
            "centro_costo": cdc.centro_costo,
            "valor_driver": _valor_driver(cdc, config.driver),
            "coeficiente": coef,
            "coeficiente_manual": cdc.coeficiente_manual is not None,
            "cif_asignado": Decimal("0"),
            "porcentaje": Decimal("0"),
        })

    if suma_coeficientes > 0:
        for c in resultado_centros:
            proporcion = c["coeficiente"] / suma_coeficientes
            c["cif_asignado"] = (monto_total_cif * proporcion).quantize(Decimal("0.01"))
            c["porcentaje"] = (proporcion * 100).quantize(Decimal("0.01"))

    total_asignado = sum(c["cif_asignado"] for c in resultado_centros)

    diferencia = monto_total_cif - total_asignado
    if diferencia != 0 and resultado_centros:
        max_idx = max(
            range(len(resultado_centros)),
            key=lambda i: resultado_centros[i]["coeficiente"],
        )
        resultado_centros[max_idx]["cif_asignado"] += diferencia
        total_asignado += diferencia

    return {
        "configuracion": config,
        "driver": config.driver,
        "metodo": config.metodo,
        "base_pivot": config.base_pivot or Decimal("0"),
        "centro_pivot": config.centro_pivot,
        "monto_total_cif": monto_total_cif,
        "centros": resultado_centros,
        "total_asignado": total_asignado,
        "hay_configuracion": True,
    }


# ============================================================
#  LIBROS SENIAT  (Sprint 3.2)
# ============================================================

def _get_config_iva(empresa):
    """Devuelve la configuración de IVA de la empresa o una default."""
    try:
        return ConfiguracionIVA.objects.get(empresa=empresa, activa=True)
    except ConfiguracionIVA.DoesNotExist:
        return None


def validar_factura_para_libro(factura):
    """
    Verifica que una factura tenga los datos mínimos para aparecer en un libro.

    Retorna una lista de errores (vacía si está OK).
    """
    errores = []
    if not factura.numero_factura:
        errores.append("Falta número de factura")
    if not factura.numero_control:
        errores.append("Falta número de control")
    if not factura.rif_contraparte:
        errores.append("Falta RIF de la contraparte")
    if not factura.razon_social_contraparte:
        errores.append("Falta razón social de la contraparte")
    if factura.monto_total <= 0:
        errores.append("Monto total es cero")
    if factura.estado == "anulada":
        errores.append("Factura anulada")
    return errores


def _formatear_fecha(fecha):
    """Formatea fecha como DD/MM/AAAA (formato SENIAT)."""
    if not fecha:
        return ""
    return fecha.strftime("%d/%m/%Y")


def _estructura_factura_para_libro(factura, numero_operacion, tipo_libro):
    """
    Convierte una FacturaFiscal en un dict uniforme para el libro.

    tipo_libro: "COMPRAS" o "VENTAS"
    """
    return {
        "numero_operacion": numero_operacion,
        "factura_id": factura.id,
        "tipo": factura.tipo,
        "fecha_factura": factura.fecha_emision,
        "fecha_formateada": _formatear_fecha(factura.fecha_emision),
        "numero_factura": factura.numero_factura,
        "numero_control": factura.numero_control,
        "rif_contraparte": factura.rif_contraparte,
        "razon_social_contraparte": factura.razon_social_contraparte,
        "tipo_transaccion": factura.tipo_transaccion or "NACIONAL",
        "base_imponible": factura.base_imponible or Decimal("0"),
        "alicuota_iva": factura.alicuota_iva or Decimal("0"),
        "monto_iva": factura.monto_iva or Decimal("0"),
        "monto_exento": factura.monto_exento or Decimal("0"),
        "monto_total": factura.monto_total or Decimal("0"),
        "iva_retenido": factura.iva_retenido or Decimal("0"),
        "numero_comprobante_retencion": factura.numero_comprobante_retencion or "",
        "estado": factura.estado,
        "errores_validacion": validar_factura_para_libro(factura),
        "asiento_numero": factura.asiento.numero if factura.asiento else "",
    }


def generar_libro_compras(empresa, anio, mes):
    """
    Genera la estructura del Libro de Compras del período.

    Args:
        empresa: instancia de Empresa.
        anio: año (int).
        mes: mes 1-12 (int).

    Returns:
        dict con:
        - empresa
        - periodo: {"anio": ..., "mes": ...}
        - config_iva: ConfiguracionIVA o None
        - filas: lista de dicts (una por factura, ordenadas por fecha)
        - totales: dict con base_imponible, iva, exento, total, retenido
        - total_facturas
        - facturas_incompletas: lista de facturas con errores
        - resumen_alicuotas: dict {alicuota: {base, iva, cantidad}}
    """
    qs = FacturaFiscal.objects.filter(
        empresa=empresa,
        tipo__in=["COMPRA", "NOTA_DEBITO"],
        fecha_emision__year=anio,
        fecha_emision__month=mes,
        estado__in=["borrador", "confirmada"],
    ).select_related("asiento").order_by("fecha_emision", "numero_factura")

    filas = []
    facturas_incompletas = []
    for idx, factura in enumerate(qs, start=1):
        fila = _estructura_factura_para_libro(factura, idx, "COMPRAS")
        if fila["errores_validacion"]:
            facturas_incompletas.append(fila)
        filas.append(fila)

    return {
        "empresa": empresa,
        "periodo": {"anio": anio, "mes": mes},
        "config_iva": _get_config_iva(empresa),
        "filas": filas,
        "totales": calcular_totales_libro(filas),
        "total_facturas": len(filas),
        "facturas_incompletas": facturas_incompletas,
        "resumen_alicuotas": resumen_libro_por_alicuota(filas),
        "tipo": "COMPRAS",
    }


def generar_libro_ventas(empresa, anio, mes):
    """
    Genera la estructura del Libro de Ventas del período.
    """
    qs = FacturaFiscal.objects.filter(
        empresa=empresa,
        tipo__in=["VENTA", "NOTA_CREDITO"],
        fecha_emision__year=anio,
        fecha_emision__month=mes,
        estado__in=["borrador", "confirmada"],
    ).select_related("asiento").order_by("fecha_emision", "numero_factura")

    filas = []
    facturas_incompletas = []
    for idx, factura in enumerate(qs, start=1):
        fila = _estructura_factura_para_libro(factura, idx, "VENTAS")
        if fila["errores_validacion"]:
            facturas_incompletas.append(fila)
        filas.append(fila)

    return {
        "empresa": empresa,
        "periodo": {"anio": anio, "mes": mes},
        "config_iva": _get_config_iva(empresa),
        "filas": filas,
        "totales": calcular_totales_libro(filas),
        "total_facturas": len(filas),
        "facturas_incompletas": facturas_incompletas,
        "resumen_alicuotas": resumen_libro_por_alicuota(filas),
        "tipo": "VENTAS",
    }


def calcular_totales_libro(filas):
    """
    Calcula los totales del libro.

    Args:
        filas: lista de dicts (como los devuelve _estructura_factura_para_libro).

    Returns:
        dict con base_imponible, monto_iva, monto_exento, monto_total,
        iva_retenido, cantidad.
    """
    totales = {
        "base_imponible": Decimal("0"),
        "monto_iva": Decimal("0"),
        "monto_exento": Decimal("0"),
        "monto_total": Decimal("0"),
        "iva_retenido": Decimal("0"),
        "cantidad": 0,
    }

    for fila in filas:
        totales["base_imponible"] += fila.get("base_imponible") or Decimal("0")
        totales["monto_iva"] += fila.get("monto_iva") or Decimal("0")
        totales["monto_exento"] += fila.get("monto_exento") or Decimal("0")
        totales["monto_total"] += fila.get("monto_total") or Decimal("0")
        totales["iva_retenido"] += fila.get("iva_retenido") or Decimal("0")
        totales["cantidad"] += 1

    return totales


def resumen_libro_por_alicuota(filas):
    """
    Agrupa el libro por alícuota de IVA.

    Returns:
        dict: {
            "16.00": {"base": ..., "iva": ..., "cantidad": ...},
            "8.00": {...},
            "EXENTO": {"base": ..., "iva": 0, "cantidad": ...},
        }
    """
    resumen = {}

    for fila in filas:
        alicuota = fila.get("alicuota_iva") or Decimal("0")
        base = fila.get("base_imponible") or Decimal("0")
        iva = fila.get("monto_iva") or Decimal("0")
        exento = fila.get("monto_exento") or Decimal("0")

        # Facturas exentas
        if base == 0 and exento > 0:
            clave = "EXENTO"
            resumen.setdefault(clave, {"base": Decimal("0"), "iva": Decimal("0"), "cantidad": 0})
            resumen[clave]["base"] += exento
            resumen[clave]["cantidad"] += 1
            continue

        clave = f"{alicuota:.2f}"
        resumen.setdefault(clave, {"base": Decimal("0"), "iva": Decimal("0"), "cantidad": 0})
        resumen[clave]["base"] += base
        resumen[clave]["iva"] += iva
        resumen[clave]["cantidad"] += 1

        # Si la factura tiene además parte exenta, agregarla
        if exento > 0:
            resumen.setdefault("EXENTO", {"base": Decimal("0"), "iva": Decimal("0"), "cantidad": 0})
            resumen["EXENTO"]["base"] += exento
            resumen["EXENTO"]["cantidad"] += 1

    return resumen


def generar_txt_libro(libro):
    """
    Genera el TXT del libro en formato SENIAT (separado por tabulaciones).

    El formato es simplificado (para importación externa). Cada línea
    contiene los campos separados por tabuladores en el orden que exige
    el SENIAT para la declaración de IVA.

    Args:
        libro: dict devuelto por generar_libro_compras o generar_libro_ventas.

    Returns:
        str con el contenido del TXT.
    """
    lineas = []
    for fila in libro["filas"]:
        campos = [
            str(fila["numero_operacion"]),
            fila["fecha_formateada"],
            fila["numero_factura"],
            fila["numero_control"],
            fila["rif_contraparte"],
            fila["razon_social_contraparte"][:60],  # truncar a 60
            fila["tipo_transaccion"],
            f"{fila['base_imponible']:.2f}",
            f"{fila['alicuota_iva']:.2f}",
            f"{fila['monto_iva']:.2f}",
            f"{fila['monto_exento']:.2f}",
            f"{fila['monto_total']:.2f}",
            f"{fila['iva_retenido']:.2f}",
            fila["numero_comprobante_retencion"],
        ]
        lineas.append("\t".join(campos))

    return "\n".join(lineas)