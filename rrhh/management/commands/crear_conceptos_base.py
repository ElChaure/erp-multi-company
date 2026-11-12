"""
Crea los conceptos base de nómina para Venezuela.

Uso:
    python manage.py crear_conceptos_base
    python manage.py crear_conceptos_base --empresa-id 1
    python manage.py crear_conceptos_base --global
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from rrhh.models import Empresa, ConceptoNomina


CONCEPTOS = [
    # ─── PERCEPCIONES ────────────────────────────────────
    {
        "codigo": "001",
        "nombre": "Sueldo básico",
        "tipo": "percepcion",
        "naturaleza": "gravado",
        "es_fijo": True,
        "prioridad": 10,
        "afecta_isr": True,
        "afecta_ivss": True,
        "afecta_rpe": True,
        "afecta_banavih": True,
        "forma_parte_salario_normal": True,
    },
    {
        "codigo": "010",
        "nombre": "Horas extra diurnas",
        "tipo": "percepcion",
        "naturaleza": "gravado",
        "es_fijo": False,
        "prioridad": 20,
        "afecta_isr": True,
        "afecta_ivss": True,
        "afecta_rpe": True,
        "afecta_banavih": True,
        "forma_parte_salario_normal": True,
    },
    {
        "codigo": "011",
        "nombre": "Horas extra nocturnas",
        "tipo": "percepcion",
        "naturaleza": "gravado",
        "es_fijo": False,
        "prioridad": 21,
        "afecta_isr": True,
        "afecta_ivss": True,
        "afecta_rpe": True,
        "afecta_banavih": True,
        "forma_parte_salario_normal": True,
    },
    {
        "codigo": "012",
        "nombre": "Bono nocturno",
        "tipo": "percepcion",
        "naturaleza": "gravado",
        "es_fijo": False,
        "prioridad": 22,
        "afecta_isr": True,
        "afecta_ivss": True,
        "afecta_rpe": True,
        "afecta_banavih": True,
        "forma_parte_salario_normal": True,
    },
    {
        "codigo": "020",
        "nombre": "Cestaticket",
        "tipo": "percepcion",
        "naturaleza": "exento",
        "es_fijo": True,
        "prioridad": 30,
        "afecta_isr": False,
        "afecta_ivss": False,
        "afecta_rpe": False,
        "afecta_banavih": False,
        "forma_parte_salario_normal": False,
    },
    {
        "codigo": "030",
        "nombre": "Feriado trabajado",
        "tipo": "percepcion",
        "naturaleza": "gravado",
        "es_fijo": False,
        "prioridad": 40,
        "afecta_isr": True,
        "afecta_ivss": True,
        "afecta_rpe": True,
        "afecta_banavih": True,
        "forma_parte_salario_normal": True,
    },
    {
        "codigo": "005",
        "nombre": "Prima vacacional",
        "tipo": "percepcion",
        "naturaleza": "gravado",
        "es_fijo": False,
        "prioridad": 25,
        "afecta_isr": True,
        "afecta_ivss": True,
        "afecta_rpe": True,
        "afecta_banavih": True,
        "forma_parte_salario_normal": True,
    },
    # ─── DEDUCCIONES ─────────────────────────────────────
    {
        "codigo": "050",
        "nombre": "IVSS (Seguro Social)",
        "tipo": "deduccion",
        "naturaleza": "gravado",
        "es_fijo": True,
        "prioridad": 200,
        "afecta_isr": False,
        "afecta_ivss": False,
        "afecta_rpe": False,
        "afecta_banavih": False,
        "forma_parte_salario_normal": False,
    },
    {
        "codigo": "051",
        "nombre": "Paro Forzoso (RPE)",
        "tipo": "deduccion",
        "naturaleza": "gravado",
        "es_fijo": True,
        "prioridad": 210,
        "afecta_isr": False,
        "afecta_ivss": False,
        "afecta_rpe": False,
        "afecta_banavih": False,
        "forma_parte_salario_normal": False,
    },
    {
        "codigo": "052",
        "nombre": "BANAVIH (Vivienda)",
        "tipo": "deduccion",
        "naturaleza": "gravado",
        "es_fijo": True,
        "prioridad": 220,
        "afecta_isr": False,
        "afecta_ivss": False,
        "afecta_rpe": False,
        "afecta_banavih": False,
        "forma_parte_salario_normal": False,
    },
    {
        "codigo": "060",
        "nombre": "ISLR",
        "tipo": "deduccion",
        "naturaleza": "gravado",
        "es_fijo": True,
        "prioridad": 230,
        "afecta_isr": False,
        "afecta_ivss": False,
        "afecta_rpe": False,
        "afecta_banavih": False,
        "forma_parte_salario_normal": False,
    },
    # ─── APORTES PATRONALES ──────────────────────────────
    {
        "codigo": "100",
        "nombre": "IVSS patronal",
        "tipo": "aporte_patronal",
        "naturaleza": "gravado",
        "es_fijo": True,
        "prioridad": 300,
        "afecta_isr": False,
        "afecta_ivss": False,
        "afecta_rpe": False,
        "afecta_banavih": False,
        "forma_parte_salario_normal": False,
    },
    {
        "codigo": "101",
        "nombre": "Paro Forzoso patronal",
        "tipo": "aporte_patronal",
        "naturaleza": "gravado",
        "es_fijo": True,
        "prioridad": 310,
        "afecta_isr": False,
        "afecta_ivss": False,
        "afecta_rpe": False,
        "afecta_banavih": False,
        "forma_parte_salario_normal": False,
    },
    {
        "codigo": "102",
        "nombre": "BANAVIH patronal",
        "tipo": "aporte_patronal",
        "naturaleza": "gravado",
        "es_fijo": True,
        "prioridad": 320,
        "afecta_isr": False,
        "afecta_ivss": False,
        "afecta_rpe": False,
        "afecta_banavih": False,
        "forma_parte_salario_normal": False,
    },
    {
        "codigo": "103",
        "nombre": "INCES patronal",
        "tipo": "aporte_patronal",
        "naturaleza": "gravado",
        "es_fijo": True,
        "prioridad": 330,
        "afecta_isr": False,
        "afecta_ivss": False,
        "afecta_rpe": False,
        "afecta_banavih": False,
        "forma_parte_salario_normal": False,
    },
    {
        "codigo": "104",
        "nombre": "LOPCYMAT patronal",
        "tipo": "aporte_patronal",
        "naturaleza": "gravado",
        "es_fijo": True,
        "prioridad": 340,
        "afecta_isr": False,
        "afecta_ivss": False,
        "afecta_rpe": False,
        "afecta_banavih": False,
        "forma_parte_salario_normal": False,
    },
]


class Command(BaseCommand):
    help = "Crea los conceptos base de nómina para Venezuela"

    def add_arguments(self, parser):
        parser.add_argument(
            "--empresa-id",
            type=int,
            default=None,
            help="ID de la empresa (por defecto, la primera)",
        )
        parser.add_argument(
            "--global",
            dest="es_global",
            action="store_true",
            help="Crea los conceptos como globales (empresa=None)",
        )

    def handle(self, *args, **options):
        empresa = None

        if options["empresa_id"]:
            try:
                empresa = Empresa.objects.get(pk=options["empresa_id"])
                self.stdout.write(f"Empresa: {empresa.razon_social}")
            except Empresa.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(
                        f"No existe la empresa con id={options['empresa_id']}"
                    )
                )
                return
        elif not options["es_global"]:
            empresa = Empresa.objects.first()
            if not empresa:
                self.stderr.write(
                    self.style.ERROR(
                        "No hay empresas en la base. Crea una primero "
                        "o usa --global."
                    )
                )
                return
            self.stdout.write(f"Empresa: {empresa.razon_social}")
        else:
            self.stdout.write("Modo: conceptos globales (empresa=None)")

        creados = 0
        actualizados = 0

        for data in CONCEPTOS:
            obj, created = ConceptoNomina.objects.update_or_create(
                empresa=empresa,
                codigo=data["codigo"],
                defaults=data,
            )
            if created:
                creados += 1
                self.stdout.write(f"  ✅ {obj.codigo} - {obj.nombre}")
            else:
                actualizados += 1
                self.stdout.write(
                    f"  🔄 {obj.codigo} - {obj.nombre} (actualizado)"
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ {creados} conceptos creados, {actualizados} actualizados."
            )
        )