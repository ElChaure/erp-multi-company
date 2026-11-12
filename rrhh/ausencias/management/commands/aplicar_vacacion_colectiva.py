"""
Aplica una vacación colectiva previamente creada (en estado borrador).

La vacación colectiva genera:
    1. Una SolicitudAusencia por cada empleado del alcance.
    2. Un descuento del saldo correspondiente.
    3. Actualización del estatus a "aplicada".

Uso:
    python manage.py aplicar_vacacion_colectiva --vacacion-id 1
    python manage.py aplicar_vacacion_colectiva --vacacion-id 1 --dry-run
    python manage.py aplicar_vacacion_colectiva --listar-borradores
"""
from django.core.management.base import BaseCommand, CommandError

from rrhh.models import VacacionColectiva
from rrhh.ausencias.vacaciones_services import aplicar_vacacion_colectiva


class Command(BaseCommand):
    help = (
        "Aplica una vacación colectiva en estado borrador. "
        "Genera solicitudes individuales y descuenta saldos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--vacacion-id",
            type=int,
            help="ID de la VacacionColectiva a aplicar.",
        )
        parser.add_argument(
            "--listar-borradores",
            action="store_true",
            help="Lista las vacaciones colectivas en estado borrador.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra lo que haría, sin guardar cambios.",
        )

    def handle(self, *args, **options):
        vacacion_id = options.get("vacacion_id")
        listar = options["listar_borradores"]
        dry_run = options["dry_run"]

        # Listar borradores
        if listar:
            borradores = VacacionColectiva.objects.filter(
                estatus="borrador"
            ).select_related("empresa").order_by("-fecha_inicio")

            self.stdout.write(self.style.NOTICE(
                f"\n═══ Vacaciones colectivas en borrador ═══\n"
            ))

            if not borradores.exists():
                self.stdout.write(self.style.WARNING(
                    "No hay vacaciones colectivas en estado borrador."
                ))
                return

            for v in borradores:
                self.stdout.write(
                    f"  [{v.id}] {v.nombre}\n"
                    f"      Empresa: {v.empresa.razon_social}\n"
                    f"      Fechas: {v.fecha_inicio} al {v.fecha_fin}\n"
                    f"      Alcance: {v.get_alcance_display()}\n"
                    f"      Días hábiles: {v.dias_habiles}\n"
                    f"      Empleados en alcance: {v.total_empleados}\n"
                )
            return

        # Aplicar vacación
        if not vacacion_id:
            raise CommandError(
                "Debes especificar --vacacion-id N o --listar-borradores."
            )

        try:
            vacacion = VacacionColectiva.objects.select_related(
                "empresa", "sede", "departamento", "tipo_ausencia"
            ).get(pk=vacacion_id)
        except VacacionColectiva.DoesNotExist:
            raise CommandError(f"No existe la vacación colectiva con ID {vacacion_id}.")

        self.stdout.write(self.style.NOTICE(
            f"\n═══ Aplicando vacación colectiva ═══\n"
        ))
        self.stdout.write(f"Nombre: {vacacion.nombre}")
        self.stdout.write(f"Empresa: {vacacion.empresa.razon_social}")
        self.stdout.write(f"Fechas: {vacacion.fecha_inicio} al {vacacion.fecha_fin}")
        self.stdout.write(f"Alcance: {vacacion.get_alcance_display()}")
        self.stdout.write(f"Días hábiles: {vacacion.dias_habiles}")
        self.stdout.write(f"Estatus actual: {vacacion.get_estatus_display()}")
        self.stdout.write(f"Empleados en alcance: {vacacion.total_empleados}")
        self.stdout.write(f"Modo: {'DRY-RUN' if dry_run else 'REAL'}\n")

        if vacacion.estatus != "borrador":
            raise CommandError(
                f"Solo se pueden aplicar vacaciones en estado 'borrador'. "
                f"Esta está en '{vacacion.get_estatus_display()}'."
            )

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "  [DRY] Se generarían "
                f"{vacacion.total_empleados} solicitudes de vacaciones."
            ))
            self.stdout.write(self.style.WARNING(
                "\n💡 Ejecuta sin --dry-run para aplicar los cambios."
            ))
            return

        try:
            resultado = aplicar_vacacion_colectiva(vacacion)

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(
                f"  ✅ Total empleados: {resultado['total_empleados']}"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"  ✅ Solicitudes creadas: {resultado['solicitudes_creadas']}"
            ))

            if resultado["errores"]:
                self.stdout.write(self.style.ERROR(
                    f"  ❌ Errores: {len(resultado['errores'])}"
                ))
                for err in resultado["errores"][:20]:
                    self.stdout.write(self.style.ERROR(
                        f"      {err['empleado']}: {err['error']}"
                    ))

            self.stdout.write(self.style.SUCCESS(
                f"\n🎉 Vacación colectiva aplicada correctamente."
            ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"\n❌ Error al aplicar: {e}"
            ))
            raise