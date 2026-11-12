"""
Servicios para agrupar nóminas por banco y preparar la descarga.
"""
from collections import defaultdict
from decimal import Decimal

from rrhh.models import NominaEmpleado, Banco

from .factory import GENERADORES


def nominas_agrupadas_por_banco(periodo):
    """
    Agrupa las nóminas de un periodo por banco del empleado.

    Args:
        periodo: instancia de PeriodoNomina

    Returns:
        list de dicts ordenada por código:
        [
            {
                "codigo": "0108",
                "banco": instancia Banco o None,
                "nombre": "Provincial",
                "total": Decimal,
                "cantidad": int,
                "generador_disponible": bool,
            },
            ...
        ]
    """
    nominas = (
        NominaEmpleado.objects
        .filter(periodo=periodo)
        .select_related("empleado", "empleado__banco")
    )

    agrupadas = defaultdict(lambda: {
        "total": Decimal("0"),
        "cantidad": 0,
        "empleado_ids": [],
    })

    sin_banco = 0
    for nomina in nominas:
        banco = nomina.empleado.banco
        if not banco:
            sin_banco += 1
            continue

        key = banco.codigo
        agrupadas[key]["total"] += nomina.neto_pagar
        agrupadas[key]["cantidad"] += 1
        agrupadas[key]["empleado_ids"].append(nomina.empleado_id)

    resultado = []
    for codigo, data in sorted(agrupadas.items()):
        banco = Banco.objects.filter(codigo=codigo).first()
        nombre = banco.nombre_corto if banco and banco.nombre_corto else (
            banco.nombre if banco else codigo
        )
        resultado.append({
            "codigo": codigo,
            "banco": banco,
            "nombre": nombre,
            "total": data["total"],
            "cantidad": data["cantidad"],
            "generador_disponible": codigo in GENERADORES,
        })

    return {
        "bancos": resultado,
        "sin_banco": sin_banco,
    }