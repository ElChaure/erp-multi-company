"""
Procesa la liquidación de prestaciones sociales de un empleado egresado.

Uso:
    python manage.py procesar_liquidacion --empleado-id 5
    python manage.py procesar_liquidacion --empleado-id 5 --fecha-egreso 2026-10-31
    python manage.py procesar_liquidacion --empleado-id 5 --dry-run

Acciones:
    1. Calcula garantía acumulada + retroactivo
    2. Aplica Art. 142.d (el mayor)
    3. Registra un CalculoRetroactivo con la comparación
    4. Marca la prestación como liquidada
    5. Actualiza Empleado.estatus = 'baja' (si no lo está)
    6. Actualiza Empleado.fecha_egreso (si no la tiene)
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from rrhh.models import Empleado
from rrhh.prestaciones.engine import calcular_prestaciones
from rrhh.prestaciones.services import (
    obtener_prestacion,
    registrar_calculo_retroactivo,
    recalcular_prestacion,
)


class Command(BaseCommand):
    help = "Liquida las prestaciones sociales de un empleado egresado."

    def add_arguments(self, parser):
        parser.add_argument("--empleado-id", type=int, required=True)
        parser.add_argument(
            "--fecha-egreso",
            type=str,
            help="Fecha de egreso (YYYY-MM-DD). Si no se pasa, usa hoy.",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        empleado_id = options["empleado_id"]
        dry_run = options["dry_run"]

        try:
            empleado = Empleado.objects.get(pk=empleado_id)
        except Empleado.DoesNotExist:
            raise CommandError(f"No existe el empleado con ID {empleado_id}.")

        # Fecha de egreso
        if options.get("fecha_egreso"):
            try:
                fecha_egreso = date.fromisoformat(options["fecha_egreso"])
            except ValueError:
                raise CommandError(
                    f"Fecha inválida: {options['fecha_egreso']}. "
                    f"Formato esperado: YYYY-MM-DD."
                )
        else:
            fecha_egreso = empleado.fecha_egreso or date.today()

        self.stdout.write(self.style.NOTICE(
            f"\n═══ Liquidación de prestaciones ═══"
        ))
        self.stdout.write(f"Empleado:      {empleado.numero_empleado} - {empleado.nombre_completo}")
        self.stdout.write(f"Empresa:       {empleado.empresa.razon_social}")
        self.stdout.write(f"Fecha ingreso: {empleado.fecha_ingreso}")
        self.stdout.write(f"Fecha egreso:  {fecha_egreso}")
        self.stdout.write(f"Modo:          {'DRY-RUN' if dry_run else 'REAL'}\n")

        # ─── Calcular ────────────────────────────────────
        calculo = calcular_prestaciones(empleado, fecha_egreso)

        garantia = calculo["garantia"]
        retro = calculo["retroactivo"]

        self.stdout.write(self.style.NOTICE("─── Comparación Art. 142.d ───"))
        self.stdout.write(
            f"  Garantía (a+b):     Bs. {garantia['total_ves']:>15,.2f}  "
            f"({garantia['total_dias']} días)"
        )
        self.stdout.write(
            f"  Retroactivo (c):    Bs. {retro['monto_ves']:>15,.2f}  "
            f"({retro['dias_retroactivo']} días)"
        )
        self.stdout.write(
            f"  ────────────────────────────────────────"
        )
        self.stdout.write(self.style.SUCCESS(
            f"  Método aplicado:    {calculo['metodo_seleccionado'].upper()}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"  Monto a liquidar:   Bs. {calculo['monto_final_ves']:>15,.2f}"
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n💡 Ejecuta sin --dry-run para guardar la liquidación."
            ))
            return

        # ─── Guardar ─────────────────────────────────────
        with transaction.atomic():
            prestacion = obtener_prestacion(empleado)

            # Guardar snapshot
            registro = registrar_calculo_retroactivo(empleado, fecha_egreso)

            # Actualizar prestación
            prestacion.estatus = "liquidada"
            prestacion.fecha_liquidacion = fecha_egreso
            prestacion.monto_liquidacion_ves = calculo["monto_final_ves"]
            prestacion.ultimo_metodo_aplicado = calculo["metodo_seleccionado"]
            prestacion.save()

            # Actualizar empleado
            if empleado.estatus != "baja":
                empleado.estatus = "baja"
            if not empleado.fecha_egreso:
                empleado.fecha_egreso = fecha_egreso
            empleado.save(update_fields=["estatus", "fecha_egreso", "updated_at"])

        self.stdout.write(self.style.SUCCESS(
            f"\n🎉 Liquidación procesada y guardada."
        ))
        self.stdout.write(
            f"   ID del cálculo retroactivo: #{registro.id}"
        )