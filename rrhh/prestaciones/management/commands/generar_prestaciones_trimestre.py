"""
Genera los depósitos de prestaciones sociales para un trimestre específico.

Uso:
    python manage.py generar_prestaciones_trimestre --anio 2026 --trimestre 4
    python manage.py generar_prestaciones_trimestre --anio 2026 --trimestre 4 --empresa-id 1
    python manage.py generar_prestaciones_trimestre --anio 2026 --trimestre 4 --empleado-id 5
    python manage.py generar_prestaciones_trimestre --anio 2026 --trimestre 4 --dry-run

Se ejecuta típicamente:
    - Al cierre del trimestre (01/04, 01/07, 01/10, 01/01)
    - Manualmente por RRHH
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from rrhh.models import Empleado, Empresa, ParametroNomina
from rrhh.prestaciones.services import (
    generar_deposito_trimestre,
    recalcular_prestacion,
)
from rrhh.prestaciones.engine import rango_trimestre


class Command(BaseCommand):
    help = (
        "Genera los depósitos de prestaciones sociales para un trimestre. "
        "Crea un DepositoPrestacion por empleado activo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--anio",
            type=int,
            required=True,
            help="Año del trimestre (ej: 2026).",
        )
        parser.add_argument(
            "--trimestre",
            type=int,
            required=True,
            choices=[1, 2, 3, 4],
            help="Trimestre (1-4).",
        )
        parser.add_argument(
            "--empresa-id",
            type=int,
            help="ID de empresa (opcional). Si no se pasa, procesa todas.",
        )
        parser.add_argument(
            "--empleado-id",
            type=int,
            help="ID de empleado específico (opcional). Sobrescribe --empresa-id.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra lo que haría, sin guardar cambios.",
        )

    def handle(self, *args, **options):
        anio = options["anio"]
        trimestre = options["trimestre"]
        empresa_id = options.get("empresa_id")
        empleado_id = options.get("empleado_id")
        dry_run = options["dry_run"]

        fecha_inicio, fecha_fin = rango_trimestre(anio, trimestre)

        self.stdout.write(self.style.NOTICE(
            f"\n═══ Generando depósitos de prestaciones ═══"
        ))
        self.stdout.write(f"Trimestre: {anio}-T{trimestre}")
        self.stdout.write(f"Rango:     {fecha_inicio} → {fecha_fin}")
        self.stdout.write(f"Modo:      {'DRY-RUN (sin guardar)' if dry_run else 'REAL'}")
        self.stdout.write("")

        # ─── Filtrar empleados ────────────────────────────
        empleados = Empleado.objects.filter(estatus="activo")

        if empleado_id:
            empleados = empleados.filter(pk=empleado_id)
            if not empleados.exists():
                raise CommandError(f"No existe el empleado con ID {empleado_id}.")
        elif empresa_id:
            empleados = empleados.filter(empresa_id=empresa_id)

        empleados = empleados.select_related("empresa").order_by(
            "empresa__razon_social", "numero_empleado"
        )

        if not empleados.exists():
            self.stdout.write(self.style.WARNING(
                "⚠️ No hay empleados que cumplan los filtros."
            ))
            return

        self.stdout.write(f"Empleados a procesar: {empleados.count()}\n")

        # ─── Procesar ────────────────────────────────────
        exitosos = 0
        omitidos = 0
        errores = 0

        for empleado in empleados:
            try:
                # Verificar si el empleado estaba activo en el rango
                if empleado.fecha_ingreso > fecha_fin:
                    omitidos += 1
                    continue
                if empleado.fecha_egreso and empleado.fecha_egreso < fecha_inicio:
                    omitidos += 1
                    continue

                # Parámetros del año
                parametros = ParametroNomina.objects.filter(
                    empresa=empleado.empresa,
                    anio=anio,
                    activo=True,
                ).first()

                if not parametros:
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠️ {empleado.numero_empleado} - {empleado.nombre_completo}: "
                        f"sin parámetros de nómina para {anio}. Omitido."
                    ))
                    errores += 1
                    continue

                if dry_run:
                    # Solo mostrar
                    self.stdout.write(
                        f"  [DRY] {empleado.numero_empleado} - "
                        f"{empleado.nombre_completo} ✓"
                    )
                    exitosos += 1
                    continue

                # Generar depósito
                with transaction.atomic():
                    deposito = generar_deposito_trimestre(
                        empleado, anio, trimestre, parametros
                    )
                    if deposito:
                        recalcular_prestacion(empleado, parametros)
                        self.stdout.write(self.style.SUCCESS(
                            f"  ✅ {empleado.numero_empleado} - "
                            f"{empleado.nombre_completo} → "
                            f"Bs. {deposito.monto_ves:,.2f}"
                        ))
                        exitosos += 1

            except Exception as e:
                errores += 1
                self.stdout.write(self.style.ERROR(
                    f"  ❌ {empleado.numero_empleado} - "
                    f"{empleado.nombre_completo}: {e}"
                ))

        # ─── Resumen ─────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("═══ Resumen ═══"))
        self.stdout.write(f"  Exitosos:  {exitosos}")
        self.stdout.write(f"  Omitidos:  {omitidos}")
        self.stdout.write(f"  Errores:   {errores}")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n💡 Ejecuta sin --dry-run para guardar los cambios."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n🎉 Trimestre {anio}-T{trimestre} procesado."
            ))