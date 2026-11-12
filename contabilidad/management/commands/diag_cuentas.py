# contabilidad/management/commands/diag_cuentas.py
"""
Diagnóstico profundo del Plan de Cuentas y del helper resolver_cuenta_contable.
Uso:
    python manage.py diag_cuentas
"""
from django.core.management.base import BaseCommand

from rrhh.models import Empresa
from contabilidad.models import PlanCuenta, ConfiguracionContableCostos
from contabilidad.services import resolver_cuenta_contable
from contabilidad.constants import (
    CUENTA_SUELDOS_POR_PAGAR,
    CUENTA_INVENTARIO_PT,
    CUENTA_COSTO_PRODUCCION,
    NOMBRE_SUELDOS_POR_PAGAR,
)


class Command(BaseCommand):
    help = "Diagnóstico del Plan de Cuentas y del helper resolver_cuenta_contable."

    def handle(self, *args, **options):
        emp = Empresa.objects.filter(activa=True).first()
        if not emp:
            self.stdout.write(self.style.ERROR("No hay empresas activas."))
            return

        self.stdout.write("=" * 70)
        self.stdout.write(f"  DIAGNÓSTICO — {emp.razon_social} (ID {emp.id})")
        self.stdout.write("=" * 70)

        # ═══════════════════════════════════════════════════════
        #  1. Plan de cuentas — resumen
        # ═══════════════════════════════════════════════════════
        total = PlanCuenta.objects.filter(empresa=emp).count()
        activas = PlanCuenta.objects.filter(empresa=emp, activa=True).count()
        agrupadoras = PlanCuenta.objects.filter(empresa=emp, es_agrupadora=True).count()

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== 1. Resumen del Plan de Cuentas ==="))
        self.stdout.write(f"  Total cuentas:       {total}")
        self.stdout.write(f"  Activas:             {activas}")
        self.stdout.write(f"  Agrupadoras:         {agrupadoras}")

        # ═══════════════════════════════════════════════════════
        #  2. ¿Existen las cuentas esperadas?
        # ═══════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== 2. ¿Existen las cuentas por código? ==="))
        for prefijo, etiqueta in [
            (CUENTA_INVENTARIO_PT, "Inventario PT (esperado 110303)"),
            (CUENTA_COSTO_PRODUCCION, "Costo Producción (esperado 5102)"),
            (CUENTA_SUELDOS_POR_PAGAR, "Sueldos por Pagar (esperado 210102)"),
        ]:
            qs = PlanCuenta.objects.filter(empresa=emp, codigo__startswith=prefijo)
            count = qs.count()
            if count == 0:
                self.stdout.write(
                    self.style.ERROR(f"  ✘ {etiqueta}: NO existe (prefijo '{prefijo}')")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✔ {etiqueta}: {count} coincidencia(s)")
                )
                for c in qs[:3]:
                    self.stdout.write(
                        f"      → {c.codigo} - {c.nombre} "
                        f"(activa={c.activa}, agrupadora={c.es_agrupadora})"
                    )

        # ═══════════════════════════════════════════════════════
        #  3. Todas las cuentas con su jerarquía (primeras 40)
        # ═══════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== 3. Primeras 40 cuentas (código - nombre - tipo - naturaleza - activa - agrupadora) ==="))
        cuentas = PlanCuenta.objects.filter(empresa=emp).order_by("codigo")[:40]
        for c in cuentas:
            marca_act = "✓" if c.activa else "✗"
            marca_agr = "AG" if c.es_agrupadora else "  "
            self.stdout.write(
                f"  {c.codigo:12s} | {c.nombre[:40]:40s} | "
                f"{c.tipo:10s} | {c.naturaleza} | {marca_act} | {marca_agr}"
            )

        if total > 40:
            self.stdout.write(f"  ... ({total - 40} cuentas más)")

        # ═══════════════════════════════════════════════════════
        #  4. ¿Existe configuración guardada?
        # ═══════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== 4. Configuración guardada ==="))
        config = ConfiguracionContableCostos.objects.filter(empresa=emp).first()
        if config:
            self.stdout.write("  Hay configuración guardada:")
            self.stdout.write(f"    cuenta_inventario_pt   = {config.cuenta_inventario_pt}")
            self.stdout.write(f"    cuenta_costo_produccion = {config.cuenta_costo_produccion}")
            self.stdout.write(f"    cuenta_sueldos_por_pagar = {config.cuenta_sueldos_por_pagar}")
        else:
            self.stdout.write("  (no hay configuración guardada — usa el fallback de constantes)")

        # ═══════════════════════════════════════════════════════
        #  5. Traza del helper: qué devuelve y por qué
        # ═══════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== 5. Traza del helper resolver_cuenta_contable ==="))
        for campo in ["cuenta_inventario_pt", "cuenta_costo_produccion", "cuenta_sueldos_por_pagar"]:
            r = resolver_cuenta_contable(emp, campo)
            self.stdout.write(f"\n  {campo}:")
            self.stdout.write(f"    resolver_cuenta_contable() → {r}")
            if r:
                self.stdout.write(
                    f"    Detalle: codigo={r.codigo}, "
                    f"activa={r.activa}, "
                    f"agrupadora={r.es_agrupadora}, "
                    f"tipo={r.tipo}"
                )

        # ═══════════════════════════════════════════════════════
        #  6. Caso especial: "pagar" puede matchear con cuentas por pagar
        # ═══════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== 6. Búsqueda por nombre 'sueldo'+'pagar' ==="))
        qs = PlanCuenta.objects.filter(empresa=emp, activa=True)
        for palabra in NOMBRE_SUELDOS_POR_PAGAR:
            qs = qs.filter(nombre__icontains=palabra)
        self.stdout.write(f"  Query: nombre contiene {NOMBRE_SUELDOS_POR_PAGAR}")
        self.stdout.write(f"  Resultados: {qs.count()}")
        for c in qs[:5]:
            self.stdout.write(f"    → {c.codigo} - {c.nombre}")

        # ═══════════════════════════════════════════════════════
        #  7. Veredicto
        # ═══════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== 7. VEREDICTO ==="))
        problemas = []
        for prefijo, etiqueta in [
            (CUENTA_INVENTARIO_PT, "Inventario PT"),
            (CUENTA_COSTO_PRODUCCION, "Costo Producción"),
            (CUENTA_SUELDOS_POR_PAGAR, "Sueldos por Pagar"),
        ]:
            if not PlanCuenta.objects.filter(empresa=emp, codigo__startswith=prefijo).exists():
                problemas.append(f"Falta cuenta con código '{prefijo}' ({etiqueta})")

        if not problemas:
            self.stdout.write(self.style.SUCCESS("  ✔ Plan de cuentas completo para costos/nómina"))
        else:
            self.stdout.write(self.style.WARNING("  ⚠ Problemas detectados:"))
            for p in problemas:
                self.stdout.write(self.style.WARNING(f"    - {p}"))

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write("  FIN DEL DIAGNÓSTICO")
        self.stdout.write("=" * 70)