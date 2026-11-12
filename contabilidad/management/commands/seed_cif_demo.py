# contabilidad/management/commands/seed_cif_demo.py
"""
Carga la configuración de reparto de CIF para la Imprenta Municipal.

Crea/reutiliza:
- 16 centros de costo productivos (uno por máquina).
- La ConfiguracionCIF con driver AREA, pivot Roland Rekord, base 7000 cm².
- Los CentroCostoCIF con las áreas de cada máquina.

Uso:
    python manage.py seed_cif_demo --dry-run
    python manage.py seed_cif_demo --confirm
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from rrhh.models import Empresa
from contabilidad.models import (
    CentroCosto,
    ConfiguracionCIF,
    CentroCostoCIF,
)
from contabilidad.constants import (
    CC_PRODUCTIVO,
    DRIVER_AREA,
    METODO_PROPORCIONAL,
)


# Listado de las 16 máquinas con su área física (en cm²).
# Fuente: Excel SIC-IMPRENTA-MUNICIPAL, hoja MP, filas 69-78 + hojas de máquinas.
#
# Formato: (codigo_cc, nombre_cc, ancho_cm, alto_cm, es_pivot)
#
# Para las máquinas que no tienen dimensiones exactas en el Excel,
# usamos valores estimados según su categoría (offset grande ~7000,
# offset mediano ~4000, encuadernación ~3000, etc.).
MAQUINAS = [
    # ── OFFSET ──
    ("CC-CONCEPTA",       "Concepta",                        52,   66,  False),
    ("CC-KORD",           "Heidelberg Kord",                 46,   64,  False),
    ("CC-SAKURAI",        "Sakurai Oliver",                  52,   72,  False),
    ("CC-GTO",            "Heidelberg Gto",                  32,   46,  False),
    ("CC-PARVA",          "Roland Parva",                    59,   84,  False),
    ("CC-REKORD",         "Roland Rekord",                   70,  100,  True),   # PIVOT
    ("CC-MINERVA",        "Heidelberg Minerva 1/8",          24,   33,  False),
    ("CC-CYLINDER",       "Heidelberg Cylinder",             54,   72,  False),
    # ── ENCUADERNACIÓN ──
    ("CC-MORH",           "Guillotina Morh",                 70,  100,  False),
    ("CC-TIGRA",          "Alzadora Tigra",                  55,   80,  False),
    ("CC-MULLER",         "Muller Martini Grapadora",        60,   90,  False),
    ("CC-STAMFOLDER",     "Dobladora Heidelberg Stamfolder", 60,   80,  False),
    ("CC-VENTURA",        "Cosedora Ventura",                50,   70,  False),
    ("CC-KRAUSE",         "Empaquetadora Krause",            50,   70,  False),
    # ── PRE-PRENSA ──
    ("CC-FOTOLITO",       "Fotolito",                        60,   80,  False),
    # ── TRANSPORTE ──
    ("CC-VEHICULOS",      "Vehiculos y otros equipos",       60,   90,  False),
]


class Command(BaseCommand):
    help = "Carga la configuración CIF con las 16 máquinas de la imprenta."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--reset", action="store_true",
                            help="Borra la configuración CIF existente antes de crear.")

    def handle(self, *args, **options):
        confirm = options["confirm"]
        reset = options["reset"]

        empresa = Empresa.objects.filter(activa=True).first()
        if not empresa:
            self.stdout.write(self.style.ERROR("No hay empresas activas."))
            return

        self.stdout.write("=" * 70)
        self.stdout.write(f"  SEED CIF — {empresa.razon_social}")
        self.stdout.write("=" * 70)

        # ─── Verificar si ya existe configuración ───
        config_existente = ConfiguracionCIF.objects.filter(empresa=empresa).first()
        if config_existente:
            if not reset:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠ Ya existe una configuración CIF (ID {config_existente.id}). "
                    "Usa --reset para recrearla."
                ))
                return
            if not confirm:
                self.stdout.write(f"  [dry-run] Se borraría config existente ID {config_existente.id}")
            else:
                config_existente.delete()
                self.stdout.write(self.style.WARNING("  Config existente borrada"))

        # ─── Preparar datos ───
        datos = []
        for codigo, nombre, ancho, alto, es_pivot in MAQUINAS:
            area = Decimal(str(ancho)) * Decimal(str(alto))
            datos.append({
                "codigo": codigo,
                "nombre": nombre,
                "ancho": ancho,
                "alto": alto,
                "area": area,
                "es_pivot": es_pivot,
            })

        pivot = next((d for d in datos if d["es_pivot"]), None)
        if not pivot:
            self.stdout.write(self.style.ERROR("No hay pivot definido en MAQUINAS."))
            return

        base_pivot = pivot["area"]

        # ─── Mostrar preview ───
        self.stdout.write(f"\n  Pivot:  {pivot['nombre']} ({pivot['area']:.2f} cm²)")
        self.stdout.write(f"  Driver: {DRIVER_AREA}")
        self.stdout.write(f"\n  {'Código':<18} {'Nombre':<35} {'Área (cm²)':>12} {'Coef.':>10}")
        self.stdout.write("  " + "-" * 78)

        for d in datos:
            coef = d["area"] / base_pivot
            marca = " (PIVOT)" if d["es_pivot"] else ""
            self.stdout.write(
                f"  {d['codigo']:<18} {d['nombre']:<35} "
                f"{d['area']:>12.2f} {coef:>10.4f}{marca}"
            )

        # ─── Ejecutar ───
        if not confirm:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(
                "  Para ejecutar: python manage.py seed_cif_demo --confirm"
            )
            self.stdout.write("=" * 70)
            return

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("  EJECUTANDO...")
        self.stdout.write("=" * 70)

        with transaction.atomic():
            # ─── Crear/reutilizar los 16 centros de costo ───
            centros = {}
            for d in datos:
                cc, created = CentroCosto.objects.get_or_create(
                    empresa=empresa,
                    codigo=d["codigo"],
                    defaults={
                        "nombre": d["nombre"],
                        "tipo": CC_PRODUCTIVO,
                        "activo": True,
                        "capacidad_horas_mes": None,
                    },
                )
                if not created and cc.nombre != d["nombre"]:
                    cc.nombre = d["nombre"]
                    cc.save(update_fields=["nombre"])
                centros[d["codigo"]] = cc
                if created:
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✔ CC creado: {cc.codigo} - {cc.nombre}"
                    ))
                else:
                    self.stdout.write(f"  • CC existente: {cc.codigo} - {cc.nombre}")

            # ─── Crear la configuración CIF ───
            config = ConfiguracionCIF.objects.create(
                empresa=empresa,
                driver=DRIVER_AREA,
                centro_pivot=centros[pivot["codigo"]],
                base_pivot=base_pivot,
                metodo=METODO_PROPORCIONAL,
                activa=True,
                notas=(
                    f"Configuración inicial para la imprenta. "
                    f"Driver: AREA. Pivot: {pivot['nombre']} ({pivot['area']:.0f} cm²)."
                ),
            )
            self.stdout.write(self.style.SUCCESS(
                f"  ✔ Configuración CIF creada (ID {config.id})"
            ))

            # ─── Crear los CentroCostoCIF ───
            for d in datos:
                cdc = CentroCostoCIF.objects.create(
                    configuracion=config,
                    centro_costo=centros[d["codigo"]],
                    area_cm2=d["area"],
                    coeficiente_calculado=d["area"] / base_pivot,
                )
                marca = " (PIVOT)" if d["es_pivot"] else ""
                self.stdout.write(
                    f"  ✔ {cdc.centro_costo.codigo:<18} coef={cdc.coeficiente_calculado:.4f}{marca}"
                )

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS(
            f"  ✔ Configuración CIF cargada: {len(datos)} centros, pivot {pivot['nombre']}"
        ))
        self.stdout.write("=" * 70)