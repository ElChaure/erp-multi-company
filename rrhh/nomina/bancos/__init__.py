"""
Módulo de generadores de archivos TXT para pago de nómina por banco.

Uso:
    from rrhh.nomina.bancos import get_generador
    generador = get_generador("0134", periodo, empresa)
    contenido = generador.generar()
"""
from .base import BancoTXTGenerator, GeneradorNoDisponible
from .factory import get_generador, GENERADORES

__all__ = [
    "BancoTXTGenerator",
    "GeneradorNoDisponible",
    "get_generador",
    "GENERADORES",
]