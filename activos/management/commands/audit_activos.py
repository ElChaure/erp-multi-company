# activos/management/commands/audit_activos.py
"""
Auditoría completa de activos fijos: muestra todos los campos,
detecta duplicados, compara con el listado esperado del Excel
y marca activos con datos sospechosos (de prueba, incompletos, etc.).

Uso:
    python manage.py audit_activos
    python manage.py audit_activos --empresa-id 1
    python manage.py audit_activos --exportar  # guarda CSV
"""
import csv
from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Q

from rrhh.models import Empresa
from activos.models import ActivoFijo, DepreciacionActivo


# Listado del Excel original (con sus montos de depreciación anual)
ACTIVOS_EXCEL = [
    # (nombre_excel, costo_anual_depreciacion)
    ("Concepta",                    Decimal("348633.19")),
    ("Alzadora tigra",              None),
    ("Grapadora",                   None),
    ("Dobladora",                   Decimal("22284.09")),
    ("Guillotina",                  Decimal("27700.00")),
    ("Cosedora",                    None),
    ("Equipos de computo",          None),
    ("Muebles y enseres",           None),
    ("Vehiculos y otros equipos",   None),
    ("Edificio (planta)",           None),
    ("Heidelberg Kord",             None),
    ("Heidelberg Gto",              None),
    ("Heidelberg Minerva 1/8",      None),
    ("Heidelberg Cylinder",         None),
    ("Sakurai Oliver",              None),
    ("Roland Parva",                None),
    ("Roland Rekord",               None),
    ("Muller Martini Grapadora",    None),
    ("Dobladora Heidelberg Stamfolder", None),
    ("Cosedora Ventura",            None),
    ("Empaquetadora Krause",        None),
    ("Fotolito",                    None),
]


class Command(BaseCommand):
    help = "Auditoría completa de activos fijos."

    def add_arguments(self, parser):
        parser.add_argument("--empresa-id", type=int, default=None)
        parser.add_argument("--exportar", action="store_true",
                            help="Exporta a CSV en el directorio actual.")

    def handle(self, *args, **options):
        emp_id = options["empresa_id"]
        if emp_id:
            empresa = Empresa.objects.filter(pk=emp_id, activa=True).first()
        else:
            empresa = Empresa.objects.filter(activa=True).first()
        if not empresa:
            self.stdout.write(self.style.ERROR("No hay empresas activas."))
            return

        self.stdout.write("=" * 80)
        self.stdout.write(f"  AUDITORÍA DE ACTIVOS FIJOS — {empresa.razon_social}")
        self.stdout.write(f"  Fecha: {date.today().strftime('%d/%m/%Y')}")
        self.stdout.write("=" * 80)

        activos = list(
            ActivoFijo.objects.filter(empresa=empresa)
            .select_related(
                "centro_costo", "cuenta_activo",
                "cuenta_gasto_depreciacion", "cuenta_depreciacion_acumulada",
            )
            .order_by("codigo")
        )

        self.stdout.write(f"\nTotal activos en BD: {len(activos)}\n")

        # ═══════════════════════════════════════════════════════
        #  1. Detalle completo de cada activo
        # ═══════════════════════════════════════════════════════
        self.stdout.write("=" * 80)
        self.stdout.write("  1. DETALLE DE ACTIVOS EN BD")
        self.stdout.write("=" * 80)

        for a in activos:
            self.stdout.write(f"\n  {a.codigo} — {a.nombre}")
            self.stdout.write(f"    Serial:          {a.serial or '—'}")
            self.stdout.write(f"    Fecha adq.:      {a.fecha_adquisicion}")
            self.stdout.write(f"    Inicio deprec.:  {a.fecha_inicio_depreciacion}")
            self.stdout.write(f"    Costo:           Bs. {a.costo_adquisicion:,.2f}")
            self.stdout.write(f"    Residual:        Bs. {a.valor_residual:,.2f}")
            self.stdout.write(f"    Vida útil:       {a.vida_util_anios} años")
            self.stdout.write(f"    Método:          {a.get_metodo_depreciacion_display()}")
            self.stdout.write(f"    Centro costo:    {a.centro_costo or '⚠ SIN CC'}")
            self.stdout.write(f"    Cuenta activo:   {a.cuenta_activo or '⚠ FALTA'}")
            self.stdout.write(f"    Gasto deprec.:   {a.cuenta_gasto_depreciacion or '⚠ FALTA'}")
            self.stdout.write(f"    Dep. acumulada:  {a.cuenta_depreciacion_acumulada or '⚠ FALTA'}")
            self.stdout.write(f"    Activo:          {'✓' if a.activo else '✗'}")
            total_dep = a.total_depreciado
            self.stdout.write(f"    Total deprec.:   Bs. {total_dep:,.2f}")
            self.stdout.write(f"    Valor libro:     Bs. {a.valor_libro:,.2f}")

        # ═══════════════════════════════════════════════════════
        #  2. Activos sospechosos
        # ═══════════════════════════════════════════════════════
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("  2. ACTIVOS SOSPECHOSOS")
        self.stdout.write("=" * 80)

        # 2.1 Prueba
        prueba = [a for a in activos if "prueba" in (a.nombre or "").lower()]
        if prueba:
            self.stdout.write(self.style.WARNING("\n  De prueba (borrar):"))
            for a in prueba:
                self.stdout.write(f"    ⚠ {a.codigo} — {a.nombre}")

        # 2.2 Sin CC
        sin_cc = [a for a in activos if not a.centro_costo_id]
        if sin_cc:
            self.stdout.write(self.style.WARNING("\n  Sin Centro de Costo:"))
            for a in sin_cc:
                self.stdout.write(f"    ⚠ {a.codigo} — {a.nombre}")

        # 2.3 Sin cuentas
        sin_cuentas = [
            a for a in activos
            if not a.cuenta_activo_id
            or not a.cuenta_gasto_depreciacion_id
            or not a.cuenta_depreciacion_acumulada_id
        ]
        if sin_cuentas:
            self.stdout.write(self.style.ERROR("\n  Sin cuentas contables (no se puede depreciar):"))
            for a in sin_cuentas:
                self.stdout.write(f"    ✘ {a.codigo} — {a.nombre}")

        # 2.4 Costo 0
        costo_cero = [a for a in activos if not a.costo_adquisicion or a.costo_adquisicion <= 0]
        if costo_cero:
            self.stdout.write(self.style.ERROR("\n  Costo = 0:"))
            for a in costo_cero:
                self.stdout.write(f"    ✘ {a.codigo} — {a.nombre}")

        # 2.5 Sin depreciación este año
        anio = date.today().year
        con_deprec = set(
            DepreciacionActivo.objects.filter(
                activo__empresa=empresa,
                fecha__year=anio,
            ).values_list("activo_id", flat=True)
        )
        sin_deprec = [
            a for a in activos
            if a.activo and a.id not in con_deprec and a.fecha_inicio_depreciacion <= date.today()
        ]
        if sin_deprec:
            self.stdout.write(self.style.WARNING(
                f"\n  Sin depreciación registrada en {anio}:"
            ))
            for a in sin_deprec:
                self.stdout.write(f"    ⚠ {a.codigo} — {a.nombre}")

        # ═══════════════════════════════════════════════════════
        #  3. Comparación con el listado del Excel
        # ═══════════════════════════════════════════════════════
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("  3. COMPARACIÓN CON EL LISTADO DEL EXCEL")
        self.stdout.write("=" * 80)

        def norm(s):
            return (s or "").strip().lower()

        # Palabras clave por activo del Excel para hacer matching flexible
        KEYWORDS_EXCEL = {
            "Concepta":                     ["concepta"],
            "Alzadora tigra":               ["alzadora", "tigra"],
            "Grapadora":                    ["grapadora"],
            "Dobladora":                    ["dobladora"],
            "Guillotina":                   ["guillotina"],
            "Cosedora":                     ["cosedora"],
            "Equipos de computo":           ["computo", "computadora", "equipo"],
            "Muebles y enseres":            ["mueble", "enseres"],
            "Vehiculos y otros equipos":    ["vehiculo", "camion", "equipo"],
            "Edificio (planta)":            ["edificio", "planta"],
            "Heidelberg Kord":              ["kord"],
            "Heidelberg Gto":               ["gto"],
            "Heidelberg Minerva 1/8":       ["minerva"],
            "Heidelberg Cylinder":          ["cylinder"],
            "Sakurai Oliver":               ["sakurai", "oliver"],
            "Roland Parva":                 ["parva"],
            "Roland Rekord":                ["rekord", "record"],
            "Muller Martini Grapadora":     ["muller", "martini"],
            "Dobladora Heidelberg Stamfolder": ["stamfolder"],
            "Cosedora Ventura":             ["ventura"],
            "Empaquetadora Krause":         ["krause"],
            "Fotolito":                     ["fotolito"],
        }

        # Matching flexible
        encontrados = []
        faltantes = []
        for nombre_excel, _costo in ACTIVOS_EXCEL:
            keywords = KEYWORDS_EXCEL.get(nombre_excel, [norm(nombre_excel)])
            match = None
            for a in activos:
                nombre_bd = norm(a.nombre)
                if any(kw in nombre_bd for kw in keywords):
                    match = a
                    break
            if match:
                encontrados.append((nombre_excel, match))
                self.stdout.write(self.style.SUCCESS(
                    f"  ✔ {nombre_excel:35s} → {match.codigo} — {match.nombre}"
                ))
            else:
                faltantes.append(nombre_excel)
                self.stdout.write(self.style.ERROR(
                    f"  ✘ {nombre_excel:35s} → FALTA"
                ))

        # Activos en BD que no matchean con ninguno del Excel
        matched_ids = {m.id for _, m in encontrados}
        extras = [a for a in activos if a.id not in matched_ids]
        if extras:
            self.stdout.write("\n  Activos en BD que NO matchean con el Excel:")
            for a in extras:
                self.stdout.write(f"    + {a.codigo} — {a.nombre}")

        # ═══════════════════════════════════════════════════════
        #  4. Resumen
        # ═══════════════════════════════════════════════════════
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("  RESUMEN")
        self.stdout.write("=" * 80)
        self.stdout.write(f"  Activos en BD:                     {len(activos)}")
        self.stdout.write(f"  Del Excel encontrados:             {len(encontrados)}/{len(ACTIVOS_EXCEL)}")
        self.stdout.write(f"  Del Excel faltantes:               {len(faltantes)}")
        self.stdout.write(f"  En BD pero no en Excel:            {len(extras)}")
        self.stdout.write(f"  Sin CC:                            {len(sin_cc)}")
        self.stdout.write(f"  Sin cuentas:                       {len(sin_cuentas)}")
        self.stdout.write(f"  Costo 0:                           {len(costo_cero)}")
        self.stdout.write(f"  De prueba:                         {len(prueba)}")
        self.stdout.write(f"  Sin deprec. este año:              {len(sin_deprec)}")

        # ═══════════════════════════════════════════════════════
        #  5. Exportar CSV (opcional)
        # ═══════════════════════════════════════════════════════
        if options["exportar"]:
            archivo = f"activos_auditoria_{date.today().isoformat()}.csv"
            with open(archivo, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "codigo", "nombre", "costo", "residual", "vida_util",
                    "cc", "cuenta_activo", "cuenta_gasto", "cuenta_dep_acum",
                    "activo", "total_depreciado", "valor_libro",
                ])
                for a in activos:
                    writer.writerow([
                        a.codigo,
                        a.nombre,
                        str(a.costo_adquisicion),
                        str(a.valor_residual),
                        a.vida_util_anios,
                        str(a.centro_costo or ""),
                        str(a.cuenta_activo or ""),
                        str(a.cuenta_gasto_depreciacion or ""),
                        str(a.cuenta_depreciacion_acumulada or ""),
                        a.activo,
                        str(a.total_depreciado),
                        str(a.valor_libro),
                    ])
            self.stdout.write(self.style.SUCCESS(f"\n  CSV exportado: {archivo}"))