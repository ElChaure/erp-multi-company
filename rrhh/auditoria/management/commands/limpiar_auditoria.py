"""
Comando para limpiar auditorías antiguas.

Uso:
    python manage.py limpiar_auditoria --dias 365
    python manage.py limpiar_auditoria --dias 730 --dry-run
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from rrhh.auditoria.models import Auditoria


class Command(BaseCommand):
    help = "Elimina registros de auditoría más antiguos que N días"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias", type=int, default=365,
            help="Días de retención (default: 365)",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Solo mostrar qué se eliminaría, sin borrar",
        )
        parser.add_argument(
            "--conservar-criticos", action="store_true", default=True,
            help="Conservar acciones críticas (delete, export, login_failed)",
        )

    def handle(self, *args, **options):
        dias = options["dias"]
        dry_run = options["dry_run"]
        conservar_criticos = options["conservar_criticos"]

        limite = timezone.now() - timedelta(days=dias)

        qs = Auditoria.objects.filter(fecha__lt=limite)

        if conservar_criticos:
            qs = qs.exclude(accion__in=["delete", "export", "login_failed"])

        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                f"✅ No hay auditorías más antiguas que {dias} días."
            ))
            return

        self.stdout.write(self.style.WARNING(
            f"{'[DRY-RUN] ' if dry_run else ''}"
            f"Se eliminarán {total} registros de auditoría "
            f"anteriores a {limite.date()}."
        ))

        if dry_run:
            # Mostrar algunos ejemplos
            for aud in qs.order_by("fecha")[:10]:
                self.stdout.write(
                    f"  - {aud.fecha.date()} | {aud.usuario} | "
                    f"{aud.accion} | {aud.tabla}#{aud.registro_id}"
                )
            if total > 10:
                self.stdout.write(f"  ... y {total - 10} más.")
            return

        # Confirmar eliminación
        eliminados = qs.delete()[0]
        self.stdout.write(self.style.SUCCESS(
            f"✅ {eliminados} registros eliminados."
        ))