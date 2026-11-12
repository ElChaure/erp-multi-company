"""
Registra manualmente la tasa de interés mensual del BCV.

Uso:
    python manage.py registrar_tasa_bcv --empresa-id 1 --anio 2026 --mes 10 --tasa 12.50
    python manage.py registrar_tasa_bcv --todas --anio 2026 --mes 10 --tasa 12.50
    python manage.py registrar_tasa_bcv --empresa-id 1 --anio 2026 --mes 10 --tasa 12.50 --moneda USD

La tasa se interpreta como **anual nominal** (porcentaje).
Internamente se calcula mensual (/12) y diaria (/360).
"""
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from rrhh.models import Empresa
from rrhh.prestaciones.models import TasaInteresPrestaciones


class Command(BaseCommand):
    help = "Registra la tasa de interés BCV mensual para prestaciones."

    def add_arguments(self, parser):
        parser.add_argument("--empresa-id", type=int)
        parser.add_argument(
            "--todas",
            action="store_true",
            help="Aplicar a todas las empresas activas.",
        )
        parser.add_argument("--anio", type=int, required=True)
        parser.add_argument("--mes", type=int, required=True, choices=range(1, 13))
        parser.add_argument(
            "--tasa",
            type=str,
            required=True,
            help="Tasa anual en porcentaje (ej: 12.50)",
        )
        parser.add_argument(
            "--moneda",
            choices=["VES", "USD"],
            default="VES",
        )
        parser.add_argument(
            "--fuente",
            choices=["manual", "api_bcv", "otra"],
            default="manual",
        )
        parser.add_argument("--observaciones", default="")

    def handle(self, *args, **options):
        try:
            tasa = Decimal(options["tasa"])
            if tasa < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            raise CommandError(f"Tasa inválida: {options['tasa']}")

        # Determinar empresas
        if options["todas"]:
            empresas = Empresa.objects.filter(activa=True)
        elif options.get("empresa_id"):
            empresas = Empresa.objects.filter(id=options["empresa_id"])
            if not empresas.exists():
                raise CommandError(
                    f"No existe la empresa con ID {options['empresa_id']}."
                )
        else:
            raise CommandError(
                "Debes especificar --empresa-id N o --todas."
            )

        anio = options["anio"]
        mes = options["mes"]
        moneda = options["moneda"]
        fuente = options["fuente"]

        self.stdout.write(self.style.NOTICE(
            f"\n═══ Registrando tasa BCV ═══"
        ))
        self.stdout.write(f"Año/Mes:   {anio}-{mes:02d}")
        self.stdout.write(f"Tasa:      {tasa} por ciento anual")
        self.stdout.write(f"Moneda:    {moneda}")
        self.stdout.write(f"Empresas:  {empresas.count()}\n")

        exitosas = 0
        for empresa in empresas:
            obj, created = TasaInteresPrestaciones.objects.update_or_create(
                empresa=empresa,
                anio=anio,
                mes=mes,
                moneda=moneda,
                defaults={
                    "tasa_anual_pct": tasa,
                    "fuente": fuente,
                    "observaciones": options["observaciones"],
                },
            )
            accion = "Creada" if created else "Actualizada"
            self.stdout.write(self.style.SUCCESS(
                f"  ✅ {accion}: {empresa.razon_social} → {tasa} por ciento"
            ))
            exitosas += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n🎉 {exitosas} tasa(s) registrada(s)."
        ))