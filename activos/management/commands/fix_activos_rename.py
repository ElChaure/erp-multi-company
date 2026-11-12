# activos/management/commands/fix_activos_rename.py
"""
Renombra activos fijos para alinear con el listado oficial del Excel.

Uso:
    python manage.py fix_activos_rename --dry-run
    python manage.py fix_activos_rename --confirm
"""
from django.core.management.base import BaseCommand
from rrhh.models import Empresa
from activos.models import ActivoFijo


# (codigo_actual, nombre_actual, nombre_nuevo)
RENAMES = [
    ("AF-IMP-001", "Impresora Concepta",              "Concepta"),
    ("AF-IMP-002", "Heidelberg Speedmaster",          "Heidelberg Kord"),
    ("AF-IMP-004", "Guillotina Polar",                "Guillotina Morh"),
    ("AF-IMP-008", "Camión de Reparto",               "Vehiculos y otros equipos"),
]


class Command(BaseCommand):
    help = "Renombra activos fijos para alinear con el listado oficial."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True,
                            help="Muestra qué haría sin ejecutar (default).")
        parser.add_argument("--confirm", action="store_true",
                            help="Ejecuta los cambios.")

    def handle(self, *args, **options):
        confirm = options["confirm"]
        empresa = Empresa.objects.filter(activa=True).first()
        if not empresa:
            self.stdout.write(self.style.ERROR("No hay empresas activas."))
            return

        self.stdout.write("=" * 70)
        self.stdout.write(f"  RENOMBRAR ACTIVOS — {empresa.razon_social}")
        self.stdout.write("=" * 70)

        cambios = 0
        errores = 0

        for codigo, nombre_actual, nombre_nuevo in RENAMES:
            try:
                activo = ActivoFijo.objects.get(empresa=empresa, codigo=codigo)
            except ActivoFijo.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"  ✘ {codigo} — NO existe"))
                errores += 1
                continue

            if activo.nombre != nombre_actual:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠ {codigo} — nombre en BD: '{activo.nombre}' "
                    f"(esperado '{nombre_actual}'). Se renombra de todas formas."
                ))

            if not confirm:
                self.stdout.write(
                    f"  [dry-run] {codigo}: '{activo.nombre}' → '{nombre_nuevo}'"
                )
            else:
                activo.nombre = nombre_nuevo
                activo.save(update_fields=["nombre", "updated_at"] if hasattr(activo, "updated_at") else ["nombre"])
                self.stdout.write(self.style.SUCCESS(
                    f"  ✔ {codigo}: '{nombre_actual}' → '{nombre_nuevo}'"
                ))
            cambios += 1

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(f"  {'CONFIRMADOS' if confirm else 'SIMULADOS'}: {cambios}")
        if errores:
            self.stdout.write(self.style.ERROR(f"  Errores: {erros if 'erros' in dir() else errores}"))
        if not confirm:
            self.stdout.write(
                "\n  Para ejecutar: python manage.py fix_activos_rename --confirm"
            )
        self.stdout.write("=" * 70)