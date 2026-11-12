# contabilidad/management/commands/seed_plan_cuentas.py
from django.core.management.base import BaseCommand
from rrhh.models import Empresa
from contabilidad.models import PlanCuenta
from contabilidad.constants import *

class Command(BaseCommand):
    help = "Crea el plan de cuentas base venezolano para una empresa."

    def add_arguments(self, parser):
        parser.add_argument("--empresa-id", type=int, required=True)

    def handle(self, *args, **options):
        empresa_id = options["empresa_id"]
        try:
            empresa = Empresa.objects.get(pk=empresa_id)
        except Empresa.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"No existe la empresa con ID {empresa_id}"))
            return

        self.stdout.write(f"Generando plan de cuentas para: {empresa.razon_social}")

        # Estructura básica de cuentas (Código, Nombre, Tipo, Naturaleza, ¿Agrupadora?)
        cuentas_base = [
            # ACTIVO
            ("1", "ACTIVO", TIPO_ACTIVO, NATURALEZA_DEUDORA, True),
            ("11", "Activo Circulante", TIPO_ACTIVO, NATURALEZA_DEUDORA, True),
            ("1101", "Efectivo en Caja y Bancos", TIPO_ACTIVO, NATURALEZA_DEUDORA, True),
            ("110101", "Caja General", TIPO_ACTIVO, NATURALEZA_DEUDORA, False),
            ("110102", "Bancos", TIPO_ACTIVO, NATURALEZA_DEUDORA, False),
            ("1102", "Cuentas por Cobrar", TIPO_ACTIVO, NATURALEZA_DEUDORA, True),
            ("110201", "Clientes", TIPO_ACTIVO, NATURALEZA_DEUDORA, False),
            ("1103", "Inventarios", TIPO_ACTIVO, NATURALEZA_DEUDORA, True),
            ("110301", "Inventario de Materia Prima", TIPO_ACTIVO, NATURALEZA_DEUDORA, False),
            ("110302", "Inventario de Productos en Proceso", TIPO_ACTIVO, NATURALEZA_DEUDORA, False),
            ("110303", "Inventario de Productos Terminados", TIPO_ACTIVO, NATURALEZA_DEUDORA, False),
            ("12", "Activo No Circulante", TIPO_ACTIVO, NATURALEZA_DEUDORA, True),
            ("1201", "Propiedad, Planta y Equipo", TIPO_ACTIVO, NATURALEZA_DEUDORA, True),
            ("120101", "Maquinaria y Equipos", TIPO_ACTIVO, NATURALEZA_DEUDORA, False),
            ("120102", "Depreciación Acumulada", TIPO_ACTIVO, NATURALEZA_ACREEDORA, False),

            # PASIVO
            ("2", "PASIVO", TIPO_PASIVO, NATURALEZA_ACREEDORA, True),
            ("21", "Pasivo Circulante", TIPO_PASIVO, NATURALEZA_ACREEDORA, True),
            ("2101", "Cuentas por Pagar", TIPO_PASIVO, NATURALEZA_ACREEDORA, True),
            ("210101", "Proveedores", TIPO_PASIVO, NATURALEZA_ACREEDORA, False),
            ("210102", "Sueldos y Salarios por Pagar", TIPO_PASIVO, NATURALEZA_ACREEDORA, False),
            ("210103", "Retenciones de Ley (IVSS, RPE, BANAVIH)", TIPO_PASIVO, NATURALEZA_ACREEDORA, False),
            ("210104", "ISLR por Pagar", TIPO_PASIVO, NATURALEZA_ACREEDORA, False),

            # PATRIMONIO
            ("3", "PATRIMONIO", TIPO_PATRIMONIO, NATURALEZA_ACREEDORA, True),
            ("3101", "Capital Social", TIPO_PATRIMONIO, NATURALEZA_ACREEDORA, False),
            ("3102", "Resultados Acumulados", TIPO_PATRIMONIO, NATURALEZA_ACREEDORA, False),

            # INGRESOS
            ("4", "INGRESOS", TIPO_INGRESO, NATURALEZA_ACREEDORA, True),
            ("4101", "Ingresos Operativos", TIPO_INGRESO, NATURALEZA_ACREEDORA, True),
            ("410101", "Ventas de Productos", TIPO_INGRESO, NATURALEZA_ACREEDORA, False),
            ("410102", "Prestación de Servicios", TIPO_INGRESO, NATURALEZA_ACREEDORA, False),

            # COSTOS (Para producción)
            ("5", "COSTOS DE PRODUCCIÓN", TIPO_COSTO, NATURALEZA_DEUDORA, True),
            ("5101", "Materia Prima Directa", TIPO_COSTO, NATURALEZA_DEUDORA, True),
            ("510101", "Consumo de Papel", TIPO_COSTO, NATURALEZA_DEUDORA, False),
            ("510102", "Consumo de Tintas", TIPO_COSTO, NATURALEZA_DEUDORA, False),
            ("5102", "Mano de Obra Directa", TIPO_COSTO, NATURALEZA_DEUDORA, True),
            ("510201", "Sueldos de Producción", TIPO_COSTO, NATURALEZA_DEUDORA, False),
            ("5103", "Costos Indirectos de Fabricación (CIF)", TIPO_COSTO, NATURALEZA_DEUDORA, True),
            ("510301", "Depreciación de Maquinaria", TIPO_COSTO, NATURALEZA_DEUDORA, False),
            ("510302", "Mantenimiento de Maquinaria", TIPO_COSTO, NATURALEZA_DEUDORA, False),

            # GASTOS
            ("6", "GASTOS OPERATIVOS", TIPO_GASTO, NATURALEZA_DEUDORA, True),
            ("6101", "Gastos de Administración", TIPO_GASTO, NATURALEZA_DEUDORA, True),
            ("610101", "Sueldos Administrativos", TIPO_GASTO, NATURALEZA_DEUDORA, False),
            ("610102", "Servicios Básicos", TIPO_GASTO, NATURALEZA_DEUDORA, False),
            ("6102", "Gastos de Ventas", TIPO_GASTO, NATURALEZA_DEUDORA, True),
            ("610201", "Comisiones de Ventas", TIPO_GASTO, NATURALEZA_DEUDORA, False),
        ]

        creados = 0
        existentes = 0

        for codigo, nombre, tipo, naturaleza, es_agrupadora in cuentas_base:
            # Determinar si es cuenta de costo
            es_costo = (tipo == TIPO_COSTO)
            
            obj, created = PlanCuenta.objects.get_or_create(
                empresa=empresa,
                codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "tipo": tipo,
                    "naturaleza": naturaleza,
                    "es_agrupadora": es_agrupadora,
                    "es_cuenta_de_costo": es_costo,
                }
            )
            if created:
                creados += 1
            else:
                existentes += 1

        self.stdout.write(self.style.SUCCESS(f"Plan de cuentas generado: {creados} creadas, {existentes} ya existían."))