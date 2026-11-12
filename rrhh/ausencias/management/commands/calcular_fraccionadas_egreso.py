"""
Calcula las vacaciones fraccionadas de un empleado al egreso.

Según LOTTT Art. 196, cuando el trabajador egresa antes de completar
el año de servicio, tiene derecho a vacaciones y bono vacacional
fraccionados (proporcionales a los meses completos trabajados desde
su último aniversario).

Uso:
    python manage.py calcular_fraccionadas_egreso --empleado-id 5
    python manage.py calcular_fraccionadas_egreso --empleado-id 5 --fecha-egreso 2026-10-31
    python manage.py calcular_fraccionadas_egreso --empleado-id 5 --dry-run
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from rrhh.models import Empleado
from rrhh.ausencias.vacaciones_services import calcular_fraccionadas_al_egreso


class Command(BaseCommand):
    help = (
        "Calcula las vacaciones fraccionadas de un empleado al egreso "
        "(para liquidación)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--empleado-id",
            type=int,
            required=True,
            help="ID del empleado.",
        )
        parser.add_argument(
            "--fecha-egreso",
            type=str,
            help="Fecha de egreso en formato YYYY-MM-DD (default: hoy o la del empleado).",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        empleado_id = options["empleado_id"]
        fecha_egreso_str = options.get("fecha_egreso")
        dry_run = options["dry_run"]

        try:
            empleado = Empleado.objects.select_related("empresa").get(
                pk=empleado_id
            )
        except Empleado.DoesNotExist:
            raise CommandError(f"No existe el empleado con ID {empleado_id}.")

        # Determinar fecha de egreso
        if fecha_egreso_str:
            try:
                fecha_egreso = date.fromisoformat(fecha_egreso_str)
            except ValueError:
                raise CommandError(
                    f"Formato de fecha inválido: {fecha_egreso_str}. "
                    f"Usa YYYY-MM-DD."
                )
        else:
            fecha_egreso = empleado.fecha_egreso or date.today()

        # Encabezado
        self.stdout.write(self.style.NOTICE(
            f"\n═══ Vacaciones fraccionadas al egreso ═══\n"
        ))
        self.stdout.write(f"Empleado: {empleado.numero_empleado} - "
                          f"{empleado.nombre_completo}")
        self.stdout.write(f"Empresa: {empleado.empresa.razon_social}")
        self.stdout.write(f"Fecha de ingreso: {empleado.fecha_ingreso}")
        self.stdout.write(f"Fecha de egreso: {fecha_egreso}")
        self.stdout.write(f"Modo: {'DRY-RUN' if dry_run else 'REAL'}\n")

        try:
            calculo = calcular_fraccionadas_al_egreso(empleado, fecha_egreso)

            self.stdout.write(self.style.NOTICE("─── Cálculo ───"))
            self.stdout.write(
                f"  Último aniversario: {calculo['ultimo_aniversario']}"
            )
            self.stdout.write(
                f"  Meses completos desde el último aniversario: "
                f"{calculo['meses_fraccion']}"
            )
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(
                f"  Días de vacaciones fraccionadas: "
                f"{calculo['dias_vacaciones_fraccionadas']}"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"  Días de bono vacacional fraccionado: "
                f"{calculo['dias_bono_fraccionados']}"
            ))

            # Sugerencia de monto (si quieres calcular el valor)
            # Esto requiere el salario diario, que se puede calcular así:
            salario_diario = Decimal(str(empleado.salario_base)) / Decimal("30")
            monto_vac = calculo["dias_vacaciones_fraccionadas"] * salario_diario
            monto_bono = calculo["dias_bono_fraccionados"] * salario_diario

            self.stdout.write("")
            self.stdout.write(self.style.NOTICE("─── Montos estimados ───"))
            self.stdout.write(
                f"  Salario diario (base): Bs. {salario_diario:,.2f}"
            )
            self.stdout.write(
                f"  Vacaciones fraccionadas: Bs. {monto_vac:,.2f}"
            )
            self.stdout.write(
                f"  Bono vacacional fraccionado: Bs. {monto_bono:,.2f}"
            )
            self.stdout.write(self.style.SUCCESS(
                f"  TOTAL a pagar: Bs. {monto_vac + monto_bono:,.2f}"
            ))

            if dry_run:
                self.stdout.write(self.style.WARNING(
                    "\n💡 Este comando es informativo. No guarda cambios."
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"\n❌ Error al calcular: {e}"
            ))
            raise