# activos/management/commands/diag_activos_vs_excel.py
"""
Cruza los activos fijos del ERP contra el listado del Excel
SIC-IMPRENTA-MUNICIPAL y reporta faltantes.

Uso:
    python manage.py diag_activos_vs_excel --excel "ruta/al/archivo.xlsx"
    python manage.py diag_activos_vs_excel --excel "..." --hoja "CIF"
"""
import os
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from openpyxl import load_workbook

from rrhh.models import Empresa
from activos.models import ActivoFijo


# Listado extraído del Excel original (columna DESCRIPCION de la hoja CIF)
# Estos son los nombres que esperamos encontrar.
ACTIVOS_ESPERADOS = [
    "Concepta",
    "Alzadora tigra",
    "Grapadora",
    "Dobladora",
    "Guillotina",
    "Cosedora",
    "Equipos de computo",
    "Muebles y enseres",
    "Vehiculos y otros equipos",
    "Edificio (planta)",
    "Heidelberg Kord",
    "Heidelberg Gto",
    "Heidelberg Minerva",
    "Heidelberg Cylinder",
    "Sakurai Oliver",
    "Roland Parva",
    "Roland Rekord",
    "Muller Martini Grapadora",
    "Dobladora Heidelberg Stamfolder",
    "Cosedora Ventura",
    "Empaquetadora Krause",
    "Fotolito",
]


class Command(BaseCommand):
    help = "Cruza los activos del ERP contra el listado esperado del Excel."

    def add_arguments(self, parser):
        parser.add_argument("--excel", type=str, default=None,
                            help="Ruta opcional al .xlsx (si quieres leer los montos).")
        parser.add_argument("--hoja", type=str, default="CIF",
                            help="Hoja del Excel a leer (por defecto CIF).")
        parser.add_argument("--empresa-id", type=int, default=None,
                            help="ID de empresa. Si se omite, usa la primera activa.")

    def handle(self, *args, **options):
        # ─── Empresa ───
        emp_id = options["empresa_id"]
        if emp_id:
            empresa = Empresa.objects.filter(pk=emp_id, activa=True).first()
        else:
            empresa = Empresa.objects.filter(activa=True).first()
        if not empresa:
            raise CommandError("No hay empresas activas.")

        self.stdout.write("=" * 70)
        self.stdout.write(f"  DIAGNÓSTICO ACTIVOS — {empresa.razon_social}")
        self.stdout.write("=" * 70)

        # ─── Activos en BD ───
        activos_bd = list(
            ActivoFijo.objects.filter(empresa=empresa)
            .order_by("nombre")
        )
        self.stdout.write(f"\nActivos en BD: {len(activos_bd)}")

        # ─── Comparación por nombre normalizado ───
        def norm(s):
            return (s or "").strip().lower()

        bd_nombres = {norm(a.nombre): a for a in activos_bd}

        self.stdout.write("\n=== Comparación contra listado esperado ===")
        faltantes = []
        encontrados = []

        for nombre_esperado in ACTIVOS_ESPERADOS:
            clave = norm(nombre_esperado)
            activo = bd_nombres.get(clave)
            if not activo:
                # Búsqueda parcial por si el nombre difiere un poco
                candidatos = [
                    a for a in activos_bd
                    if clave in norm(a.nombre) or norm(a.nombre) in clave
                ]
                if candidatos:
                    activo = candidatos[0]
                    self.stdout.write(self.style.WARNING(
                        f"  ≈ {nombre_esperado} → encontrado como '{activo.nombre}' (coincidencia parcial)"
                    ))
                else:
                    self.stdout.write(self.style.ERROR(f"  ✘ {nombre_esperado} → FALTA"))
                    faltantes.append(nombre_esperado)
                    continue
            else:
                self.stdout.write(self.style.SUCCESS(f"  ✔ {nombre_esperado}"))
            encontrados.append((nombre_esperado, activo))

        # ─── Activos en BD no listados en el esperado ───
        nombres_esperados_norm = {norm(n) for n in ACTIVOS_ESPERADOS}
        extras = [
            a for a in activos_bd
            if norm(a.nombre) not in nombres_esperados_norm
        ]
        if extras:
            self.stdout.write("\n=== Activos en BD NO listados en el esperado ===")
            for a in extras:
                self.stdout.write(f"  + {a.codigo} - {a.nombre}")

        # ─── Leer montos del Excel (opcional) ───
        if options["excel"]:
            ruta = options["excel"]
            if not os.path.exists(ruta):
                raise CommandError(f"Archivo no encontrado: {ruta}")

            self.stdout.write("\n=== Lectura de montos desde Excel ===")
            try:
                wb = load_workbook(ruta, data_only=True)
                ws = wb[options["hoja"]]
                # La columna de costo-anual está en L (12), fila 4 en adelante
                montos_excel = {}
                for row in range(4, 14):
                    nombre_cell = ws.cell(row=row, column=4).value  # D
                    monto_cell = ws.cell(row=row, column=12).value  # L
                    if nombre_cell:
                        montos_excel[norm(nombre_cell)] = monto_cell

                self.stdout.write(f"  Montos leídos: {len(montos_excel)} filas")

                # Comparar con activos en BD
                for nombre_esperado, activo in encontrados:
                    clave = norm(nombre_esperado)
                    monto_excel = montos_excel.get(clave)
                    if monto_excel is not None:
                        costo_bd = activo.costo_adquisicion
                        if abs(Decimal(str(monto_excel)) - costo_bd) > Decimal("1"):
                            self.stdout.write(self.style.WARNING(
                                f"  ⚠ {activo.nombre}: Excel={monto_excel} vs BD={costo_bd}"
                            ))

                wb.close()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error leyendo Excel: {e}"))

        # ─── Resumen final ───
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("  RESUMEN")
        self.stdout.write("=" * 70)
        self.stdout.write(f"  Encontrados: {len(encontrados)}/{len(ACTIVOS_ESPERADOS)}")
        if faltantes:
            self.stdout.write(self.style.ERROR(f"  Faltantes:  {len(faltantes)}"))
            for f in faltantes:
                self.stdout.write(self.style.ERROR(f"    - {f}"))
        else:
            self.stdout.write(self.style.SUCCESS("  ✔ Todos los activos esperados están cargados"))
        self.stdout.write("")