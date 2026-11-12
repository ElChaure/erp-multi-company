# activos/management/commands/import_activos_excel.py
"""
Crea los activos fijos faltantes del listado oficial del Excel.

Uso:
    python manage.py import_activos_excel --dry-run
    python manage.py import_activos_excel --confirm
"""
from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from rrhh.models import Empresa
from contabilidad.models import PlanCuenta, CentroCosto
from activos.models import ActivoFijo
from activos.constants import METODOS_DEPRECIACION  # ajusta si tu módulo tiene otro nombre


# Plantilla de los activos a crear.
# Los montos son estimados; se pueden editar luego desde el admin.
ACTIVOS_NUEVOS = [
    # codigo,       nombre,                              tipo,        costo,      vida,  cc_sugerido
    ("AF-IMP-011", "Heidelberg Gto",                     "offset",    Decimal("60000"),  10, "PRODUCTIVO"),
    ("AF-IMP-012", "Roland Parva",                       "offset",    Decimal("50000"),  10, "PRODUCTIVO"),
    ("AF-IMP-013", "Roland Rekord",                      "offset",    Decimal("120000"), 15, "PRODUCTIVO"),
    ("AF-IMP-014", "Heidelberg Minerva 1/8",             "tipografia",Decimal("30000"),  10, "PRODUCTIVO"),
    ("AF-IMP-015", "Heidelberg Cylinder",                "tipografia",Decimal("70000"),  15, "PRODUCTIVO"),
    ("AF-IMP-016", "Alzadora Tigra",                     "encuad",    Decimal("25000"),  10, "PRODUCTIVO"),
    ("AF-IMP-017", "Muller Martini Grapadora",           "encuad",    Decimal("45000"),  10, "PRODUCTIVO"),
    ("AF-IMP-018", "Dobladora Heidelberg Stamfolder",    "encuad",    Decimal("35000"),  10, "PRODUCTIVO"),
    ("AF-IMP-019", "Cosedora Ventura",                   "encuad",    Decimal("20000"),  10, "PRODUCTIVO"),
    ("AF-IMP-020", "Empaquetadora Krause",               "empaque",   Decimal("15000"),  10, "PRODUCTIVO"),
    ("AF-IMP-021", "Fotolito",                           "preprensa", Decimal("18000"),   8, "PRODUCTIVO"),
    # Nota: "Heidelberg Kord" y "Vehiculos y otros equipos" ya se cubren con rename.
]


class Command(BaseCommand):
    help = "Crea activos fijos faltantes del listado oficial."

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
        self.stdout.write(f"  CREAR ACTIVOS — {empresa.razon_social}")
        self.stdout.write("=" * 70)

        # ─── Resolver cuentas por defecto ───
        cuenta_activo = PlanCuenta.objects.filter(
            empresa=empresa, codigo__startswith="120101", activa=True
        ).first()
        cuenta_gasto = PlanCuenta.objects.filter(
            empresa=empresa, codigo__startswith="610202", activa=True
        ).first() or PlanCuenta.objects.filter(
            empresa=empresa, codigo__startswith="5105", activa=True
        ).first()
        cuenta_dep_acum = PlanCuenta.objects.filter(
            empresa=empresa, codigo__startswith="120102", activa=True
        ).first()

        if not (cuenta_activo and cuenta_gasto and cuenta_dep_acum):
            self.stdout.write(self.style.ERROR(
                "Faltan cuentas contables para activos:\n"
                f"  cuenta_activo: {cuenta_activo}\n"
                f"  cuenta_gasto:  {cuenta_gasto}\n"
                f"  cuenta_dep_acum: {cuenta_dep_acum}\n"
                "Crea las cuentas 120101, 610202 y 120102 primero."
            ))
            return

        self.stdout.write(f"\n  Cuenta activo:    {cuenta_activo}")
        self.stdout.write(f"  Cuenta gasto:     {cuenta_gasto}")
        self.stdout.write(f"  Cuenta dep. acum: {cuenta_dep_acum}")

        # ─── Resolver centros de costo ───
        centros = {
            cc.tipo: cc
            for cc in CentroCosto.objects.filter(empresa=empresa, activo=True)
        }
        if not centros:
            self.stdout.write(self.style.ERROR(
                "No hay centros de costo activos. Crea al menos uno primero."
            ))
            return

        self.stdout.write(f"\n  Centros disponibles: {[str(c) for c in centros.values()]}")

        # ─── Crear ───
        self.stdout.write("\n" + "-" * 70)
        creados = 0
        existentes = 0

        for codigo, nombre, tipo, costo, vida, cc_sugerido in ACTIVOS_NUEVOS:
            # Verificar si ya existe
            if ActivoFijo.objects.filter(empresa=empresa, codigo=codigo).exists():
                self.stdout.write(self.style.WARNING(
                    f"  ⚠ {codigo} — ya existe, saltando"
                ))
                existentes += 1
                continue

            # CC: buscar PRODUCTIVO o cualquier activo
            cc = centros.get(cc_sugerido) or centros.get("PRODUCTIVO") or list(centros.values())[0]

            if not confirm:
                self.stdout.write(
                    f"  [dry-run] {codigo}: {nombre} — Bs. {costo:,.2f} / {vida} años → {cc}"
                )
            else:
                with transaction.atomic():
                    ActivoFijo.objects.create(
                        empresa=empresa,
                        codigo=codigo,
                        nombre=nombre,
                        descripcion=f"Importado del listado oficial (tipo: {tipo})",
                        fecha_adquisicion=date.today(),
                        fecha_inicio_depreciacion=date.today(),
                        costo_adquisicion=costo,
                        valor_residual=costo * Decimal("0.10"),
                        vida_util_anios=vida,
                        metodo_depreciacion="LINEA_RECTA",
                        tasa_anual=(Decimal("100") / Decimal(str(vida))).quantize(Decimal("0.01")),
                        cuenta_activo=cuenta_activo,
                        cuenta_gasto_depreciacion=cuenta_gasto,
                        cuenta_depreciacion_acumulada=cuenta_dep_acum,
                        centro_costo=cc,
                        activo=True,
                    )
                self.stdout.write(self.style.SUCCESS(
                    f"  ✔ {codigo}: {nombre} — Bs. {costo:,.2f} / {vida} años → {cc}"
                ))
            creados += 1

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(f"  Creados: {creados} | Existentes: {existentes}")
        if not confirm:
            self.stdout.write(
                "\n  Para ejecutar: python manage.py import_activos_excel --confirm"
            )
        self.stdout.write("=" * 70)