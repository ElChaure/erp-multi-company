"""
Fábrica que devuelve el generador correcto según el código de banco.
"""
from .base import GeneradorNoDisponible
from .banesco import BanescoTXTGenerator
from .provincial import ProvincialTXTGenerator


# Registro de generadores disponibles
GENERADORES = {
    "0134": BanescoTXTGenerator,
    "0108": ProvincialTXTGenerator,
    # Agregar más cuando estén implementados:
    # "0102": BDVTXTGenerator,
    # "0105": MercantilTXTGenerator,
    # "0114": BancaribeTXTGenerator,
    # "0151": BFCTXTGenerator,
    # "0191": BNCTXTGenerator,
}


def get_generador(codigo_banco, periodo, empresa, nominas=None):
    """
    Devuelve una instancia del generador para el banco dado.

    Args:
        codigo_banco: str, código Sudeban (4 dígitos)
        periodo: PeriodoNomina
        empresa: Empresa
        nominas: queryset opcional

    Returns:
        Instancia de BancoTXTGenerator

    Raises:
        GeneradorNoDisponible: si el banco no tiene generador implementado.
    """
    generador_cls = GENERADORES.get(codigo_banco)
    if not generador_cls:
        raise GeneradorNoDisponible(
            f"No hay generador implementado para el banco {codigo_banco}. "
            f"Bancos disponibles: {', '.join(sorted(GENERADORES.keys()))}"
        )
    return generador_cls(periodo, empresa, nominas)