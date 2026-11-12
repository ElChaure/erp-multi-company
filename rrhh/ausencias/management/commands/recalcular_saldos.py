"""
Recalcula los saldos de vacaciones existentes.

Útil cuando:
    - Cambia la configuración de la empresa (ej: nuevo contrato colectivo)
    - Se corrigen fechas de ingreso
    - Se detectan saldos mal calculados

Uso:
    python manage.py recalcular_saldos --anio 2026
    python manage.py recalcular_saldos --anio 2026 --empresa-id 1
    python manage.py recalcular_saldos --anio 2026 --empleado-id 5
    python manage.py recalcular_saldos --todos-los-anios
    python manage.py recalcular_saldos --dry-run
"""
from django.core.management.base import BaseCommand, CommandError

from rrhh.models import Empleado, Empresa, SaldoVacaciones
from rrhh.ausencias.vacaciones_services import recalcular_saldo


class Command(BaseCommand):
    help = "Recalcula los días de derecho de los saldos de vacaciones existentes."

    def add_arguments(self, parser):
        parser.add_argument("--anio", type=int, help="Año específico a recalcular.")
        parser.add_argument("--empresa-id", type=int)
        parser.add_argument("--empleado-id", type=int)
        parser.add_argument(
            "--todos-los-anios",
            action="store_true",
            help="Recalcular todos los años de los empleados filtrados.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra lo que haría, sin guardar cambios.",
        )

    def handle(self, *args, **options):
        anio = options.get("anio")
        empresa_id = options.get("empresa_id")
        empleado_id = options.get("empleado_id")
        todos_anios = options["todos_los_anios"]
        dry_run = options["dry_run"]

        if not (anio or todos_anios):
            raise CommandError("Debes especificar --anio N o --todos-los-anios.")

        # Queryset base
        qs = SaldoVacaciones.objects.select_related("empleado", "empleado__empresa")

        if empleado_id:
            qs = qs.filter(empleado_id=empleado_id)
        elif empresa_id:
            qs = qs.filter(empleado__empresa_id=empresa_id)

        if anio:
            qs = qs.filter(anio=anio)

        qs = qs.order_by("empleado__apellido_paterno", "empleado__nombre", "anio")

        total = qs.count()

        self.stdout.write(self.style.NOTICE(
            f"\n═══ Recálculo de saldos de vacaciones ═══"
        ))
        self.stdout.write(f"Saldos a procesar: {total}")
        self.stdout.write(
            f"Modo: {'DRY-RUN' if dry_run else 'REAL'}\n"
        )

        if total == 0:
            self.stdout.write(self.style.WARNING(
                "No hay saldos que coincidan con los filtros."
            ))
            return

        exitosos = 0
        errores = 0

        for saldo in qs:
            try:
                dias_antes = saldo.dias_derecho

                if dry_run:
                    self.stdout.write(
                        f"  [DRY] {saldo.empleado.numero_empleado} - "
                        f"{saldo.anio} (derecho actual: {dias_antes})"
                    )
                    exitosos += 1
                    continue

                recalcular_saldo(saldo)
                dias_despues = saldo.dias_derecho

                if dias_antes != dias_despues:
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✅ {saldo.empleado.numero_empleado} - "
                        f"{saldo.anio}: {dias_antes} → {dias_despues}"
                    ))
                else:
                    self.stdout.write(
                        f"  · {saldo.empleado.numero_empleado} - "
                        f"{saldo.anio}: sin cambios ({dias_despues})"
                    )
                exitosos += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"  ❌ {saldo.empleado.numero_empleado} - {saldo.anio}: {e}"
                ))
                errores += 1

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("═══ Resumen ═══"))
        self.stdout.write(f"  Exitosos: {exitosos}")
        self.stdout.write(f"  Errores:  {errores}")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n💡 Ejecuta sin --dry-run para guardar los cambios."
            ))