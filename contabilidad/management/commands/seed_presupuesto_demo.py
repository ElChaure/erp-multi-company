# contabilidad/management/commands/seed_presupuesto_demo.py
"""
Comando de management para poblar un presupuesto demo realista
en la empresa indicada (por defecto, la primera empresa activa).

Uso:
    python manage.py seed_presupuesto_demo
    python manage.py seed_presupuesto_demo --empresa-id 2
    python manage.py seed_presupuesto_demo --anio 2026 --nombre "Presupuesto Operativo 2026"
    python manage.py seed_presupuesto_demo --reset  # borra el presupuesto demo si ya existe
"""
from decimal import Decimal
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from rrhh.models import Empresa
from contabilidad.models import (
    EjercicioFiscal,
    PlanCuenta,
    CentroCosto,
    Presupuesto,
    PresupuestoLinea,
)


# ─────────────────────────────────────────────────────────────
#  PLAN DE CUENTAS DEMO (código → nombre, tipo, naturaleza)
#  Solo se crean las que no existan. Si ya hay un plan cargado,
#  se reutiliza el existente.
# ─────────────────────────────────────────────────────────────
CUENTAS_DEMO = [
    # (codigo, nombre, tipo, naturaleza)
    ("410101", "Ingresos por Servicios", "INGRESO", "A"),
    ("410102", "Ingresos por Suscripciones", "INGRESO", "A"),
    ("510101", "Sueldos y Salarios", "GASTO", "D"),
    ("510102", "Cestaticket", "GASTO", "D"),
    ("510103", "Aportes Patronales", "GASTO", "D"),
    ("510201", "Servicios Básicos", "GASTO", "D"),
    ("510202", "Alquiler de Oficina", "GASTO", "D"),
    ("510203", "Internet y Telecomunicaciones", "GASTO", "D"),
    ("510301", "Materiales de Oficina", "GASTO", "D"),
    ("510302", "Software y Licencias", "GASTO", "D"),
    ("510401", "Publicidad y Marketing", "GASTO", "D"),
    ("510501", "Depreciación de Activos", "GASTO", "D"),
    ("610101", "Servicios Profesionales", "GASTO", "D"),
    ("610201", "Mantenimiento", "GASTO", "D"),
]

# ─────────────────────────────────────────────────────────────
#  CENTROS DE COSTO DEMO
# ─────────────────────────────────────────────────────────────
CENTROS_DEMO = [
    ("CC-ADMIN", "Administración", "ADMINISTRATIVO", 160),
    ("CC-VENTAS", "Ventas y Marketing", "ADMINISTRATIVO", 160),
    ("CC-TECH", "Producción / Tecnología", "PRODUCTIVO", 180),
]


# ─────────────────────────────────────────────────────────────
#  PRESUPUESTO DEMO
#  Estructura: {(codigo_cuenta, codigo_cc): [12 montos mensuales]}
#  Los montos son Decimal("...") con separador punto.
#  Un CC en None significa "sin CC".
# ─────────────────────────────────────────────────────────────
PRESUPUESTO_DEMO = {
    # INGRESOS
    ("410101", None): [
        "45000", "45000", "47000", "47000", "50000", "50000",
        "50000", "52000", "52000", "55000", "55000", "58000",
    ],
    ("410102", None): [
        "12000", "12500", "12500", "13000", "13000", "13500",
        "13500", "14000", "14000", "14500", "14500", "15000",
    ],

    # GASTOS DE PERSONAL (sueldos base)
    ("510101", "CC-ADMIN"): [
        "8000", "8000", "8200", "8200", "8400", "8400",
        "8400", "8600", "8600", "8800", "8800", "8800",
    ],
    ("510101", "CC-VENTAS"): [
        "10000", "10000", "10200", "10200", "10500", "10500",
        "10500", "10800", "10800", "11000", "11000", "11000",
    ],
    ("510101", "CC-TECH"): [
        "14000", "14000", "14500", "14500", "15000", "15000",
        "15000", "15500", "15500", "16000", "16000", "16000",
    ],

    # CESTATICKET
    ("510102", "CC-ADMIN"): [
        "1200", "1200", "1200", "1200", "1200", "1200",
        "1200", "1200", "1200", "1200", "1200", "1200",
    ],
    ("510102", "CC-VENTAS"): [
        "1600", "1600", "1600", "1600", "1600", "1600",
        "1600", "1600", "1600", "1600", "1600", "1600",
    ],
    ("510102", "CC-TECH"): [
        "2000", "2000", "2000", "2000", "2000", "2000",
        "2000", "2000", "2000", "2000", "2000", "2000",
    ],

    # APORTES PATRONALES (aproximado 25% de sueldos)
    ("510103", "CC-ADMIN"): [
        "2000", "2000", "2050", "2050", "2100", "2100",
        "2100", "2150", "2150", "2200", "2200", "2200",
    ],
    ("510103", "CC-VENTAS"): [
        "2500", "2500", "2550", "2550", "2600", "2600",
        "2600", "2700", "2700", "2750", "2750", "2750",
    ],
    ("510103", "CC-TECH"): [
        "3500", "3500", "3600", "3600", "3750", "3750",
        "3750", "3900", "3900", "4000", "4000", "4000",
    ],

    # SERVICIOS BÁSICOS
    ("510201", "CC-ADMIN"): [
        "800", "850", "900", "950", "1000", "1050",
        "1100", "1050", "1000", "950", "900", "850",
    ],

    # ALQUILER
    ("510202", "CC-ADMIN"): [
        "3000", "3000", "3000", "3000", "3000", "3000",
        "3000", "3000", "3000", "3000", "3000", "3000",
    ],

    # INTERNET Y TELECOM
    ("510203", "CC-TECH"): [
        "500", "500", "500", "500", "500", "500",
        "500", "500", "500", "500", "500", "500",
    ],

    # MATERIALES DE OFICINA
    ("510301", "CC-ADMIN"): [
        "400", "350", "400", "380", "420", "400",
        "400", "380", "420", "400", "380", "450",
    ],

    # SOFTWARE Y LICENCIAS
    ("510302", "CC-TECH"): [
        "1500", "1500", "1500", "1500", "1500", "1500",
        "1500", "1500", "1500", "1500", "1500", "1500",
    ],

    # PUBLICIDAD
    ("510401", "CC-VENTAS"): [
        "3000", "2500", "3500", "3000", "4000", "3500",
        "3500", "4000", "3000", "3500", "4000", "5000",
    ],

    # DEPRECIACIÓN
    ("510501", "CC-ADMIN"): [
        "800", "800", "800", "800", "800", "800",
        "800", "800", "800", "800", "800", "800",
    ],
    ("510501", "CC-TECH"): [
        "1500", "1500", "1500", "1500", "1500", "1500",
        "1500", "1500", "1500", "1500", "1500", "1500",
    ],
}

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


class Command(BaseCommand):
    help = "Crea un presupuesto demo realista con cuentas, centros de costo y montos mensuales."

    def add_arguments(self, parser):
        parser.add_argument(
            "--empresa-id", type=int, default=None,
            help="ID de la empresa. Si se omite, se usa la primera empresa activa.",
        )
        parser.add_argument(
            "--anio", type=int, default=date.today().year,
            help="Año del ejercicio fiscal. Por defecto, el año en curso.",
        )
        parser.add_argument(
            "--nombre", type=str, default=None,
            help="Nombre del presupuesto. Por defecto: 'Presupuesto Operativo <año>'.",
        )
        parser.add_argument(
            "--reset", action="store_true",
            help="Si ya existe un presupuesto con ese nombre, lo borra y lo recrea.",
        )

    def handle(self, *args, **options):
        empresa_id = options["empresa_id"]
        anio = options["anio"]
        nombre = options["nombre"] or f"Presupuesto Operativo {anio}"
        reset = options["reset"]

        # ─── Resolver empresa ───
        if empresa_id:
            try:
                empresa = Empresa.objects.get(pk=empresa_id, activa=True)
            except Empresa.DoesNotExist:
                raise CommandError(f"No existe empresa activa con ID {empresa_id}.")
        else:
            empresa = Empresa.objects.filter(activa=True).first()
            if not empresa:
                raise CommandError("No hay empresas activas en la BD.")

        self.stdout.write(f"Empresa: {empresa.razon_social} (ID {empresa.id})")

        # ─── Resolver ejercicio fiscal ───
        ejercicio, _ = EjercicioFiscal.objects.get_or_create(
            empresa=empresa,
            anio=anio,
            defaults={
                "fecha_inicio": date(anio, 1, 1),
                "fecha_fin": date(anio, 12, 31),
            },
        )
        self.stdout.write(f"Ejercicio: {ejercicio.anio}")

        # ─── Crear/actualizar plan de cuentas ───
        cuentas_creadas = 0
        for codigo, nombre_cta, tipo, naturaleza in CUENTAS_DEMO:
            _, created = PlanCuenta.objects.get_or_create(
                empresa=empresa,
                codigo=codigo,
                defaults={
                    "nombre": nombre_cta,
                    "tipo": tipo,
                    "naturaleza": naturaleza,
                    "es_agrupadora": False,
                    "activa": True,
                },
            )
            if created:
                cuentas_creadas += 1
        self.stdout.write(f"Cuentas creadas: {cuentas_creadas} (reutilizadas: {len(CUENTAS_DEMO) - cuentas_creadas})")

        # ─── Crear/actualizar centros de costo ───
        centros_creados = 0
        for codigo, nombre_cc, tipo_cc, capacidad in CENTROS_DEMO:
            _, created = CentroCosto.objects.get_or_create(
                empresa=empresa,
                codigo=codigo,
                defaults={
                    "nombre": nombre_cc,
                    "tipo": tipo_cc,
                    "activo": True,
                    "capacidad_horas_mes": Decimal(str(capacidad)),
                },
            )
            if created:
                centros_creados += 1
        self.stdout.write(f"Centros de costo creados: {centros_creados}")

        # ─── Crear presupuesto ───
        with transaction.atomic():
            existente = Presupuesto.objects.filter(
                empresa=empresa, ejercicio=ejercicio, nombre=nombre
            ).first()

            if existente and not reset:
                raise CommandError(
                    f"Ya existe el presupuesto '{nombre}' para {anio} (ID {existente.id}). "
                    f"Usa --reset para borrarlo y recrearlo."
                )

            if existente and reset:
                self.stdout.write(self.style.WARNING(
                    f"Reset: borrando presupuesto existente '{nombre}' (ID {existente.id})"
                ))
                existente.delete()

            presupuesto = Presupuesto.objects.create(
                empresa=empresa,
                ejercicio=ejercicio,
                nombre=nombre,
            )
            self.stdout.write(f"Presupuesto creado: ID {presupuesto.id} — '{nombre}'")

            # ─── Crear líneas ───
            lineas_creadas = 0
            for (cuenta_codigo, cc_codigo), montos in PRESUPUESTO_DEMO.items():
                cuenta = PlanCuenta.objects.filter(
                    empresa=empresa, codigo=cuenta_codigo
                ).first()
                if not cuenta:
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠ Cuenta {cuenta_codigo} no encontrada, línea omitida"
                    ))
                    continue

                centro = None
                if cc_codigo:
                    centro = CentroCosto.objects.filter(
                        empresa=empresa, codigo=cc_codigo
                    ).first()
                    if not centro:
                        self.stdout.write(self.style.WARNING(
                            f"  ⚠ Centro {cc_codigo} no encontrado, línea omitida"
                        ))
                        continue

                linea, created = PresupuestoLinea.objects.get_or_create(
                    presupuesto=presupuesto,
                    cuenta=cuenta,
                    centro_costo=centro,
                )
                if created:
                    lineas_creadas += 1

                # Asignar los 12 montos
                for idx, mes in enumerate(MESES):
                    setattr(linea, f"monto_{mes}", Decimal(montos[idx]))
                linea.save()

            self.stdout.write(self.style.SUCCESS(
                f"✔ Presupuesto demo creado con {lineas_creadas} línea(s)."
            ))
            self.stdout.write(f"  Abre: /contabilidad/presupuestos/{presupuesto.id}/")
            self.stdout.write(f"  Dashboard: /contabilidad/presupuestos/{presupuesto.id}/dashboard/")
            self.stdout.write(f"  Vs Real: /contabilidad/presupuestos/{presupuesto.id}/vs-real/")