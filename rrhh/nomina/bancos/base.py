"""
Clase base para generadores de archivos TXT de pago de nómina.
Cada banco implementa su propio formato.
"""
from abc import ABC, abstractmethod
from decimal import Decimal


class GeneradorNoDisponible(Exception):
    """El banco no tiene generador implementado."""
    pass


class BancoTXTGenerator(ABC):
    """
    Clase base para generar el archivo TXT de pago de nómina de un banco.

    Las subclases deben implementar:
        - codigo_banco (propiedad)
        - generar() (método)

    Helpers disponibles:
        - self.nominas → queryset filtrado por banco
        - self._fmt_cedula(empleado)
        - self._fmt_cuenta(cuenta)
        - self._fmt_monto(monto, digitos=17)
        - self._nombre_completo(empleado)
        - self._monto_total()
    """

    # Nombre corto del banco (para el nombre del archivo)
    banco_nombre = "BANCO"

    def __init__(self, periodo, empresa, nominas=None):
        """
        Args:
            periodo: instancia de PeriodoNomina
            empresa: instancia de Empresa
            nominas: queryset opcional (si None, se obtiene del periodo)
        """
        self.periodo = periodo
        self.empresa = empresa
        self._nominas = nominas

    @property
    def nominas(self):
        """Nóminas filtradas por el banco del generador."""
        if self._nominas is not None:
            return self._nominas
        from rrhh.models import NominaEmpleado
        return (
            NominaEmpleado.objects
            .filter(
                periodo=self.periodo,
                empleado__banco__codigo=self.codigo_banco,
            )
            .select_related("empleado", "empleado__banco")
            .order_by("empleado__apellido_paterno", "empleado__nombre")
        )

    @property
    @abstractmethod
    def codigo_banco(self):
        """Código Sudeban del banco (ej: '0134')."""
        raise NotImplementedError

    @abstractmethod
    def generar(self) -> str:
        """
        Genera el contenido del archivo TXT.

        Returns:
            String con el contenido del archivo (líneas separadas por \\n).
        """
        raise NotImplementedError

    # ═══════════════════════════════════════════════════════
    #  HELPERS COMUNES
    # ═══════════════════════════════════════════════════════

    def _fmt_cedula(self, empleado):
        """Formatea la cédula: V000000000 (1 letra + 9 dígitos)."""
        cedula_limpia = str(empleado.cedula).replace(".", "").replace(" ", "").strip()
        try:
            return f"{empleado.nacionalidad}{int(cedula_limpia):09d}"
        except (ValueError, TypeError):
            return f"{empleado.nacionalidad}{cedula_limpia:>9}"

    def _fmt_cuenta(self, cuenta):
        """
        Formatea la cuenta de 20 dígitos.
        - Quita guiones y espacios
        - Rellena con ceros a la izquierda
        - Trunca a 20 si es más larga
        """
        if not cuenta:
            return "0" * 20
        limpio = str(cuenta).replace("-", "").replace(" ", "").strip()
        return limpio.zfill(20)[:20]

    def _fmt_monto(self, monto, digitos=17):
        """
        Formatea el monto como entero (céntimos) alineado a la derecha.

        Args:
            monto: Decimal o float
            digitos: ancho total (default 17 = 15 enteros + 2 decimales)

        Ej:
            1234.56 → '000000000123456'
        """
        if monto is None:
            monto = 0
        centimos = int(Decimal(str(monto)) * 100)
        return f"{centimos:0{digitos}d}"

    def _nombre_completo(self, empleado):
        """Nombre completo del empleado."""
        partes = [
            empleado.nombre or "",
            empleado.apellido_paterno or "",
            empleado.apellido_materno or "",
        ]
        return " ".join(p for p in partes if p).strip()

    def _monto_total(self):
        """Suma de neto_pagar de todas las nóminas del banco."""
        return sum(n.neto_pagar for n in self.nominas)