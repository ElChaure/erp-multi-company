"""
Pobla el catálogo de bancos con los códigos Sudeban oficiales.
Fuente: BCV / Sudeban
"""
from django.core.management.base import BaseCommand
from rrhh.models import Banco


BANCOS_SUDEBAN = [
    # (codigo, nombre, nombre_corto)
    ("0001", "Banco Central de Venezuela", "BCV"),
    ("0102", "Banco de Venezuela, S.A. Banco Universal", "BDV"),
    ("0104", "Banco Venezolano de Crédito, S.A. Banco Universal", "BVC"),
    ("0105", "Banco Mercantil C.A., Banco Universal", "Mercantil"),
    ("0108", "Banco Provincial, S.A. Banco Universal", "Provincial"),
    ("0114", "Banco del Caribe C.A., Banco Universal", "Bancaribe"),
    ("0115", "Banco Exterior C.A., Banco Universal", "Exterior"),
    ("0128", "Banco Caroní C.A., Banco Universal", "Caroní"),
    ("0134", "Banesco Banco Universal, C.A.", "Banesco"),
    ("0137", "Banco Sofitasa Banco Universal, C.A.", "Sofitasa"),
    ("0138", "Banco Plaza, Banco Universal", "Plaza"),
    ("0146", "Banco de la Gente Emprendedora C.A.", "Bangente"),
    ("0151", "Banco Fondo Común, C.A. Banco Universal", "BFC"),
    ("0156", "100% Banco, Banco Comercial, C.A.", "100% Banco"),
    ("0157", "DelSur, Banco Universal C.A.", "DelSur"),
    ("0163", "Banco del Tesoro C.A., Banco Universal", "Tesoro"),
    ("0166", "Banco Agrícola de Venezuela C.A., Banco Universal", "Agrícola"),
    ("0168", "Bancrecer S.A., Banco Microfinanciero", "Bancrecer"),
    ("0169", "Mi Banco, Banco Microfinanciero, C.A.", "Mi Banco"),
    ("0171", "Banco Activo C.A., Banco Universal", "Activo"),
    ("0172", "Bancamiga Banco Universal, C.A.", "Bancamiga"),
    ("0173", "Banco Internacional de Desarrollo C.A., Banco Universal", "BID"),
    ("0174", "Banplus Banco Universal, C.A.", "Banplus"),
    ("0175", "Banco Bicentenario del Pueblo, Banco Universal C.A.", "Bicentenario"),
    ("0177", "Banco de la Fuerza Armada Nacional Bolivariana, B.U.", "BANFANB"),
    ("0178", "N58 Banco Digital, Banco Microfinanciero", "N58"),
    ("0191", "Banco Nacional de Crédito C.A., Banco Universal", "BNC"),
    ("0601", "Instituto Municipal de Crédito Popular", "IMCP"),
]


class Command(BaseCommand):
    help = "Pobla el catálogo de bancos con los códigos Sudeban oficiales."

    def add_arguments(self, parser):
        parser.add_argument(
            "--update",
            action="store_true",
            help="Actualiza los bancos existentes (nombre, nombre_corto).",
        )

    def handle(self, *args, **options):
        creados = 0
        actualizados = 0

        for codigo, nombre, nombre_corto in BANCOS_SUDEBAN:
            if options["update"]:
                banco, created = Banco.objects.update_or_create(
                    codigo=codigo,
                    defaults={
                        "nombre": nombre,
                        "nombre_corto": nombre_corto,
                        "activo": True,
                    },
                )
            else:
                banco, created = Banco.objects.get_or_create(
                    codigo=codigo,
                    defaults={
                        "nombre": nombre,
                        "nombre_corto": nombre_corto,
                        "activo": True,
                    },
                )

            if created:
                creados += 1
                self.stdout.write(f"  ✅ Creado: {codigo} - {nombre_corto}")
            elif options["update"]:
                actualizados += 1
                self.stdout.write(f"  🔄 Actualizado: {codigo} - {nombre_corto}")

        self.stdout.write(self.style.SUCCESS(
            f"\n🎉 Bancos procesados: {creados} creados, {actualizados} actualizados."
        ))