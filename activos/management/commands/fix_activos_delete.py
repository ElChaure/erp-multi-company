# activos/management/commands/fix_activos_delete.py
"""
Borra activos fijos que no están en el listado oficial.

Uso:
    python manage.py fix_activos_delete --dry-run
    python manage.py fix_activos_delete --confirm
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from rrhh.models import Empresa
from activos.models import ActivoFijo, DepreciacionActivo


CODIGOS_A_BORRAR = [
    "AF-001",       # Máquina de Prueba
    "AF-IMP-006",   # Encuadernadora Industrial
    "AF-IMP-009",   # Servidor de Red
    "AF-IMP-010",   # Aire Acondicionado Central
]


class Command(BaseCommand):
    help = "Borra activos fijos que no están en el listado oficial."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **options):
        confirm = options["confirm"]
        empresa = Empresa.objects.filter(activa=True).first()
        if not empresa:
            self.stdout.write(self.style.ERROR("No hay empresas activas."))
            return

        self.stdout.write("=" * 70)
        self.stdout.write(f"  BORRAR ACTIVOS — {empresa.razon_social}")
        self.stdout.write("=" * 70)

        for codigo in CODIGOS_A_BORRAR:
            try:
                activo = ActivoFijo.objects.get(empresa=empresa, codigo=codigo)
            except ActivoFijo.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"  ⚠ {codigo} — NO existe (nada que borrar)"))
                continue

            deprecs = DepreciacionActivo.objects.filter(activo=activo).count()
            self.stdout.write(f"\n  {codigo} — {activo.nombre}")
            self.stdout.write(f"    Costo:          Bs. {activo.costo_adquisicion:,.2f}")
            self.stdout.write(f"    Depreciaciones: {deprecs}")

            if not confirm:
                self.stdout.write(self.style.WARNING("    [dry-run] Se borraría"))
            else:
                with transaction.atomic():
                    activo.delete()
                self.stdout.write(self.style.SUCCESS("    ✔ BORRADO"))

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(
            "  Para ejecutar: python manage.py fix_activos_delete --confirm"
            if not confirm else "  ✔ Borrado completado"
        )
        self.stdout.write("=" * 70)