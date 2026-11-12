"""
Recalcula los saldos acumulados de prestaciones sociales.

Uso:
    python manage.py recalcular_prestaciones
    python manage.py recalcular_prestaciones --empresa-id 1
    python manage.py recalcular_prestaciones --empleado-id 5
    python manage.py recalcular_prestaciones --solo-activos
    python manage.py recalcular_prestaciones --dry-run

Se ejecuta típicamente:
    - Después de cargar/actualizar salarios
    - Cuando cambia la jurisprudencia
    - Para refrescar saldos antes de liquidar
"""
from django.core.management.base import BaseCommand, CommandError

from rrhh.models import Empleado, ParametroNomina
from rrhh.prestaciones.services import recalcular_prestacion


class Command(BaseCommand):
    help = "Recalcula saldos de prestaciones sociales de los empleados."

    def add_arguments(self, parser):
        parser.add_argument("--empresa-id", type=int)
        parser.add_argument("--empleado-id", type=int)
        parser.add_argument(
            "--solo-activos",
            action="store_true",
            help="Solo procesar empleados con estatus='activo'.",
        )
        parser.add_argument(
            "--incluir-liquidados",
            action="store_true",
            help="Incluir empleados con prestación ya liquidada.",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        empleados = Empleado.objects.all()

        if options.get("empleado_id"):
            empleados = empleados.filter(pk=options["empleado_id"])
            if not empleados.exists():
                raise CommandError(
                    f"No existe el empleado con ID {options['empleado_id']}."
                )
        elif options.get("empresa_id"):
            empleados = empleados.filter(empresa_id=options["empresa_id"])

        if options["solo_activos"]:
            empleados = empleados.filter(estatus="activo")

        if not options["incluir_liquidados"]:
            # Excluir prestaciones ya liquidadas
            empleados = empleados.exclude(
                prestacion_social__estatus="liquidada"
            )

        empleados = empleados.select_related("empresa").order_by(
            "empresa__razon_social", "numero_empleado"
        )

        total = empleados.count()
        self.stdout.write(self.style.NOTICE(
            f"\n═══ Recalculando prestaciones ({total} empleados) ═══\n"
        ))

        if not total:
            self.stdout.write(self.style.WARNING("Sin empleados que procesar."))
            return

        exitosos = 0
        errores = 0

        for empleado in empleados:
            try:
                if options["dry_run"]:
                    self.stdout.write(
                        f"  [DRY] {empleado.numero_empleado} - "
                        f"{empleado.nombre_completo}"
                    )
                    exitosos += 1
                    continue

                parametros = ParametroNomina.objects.filter(
                    empresa=empleado.empresa,
                    anio=empleado.fecha_ingreso.year,
                    activo=True,
                ).first()

                prestacion = recalcular_prestacion(empleado, parametros)

                self.stdout.write(self.style.SUCCESS(
                    f"  ✅ {empleado.numero_empleado} - "
                    f"{empleado.nombre_completo} → "
                    f"Saldo Bs. {prestacion.saldo_total_ves:,.2f} "
                    f"(retroactivo Bs. {prestacion.ultimo_retroactivo:,.2f}, "
                    f"método: {prestacion.ultimo_metodo_aplicado})"
                ))
                exitosos += 1

            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(
                    f"  ❌ {empleado.numero_empleado}: {e}"
                ))

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE(
            f"Exitosos: {exitosos} | Errores: {errores}"
        ))