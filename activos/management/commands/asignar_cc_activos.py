# activos/management/commands/asignar_cc_activos.py
"""
Asigna Centro de Costo a activos que no lo tienen.

Uso:
    python manage.py asignar_cc_activos --dry-run
    python manage.py asignar_cc_activos --confirm
"""
from django.core.management.base import BaseCommand
from rrhh.models import Empresa
from contabilidad.models import CentroCosto
from activos.models import ActivoFijo


# Activos que van a ADMINISTRATIVO (el resto va a PRODUCTIVO)
ACTIVOS_ADMIN = [
    "Vehiculos y otros equipos",
    "Camión de Reparto",  # por si el rename aún no se aplicó
]


class Command(BaseCommand):
    help = "Asigna CC a activos que no lo tienen."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **options):
        confirm = options["confirm"]
        empresa = Empresa.objects.filter(activa=True).first()
        if not empresa:
            self.stdout.write(self.style.ERROR("No hay empresas activas."))
            return

        cc_prod = CentroCosto.objects.filter(empresa=empresa, tipo="PRODUCTIVO", activo=True).first()
        cc_admin = CentroCosto.objects.filter(empresa=empresa, tipo="ADMINISTRATIVO", activo=True).first()

        if not cc_prod:
            self.stdout.write(self.style.ERROR(
                "No hay CentroCosto tipo PRODUCTIVO. Crea uno primero."
            ))
            return

        self.stdout.write("=" * 70)
        self.stdout.write(f"  ASIGNAR CC — {empresa.razon_social}")
        self.stdout.write(f"  PRODUCTIVO:   {cc_prod}")
        self.stdout.write(f"  ADMINISTRATIVO: {cc_admin or '(no existe, se usará PRODUCTIVO)'}")
        self.stdout.write("=" * 70)

        sin_cc = ActivoFijo.objects.filter(empresa=empresa, centro_costo__isnull=True)
        for a in sin_cc:
            cc = cc_admin if (cc_admin and a.nombre in ACTIVOS_ADMIN) else cc_prod
            if not confirm:
                self.stdout.write(f"  [dry-run] {a.codigo} → {cc}")
            else:
                a.centro_costo = cc
                a.save(update_fields=["centro_costo"])
                self.stdout.write(self.style.SUCCESS(f"  ✔ {a.codigo} → {cc}"))

        if not confirm:
            self.stdout.write(
                "\n  Para ejecutar: python manage.py asignar_cc_activos --confirm"
            )
        self.stdout.write("=" * 70)