"""
Generador de archivo TXT para pago de nómina de BBVA Provincial.

Formato: ancho fijo, campos separados por espacios.
Referencia: Manual de Pago de Nómina de Provincial.

Estructura (una línea por empleado):
    cédula (13) + cuenta (20) + monto (13) + recibo (8) + nombre (40) + email (40)
"""
from .base import BancoTXTGenerator


class ProvincialTXTGenerator(BancoTXTGenerator):

    banco_nombre = "PROVINCIAL"

    @property
    def codigo_banco(self):
        return "0108"

    def generar(self) -> str:
        if not self.nominas.exists():
            raise ValueError(
                f"No hay empleados con banco Provincial en el periodo "
                f"{self.periodo.numero_periodo}/{self.periodo.anio}."
            )

        lineas = []
        for idx, nomina in enumerate(self.nominas, start=1):
            lineas.append(self._detalle(nomina, idx))

        return "\r\n".join(lineas)

    def _detalle(self, nomina, idx):
        """
        Línea de detalle.

        Formato:
            cédula (13) + ' ' + cuenta (20) + ' ' + monto (13) + ' ' +
            recibo (8) + ' ' + nombre (40) + ' ' + email (40)
        """
        empleado = nomina.empleado

        # Cédula: V + 11 dígitos (ej: V00000000009)
        cedula_raw = str(empleado.cedula).replace(".", "").replace(" ", "").strip()
        try:
            cedula = f"{empleado.nacionalidad}{int(cedula_raw):011d}"
        except (ValueError, TypeError):
            cedula = f"{empleado.nacionalidad}{cedula_raw:>11}"

        cuenta = self._fmt_cuenta(empleado.cuenta_bancaria)

        # Monto: 11 enteros + 2 decimales = 13 dígitos
        monto = self._fmt_monto(nomina.neto_pagar, digitos=13)

        # Nro recibo: 8 dígitos correlativos
        recibo = f"{idx:08d}"

        nombre = self._nombre_completo(empleado)[:40]
        email = (empleado.email or "")[:40]

        return (
            f"{cedula} {cuenta} {monto} {recibo} "
            f"{nombre:<40} {email}"
        )