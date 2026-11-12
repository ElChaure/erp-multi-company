"""
Procesa los vencimientos de días de vacaciones no disfrutados.

Según LOTTT Art. 192, los días causados vencen a los 12 meses (o el
plazo configurado por empresa). Este comando marca esos días como
vencidos y ajusta el saldo.

Uso:
    python manage.py procesar_vencimientos
    python manage.py procesar_vencimientos --empresa-id 1
    python manage.py procesar_vencimientos --anio 2025
    python manage.py procesar_vencimientos --dry-run
    python manage.py procesar_vencimientos --avisar-dias 60

Se ejecuta típicamente:
    - Mensualmente por cron
    - Al cierre del año fiscal
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from rrhh.models import (
    Empresa,
    SaldoVacaciones,
    MovimientoSaldoVacaciones,
)


class Command(BaseCommand):
    help = (
        "Marca como vencidos los días de vacaciones pendientes cuyos "
        "saldos ya pasaron su fecha límite de uso."
    )

    def add_arguments(self, parser):
        parser.add_argument("--empresa-id", type=int)
        parser.add_argument("--anio", type=int, help="Año específico a procesar.")
        parser.add_argument(
            "--avisar-dias",
            type=int,
            default=60,
            help="Días de antelación para mostrar avisos (default: 60).",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        empresa_id = options.get("empresa_id")
        anio = options.get("anio")
        dias_aviso = options["avisar_dias"]
        dry_run = options["dry_run"]

        hoy = date.today()
        limite_aviso = hoy + timedelta(days=dias_aviso)

        # Queryset base
        qs = SaldoVacaciones.objects.select_related(
            "empleado", "empleado__empresa"
        )

        if empresa_id:
            qs = qs.filter(empleado__empresa_id=empresa_id)
        if anio:
            qs = qs.filter(anio=anio)

        self.stdout.write(self.style.NOTICE(
            f"\n═══ Procesamiento de vencimientos ═══"
        ))
        self.stdout.write(f"Fecha de hoy: {hoy}")
        self.stdout.write(f"Días de aviso: {dias_aviso}")
        self.stdout.write(f"Modo: {'DRY-RUN' if dry_run else 'REAL'}\n")

        # ─── Parte 1: Vencidos (fecha límite ya pasó) ───
        vencidos = [
            s for s in qs.filter(fecha_limite_uso__lt=hoy)
            if s.dias_pendientes > 0
        ]

        self.stdout.write(self.style.NOTICE(
            f"─── Saldos ya vencidos: {len(vencidos)} ───"
        ))

        total_vencido = Decimal("0")
        procesados = 0

        for saldo in vencidos:
            dias = saldo.dias_pendientes

            if dry_run:
                self.stdout.write(
                    f"  [DRY] {saldo.empleado.numero_empleado} - "
                    f"año {saldo.anio}: {dias} días "
                    f"(venció {saldo.fecha_limite_uso})"
                )
                total_vencido += dias
                procesados += 1
                continue

            try:
                saldo_anterior = saldo.dias_pendientes

                # Movimiento de vencimiento
                MovimientoSaldoVacaciones.objects.create(
                    saldo=saldo,
                    tipo="vencimiento",
                    dias=-dias,
                    saldo_anterior=saldo_anterior,
                    saldo_nuevo=Decimal("0"),
                    motivo=(
                        f"Días vencidos (fecha límite: "
                        f"{saldo.fecha_limite_uso})"
                    ),
                )

                # Ajuste negativo
                saldo.dias_ajuste -= dias
                saldo.save(update_fields=["dias_ajuste", "updated_at"])

                self.stdout.write(self.style.SUCCESS(
                    f"  ✅ {saldo.empleado.numero_empleado} - "
                    f"año {saldo.anio}: {dias} días vencidos"
                ))

                total_vencido += dias
                procesados += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"  ❌ {saldo.empleado.numero_empleado} - "
                    f"{saldo.anio}: {e}"
                ))

        # ─── Parte 2: Por vencer (aviso) ───
        por_vencer = [
            s for s in qs.filter(
                fecha_limite_uso__gte=hoy,
                fecha_limite_uso__lte=limite_aviso,
            )
            if s.dias_pendientes > 0
        ]

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE(
            f"─── Por vencer en los próximos {dias_aviso} días: "
            f"{len(por_vencer)} ───"
        ))

        for saldo in por_vencer:
            dias_restantes = (saldo.fecha_limite_uso - hoy).days
            self.stdout.write(
                f"  ⚠️  {saldo.empleado.numero_empleado} - "
                f"año {saldo.anio}: {saldo.dias_pendientes} días "
                f"(vence en {dias_restantes} días, "
                f"el {saldo.fecha_limite_uso})"
            )

        # Resumen
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("═══ Resumen ═══"))
        self.stdout.write(f"  Vencidos procesados: {procesados}")
        self.stdout.write(f"  Total días vencidos: {total_vencido}")
        self.stdout.write(f"  Por vencer (aviso):  {len(por_vencer)}")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n💡 Ejecuta sin --dry-run para guardar los cambios."
            ))