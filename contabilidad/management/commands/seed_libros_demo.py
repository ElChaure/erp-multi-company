# contabilidad/management/commands/seed_libros_demo.py
"""
Crea facturas fiscales de prueba (compras y ventas) para poblar
los libros SENIAT con datos realistas.

Uso:
    python manage.py seed_libros_demo --dry-run
    python manage.py seed_libros_demo --confirm
    python manage.py seed_libros_demo --confirm --anio 2026 --mes 11 --cantidad 15
    python manage.py seed_libros_demo --confirm --reset  # borra las del mes primero
"""
from datetime import date, timedelta
from decimal import Decimal
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from rrhh.models import Empresa
from contabilidad.models import (
    ConfiguracionIVA,
    FacturaFiscal,
)


PROVEEDORES = [
    ("J-30123456-7", "Papeles y Tintas del Centro CA"),
    ("J-31234567-8", "Distribuidora Gráfica Nacional CA"),
    ("J-32345678-9", "Insumos Offset de Venezuela CA"),
    ("J-33456789-0", "Suministros Heidelberg CA"),
    ("J-34567890-1", "Repuestos Roland CA"),
]

CLIENTES = [
    ("J-40123456-7", "Alcaldía del Municipio Demo"),
    ("J-41234567-8", "Gobernación del Estado Demo"),
    ("J-42345678-9", "Ministerio de Educación Demo"),
    ("J-43456789-0", "Empresa Privada Alpha CA"),
    ("J-44567890-1", "Fundación Cultural Beta"),
    ("J-45678901-2", "Banco Nacional Demo"),
]


class Command(BaseCommand):
    help = "Crea facturas fiscales de prueba para poblar los libros SENIAT."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--anio", type=int, default=None)
        parser.add_argument("--mes", type=int, default=None)
        parser.add_argument("--cantidad", type=int, default=15)
        parser.add_argument("--reset", action="store_true",
                            help="Borra todas las facturas del mes antes de crear.")

    def handle(self, *args, **options):
        confirm = options["confirm"]
        reset = options["reset"]
        anio = options["anio"] or date.today().year
        mes = options["mes"] or date.today().month
        cantidad = options["cantidad"]

        empresa = Empresa.objects.filter(activa=True).first()
        if not empresa:
            self.stdout.write(self.style.ERROR("No hay empresas activas."))
            return

        self.stdout.write("=" * 70)
        self.stdout.write(f"  SEED LIBROS — {empresa.razon_social}")
        self.stdout.write("=" * 70)

        config_iva, created = ConfiguracionIVA.objects.get_or_create(
            empresa=empresa,
            defaults={
                "rif": "J-12345678-9",
                "razon_social": empresa.razon_social,
                "alicuota_general": Decimal("16.00"),
                "alicuota_reducida": Decimal("8.00"),
                "contribuyente_especial": False,
                "activa": True,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"  ✔ Config IVA creada: {config_iva}"))
        else:
            self.stdout.write(f"  • Config IVA existente: {config_iva}")

        fecha_base = date(anio, mes, 1)
        if mes == 12:
            fecha_fin = date(anio, 12, 31)
        else:
            fecha_fin = date(anio, mes + 1, 1) - timedelta(days=1)

        existentes_compra = FacturaFiscal.objects.filter(
            empresa=empresa, tipo="COMPRA",
            fecha_emision__year=anio, fecha_emision__month=mes,
        ).count()
        existentes_venta = FacturaFiscal.objects.filter(
            empresa=empresa, tipo="VENTA",
            fecha_emision__year=anio, fecha_emision__month=mes,
        ).count()

        self.stdout.write(f"\n  Facturas existentes en {mes:02d}/{anio}:")
        self.stdout.write(f"    Compras: {existentes_compra}")
        self.stdout.write(f"    Ventas:  {existentes_venta}")

        if reset:
            if confirm:
                eliminadas = FacturaFiscal.objects.filter(
                    empresa=empresa,
                    fecha_emision__year=anio,
                    fecha_emision__month=mes,
                ).delete()
                self.stdout.write(self.style.WARNING(
                    f"  Reset: {eliminadas[0]} factura(s) eliminadas del período."
                ))
                existentes_compra = 0
                existentes_venta = 0
            else:
                self.stdout.write(f"  [dry-run] Se borrarían todas las facturas del período.")

        if existentes_compra > 0 or existentes_venta > 0:
            self.stdout.write(self.style.WARNING(
                "\n  ⚠ Ya existen facturas en este período. "
                "Usa --reset para borrarlas antes de crear."
            ))

        self.stdout.write(f"\n  Se crearán {cantidad} facturas de compra y {cantidad} de venta.")
        self.stdout.write(f"  Rango de fechas: {fecha_base.strftime('%d/%m/%Y')} — {fecha_fin.strftime('%d/%m/%Y')}")

        if not confirm:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(
                "  Para ejecutar: python manage.py seed_libros_demo --confirm"
            )
            self.stdout.write("=" * 70)
            return

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("  EJECUTANDO...")
        self.stdout.write("=" * 70)

        creadas_compra = 0
        creadas_venta = 0
        errores = []

        # ─── COMPRAS (savepoint por factura) ───
        for i in range(cantidad):
            numero = existentes_compra + i + 1
            fecha = fecha_base + timedelta(days=random.randint(0, (fecha_fin - fecha_base).days))
            proveedor = random.choice(PROVEEDORES)
            base = Decimal(str(random.randint(500, 5000)))
            alicuota = Decimal("16.00")
            iva = (base * alicuota / 100).quantize(Decimal("0.01"))

            try:
                # savepoint: si falla, solo se revierte esta factura
                with transaction.atomic():
                    FacturaFiscal.objects.create(
                        empresa=empresa,
                        tipo="COMPRA",
                        estado="confirmada",
                        numero_factura=f"{numero:08d}",
                        numero_control=f"00-{numero:08d}",
                        fecha_emision=fecha,
                        rif_contraparte=proveedor[0],
                        razon_social_contraparte=proveedor[1],
                        base_imponible=base,
                        alicuota_iva=alicuota,
                        monto_iva=iva,
                        monto_total=base + iva,
                        tipo_transaccion="NACIONAL",
                        observaciones=f"Factura demo #{i+1}",
                    )
                creadas_compra += 1
                self.stdout.write(
                    f"  ✔ Compra #{numero:08d} — {proveedor[1][:30]} — Bs. {base:,.2f}"
                )
            except Exception as e:
                errores.append(f"Compra #{i+1}: {e}")
                self.stdout.write(self.style.ERROR(f"  ✘ Compra #{i+1}: {e}"))

        # ─── VENTAS (savepoint por factura) ───
        for i in range(cantidad):
            numero = existentes_venta + i + 1
            fecha = fecha_base + timedelta(days=random.randint(0, (fecha_fin - fecha_base).days))
            cliente = random.choice(CLIENTES)
            base = Decimal(str(random.randint(1000, 8000)))
            alicuota = Decimal("16.00")
            iva = (base * alicuota / 100).quantize(Decimal("0.01"))

            try:
                with transaction.atomic():
                    FacturaFiscal.objects.create(
                        empresa=empresa,
                        tipo="VENTA",
                        estado="confirmada",
                        numero_factura=f"{numero:08d}",
                        numero_control=f"00-{numero:08d}",
                        fecha_emision=fecha,
                        rif_contraparte=cliente[0],
                        razon_social_contraparte=cliente[1],
                        base_imponible=base,
                        alicuota_iva=alicuota,
                        monto_iva=iva,
                        monto_total=base + iva,
                        tipo_transaccion="NACIONAL",
                        observaciones=f"Venta demo #{i+1}",
                    )
                creadas_venta += 1
                self.stdout.write(
                    f"  ✔ Venta  #{numero:08d} — {cliente[1][:30]} — Bs. {base:,.2f}"
                )
            except Exception as e:
                errores.append(f"Venta #{i+1}: {e}")
                self.stdout.write(self.style.ERROR(f"  ✘ Venta #{i+1}: {e}"))

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("  RESUMEN")
        self.stdout.write("=" * 70)
        self.stdout.write(f"  Compras creadas: {creadas_compra}")
        self.stdout.write(f"  Ventas creadas:  {creadas_venta}")
        if errores:
            self.stdout.write(self.style.ERROR(f"  Errores: {len(errores)}"))
            for e in errores:
                self.stdout.write(self.style.ERROR(f"    {e}"))
        else:
            self.stdout.write(self.style.SUCCESS("  ✔ Todas las facturas creadas correctamente"))

        from django.db.models import Sum
        total_compra = FacturaFiscal.objects.filter(
            empresa=empresa, tipo="COMPRA",
            fecha_emision__year=anio, fecha_emision__month=mes,
        ).aggregate(base=Sum("base_imponible"), iva=Sum("monto_iva"), total=Sum("monto_total"))
        total_venta = FacturaFiscal.objects.filter(
            empresa=empresa, tipo="VENTA",
            fecha_emision__year=anio, fecha_emision__month=mes,
        ).aggregate(base=Sum("base_imponible"), iva=Sum("monto_iva"), total=Sum("monto_total"))

        self.stdout.write(f"\n  Totales del período {mes:02d}/{anio}:")
        self.stdout.write(f"    Compras — Base: Bs. {total_compra['base'] or 0:,.2f} | "
                          f"IVA: Bs. {total_compra['iva'] or 0:,.2f} | "
                          f"Total: Bs. {total_compra['total'] or 0:,.2f}")
        self.stdout.write(f"    Ventas  — Base: Bs. {total_venta['base'] or 0:,.2f} | "
                          f"IVA: Bs. {total_venta['iva'] or 0:,.2f} | "
                          f"Total: Bs. {total_venta['total'] or 0:,.2f}")
        self.stdout.write("=" * 70)