"""
Generador de archivo TXT para pago de nómina de Banesco Banco Universal.

Formato: PAYMUL (EDIFACT D 95B)
Referencia: Manual Banesco de Pago de Nómina.

Estructura:
    - Registro de Control (HDR)
    - Registro de Encabezado (01)
    - Registro de Débito (02)
    - Registro de Detalle (03) — por empleado
    - Registro de Totales (99)
"""
from decimal import Decimal

from .base import BancoTXTGenerator


class BanescoTXTGenerator(BancoTXTGenerator):

    banco_nombre = "BANESCO"

    @property
    def codigo_banco(self):
        return "0134"

    def generar(self) -> str:
        lineas = []

        if not self.nominas.exists():
            raise ValueError(
                f"No hay empleados con banco Banesco en el periodo "
                f"{self.periodo.numero_periodo}/{self.periodo.anio}."
            )

        # Header
        lineas.append(self._header())

        # Encabezado de la orden de pago
        lineas.append(self._encabezado())

        # Débito a la cuenta matriz
        lineas.append(self._debito())

        # Detalles
        for nomina in self.nominas:
            lineas.append(self._detalle(nomina))

        # Totales
        lineas.append(self._totales())

        return "\r\n".join(lineas)

    # ═══════════════════════════════════════════════════════
    #  REGISTROS
    # ═══════════════════════════════════════════════════════

    def _header(self):
        """
        Registro de Control (HDR).

        Formato:
            HDR + 'BANESCO' (15) + 'E' + 'D 95B' (6) + 'PAYMUL' (6) + 'P'
        """
        return f"HDR{'BANESCO':<15}{'E'}{'D 95B':<6}{'PAYMUL':<6}{'P'}"

    def _encabezado(self):
        """
        Registro de Encabezado (01).

        Formato:
            01 + 'SAL' (3) + descripción (32) + '9' (3) +
            nro_orden (35) + fecha (14)
        """
        descripcion = (
            f"NOMINA {self.periodo.get_tipo_display().upper()} "
            f"#{self.periodo.numero_periodo}"
        )[:32]

        rif = (self.empresa.rif or "").replace("-", "").strip()
        nro_orden = f"{rif}-{self.periodo.id}-{self.periodo.numero_periodo}"[:35]

        fecha = self.periodo.fecha_pago.strftime("%Y%m%d%H%M%S")

        return (
            f"01"
            f"{'SAL':<3}"
            f"{descripcion:<32}"
            f"{'9':<3}"
            f"{nro_orden:<35}"
            f"{fecha:<14}"
        )

    def _debito(self):
        """
        Registro de Débito (02).

        Nota: requiere una cuenta matriz de la empresa.
        Si no está configurada, se usa un placeholder.
        """
        total = self._monto_total()
        total_str = self._fmt_monto(total, digitos=15)

        nro_referencia = f"NOM-{self.periodo.id}-{self.periodo.numero_periodo}"[:30]
        rif = (self.empresa.rif or "").replace("-", "")[:17]
        nombre = (
            self.empresa.nombre_comercial or self.empresa.razon_social or ""
        )[:35]

        # Cuenta matriz: campo opcional en Empresa.
        # Si no existe, se usa un placeholder (los usuarios lo sabrán al validar).
        cuenta_matriz = getattr(self.empresa, "cuenta_matriz", None) or "0" * 20
        cuenta_matriz = self._fmt_cuenta(cuenta_matriz)

        fecha_efectiva = self.periodo.fecha_pago.strftime("%Y%m%d")

        return (
            f"02"
            f"{nro_referencia:<30}"
            f"{rif:<17}"
            f"{nombre:<35}"
            f"{total_str}"
            f"VEF"
            f"{' '}"
            f"{cuenta_matriz:<34}"
            f"{'BANESCO':<11}"
            f"{fecha_efectiva}"
        )

    def _detalle(self, nomina):
        """
        Registro de Detalle (03) — por empleado.

        Formato:
            03 + forma_pago (1) + cédula (15) + cuenta (20) +
            monto (17) + nombre (35) + email (40)
        """
        empleado = nomina.empleado

        cedula = self._fmt_cedula(empleado)
        cuenta = self._fmt_cuenta(empleado.cuenta_bancaria)
        monto = self._fmt_monto(nomina.neto_pagar, digitos=17)
        nombre = self._nombre_completo(empleado)[:35]
        email = (empleado.email or "")[:40]

        return (
            f"03"
            f"{'1':<1}"            # Forma de pago: 1 = abono en cuenta
            f"{cedula:<15}"
            f"{cuenta:<20}"
            f"{monto}"
            f"{nombre:<35}"
            f"{email:<40}"
        )

    def _totales(self):
        """
        Registro de Totales (99).

        Formato:
            99 + cantidad (5) + monto_total (17)
        """
        total = self._monto_total()
        total_str = self._fmt_monto(total, digitos=17)
        cantidad = self.nominas.count()

        return f"99{cantidad:05d}{total_str}"