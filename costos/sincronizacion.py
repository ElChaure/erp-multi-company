# costos/sincronizacion.py
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction, models
from django.core.exceptions import ValidationError
from contabilidad.models import PeriodoContable
from .models import Recurso, RecursoCosto
from .constants import TIPO_RECURSO_MAQUINA, TIPO_RECURSO_MANO_OBRA

# Horas mensuales por defecto si el CentroCosto no define capacidad_horas_mes
HORAS_MES_DEFAULT = Decimal("160")


def _rango_mes(anio, mes):
    """
    Devuelve (fecha_inicio_mes, fecha_fin_mes) para el mes indicado.
    Maneja correctamente diciembre → 31/12 del mismo año.
    """
    fecha_inicio = date(anio, mes, 1)
    if mes == 12:
        fecha_fin = date(anio, 12, 31)
    else:
        fecha_fin = date(anio, mes + 1, 1) - timedelta(days=1)
    return fecha_inicio, fecha_fin


def _horas_del_recurso(recurso):
    """
    Determina las horas mensuales a usar para costear el recurso.

    Prioridad:
    1. capacidad_horas_mes del CentroCosto del activo_fijo (si es máquina).
    2. capacidad_horas_mes del CentroCosto del empleado (si es mano de obra).
    3. HORAS_MES_DEFAULT (160).
    """
    centro = None
    if recurso.activo_fijo and recurso.activo_fijo.centro_costo:
        centro = recurso.activo_fijo.centro_costo
    elif recurso.empleado and recurso.empleado.departamento:
        # Departamento no es CentroCosto; no asumimos equivalencia.
        # Si en el futuro se agrega FK directa, usar aquí.
        centro = None

    if centro and centro.capacidad_horas_mes and centro.capacidad_horas_mes > 0:
        return centro.capacidad_horas_mes
    return HORAS_MES_DEFAULT


@transaction.atomic
def sincronizar_costos_mes(empresa, periodo):
    """
    Sincroniza los costos reales de todos los recursos de la empresa
    para el período contable indicado.

    Retorna dict:
        {
            "maquinas": int,
            "mano_obra": int,
            "insumos": int,
            "errores": list[str],
        }
    """
    anio = periodo.anio
    mes = periodo.mes
    resultados = {
        "maquinas": 0,
        "mano_obra": 0,
        "insumos": 0,
        "errores": [],
    }

    fecha_inicio_mes, fecha_fin_mes = _rango_mes(anio, mes)

    recursos = Recurso.objects.filter(
        empresa=empresa, activo=True
    ).select_related("activo_fijo", "activo_fijo__centro_costo", "empleado")

    for recurso in recursos:
        try:
            costo_mensual = Decimal("0")
            horas_trabajadas = _horas_del_recurso(recurso)
            cantidad_producida = Decimal("0")

            # ─── 1. MÁQUINAS (CIF) — desde DepreciacionActivo ───
            if recurso.tipo == TIPO_RECURSO_MAQUINA and recurso.activo_fijo:
                from activos.models import DepreciacionActivo

                depreciacion = DepreciacionActivo.objects.filter(
                    activo=recurso.activo_fijo,
                    fecha__year=anio,
                    fecha__month=mes,
                ).aggregate(total=models.Sum("monto"))["total"] or Decimal("0")

                costo_mensual = depreciacion
                resultados["maquinas"] += 1

            # ─── 2. MANO DE OBRA (MOD) — desde Nómina ───
            elif recurso.tipo == TIPO_RECURSO_MANO_OBRA and recurso.empleado:
                from rrhh.models import PeriodoNomina, NominaEmpleado

                periodo_nomina = PeriodoNomina.objects.filter(
                    empresa=empresa,
                    estatus__in=["aprobado", "pagado", "cerrado"],
                    fecha_inicio__lte=fecha_fin_mes,
                    fecha_fin__gte=fecha_inicio_mes,
                ).first()

                if periodo_nomina:
                    nomina_empleado = NominaEmpleado.objects.filter(
                        periodo=periodo_nomina,
                        empleado=recurso.empleado,
                    ).first()
                    if nomina_empleado:
                        # Costo total = percepciones + aportes patronales
                        costo_mensual = (
                            (nomina_empleado.total_percepciones or Decimal("0"))
                            + (nomina_empleado.total_aportes_patronales or Decimal("0"))
                        )
                        resultados["mano_obra"] += 1

            # ─── 3. INSUMOS (MP) — Fase futura (compras) ───
            elif recurso.tipo == TIPO_RECURSO_INSUMO:
                # Sin lógica de costeo todavía. Solo se cuenta.
                resultados["insumos"] += 1
                continue

            # ─── Guardar o actualizar el RecursoCosto ───
            RecursoCosto.objects.update_or_create(
                recurso=recurso,
                periodo=periodo,
                defaults={
                    "costo_total_periodo": costo_mensual,
                    "horas_trabajadas": horas_trabajadas,
                    "cantidad_producida": cantidad_producida,
                },
            )
        except Exception as e:
            resultados["errores"].append(f"{recurso.nombre}: {e}")

    return resultados