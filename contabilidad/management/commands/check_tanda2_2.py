# contabilidad/management/commands/check_tanda2_2.py
"""
Comando de verificación de la Tanda 2.2 / 2.3a.

Verifica que resolver_cuenta_contable respete:
  1. Fallback por código cuando no hay configuración.
  2. Configuración explícita de cuentas de movimiento (MP, MOD, CIF).
  3. Rechazo de cuentas agrupadoras en la configuración.
  4. Config vacía → sigue cayendo al fallback.

Uso:
    python manage.py check_tanda2_2
"""
from django.core.management.base import BaseCommand

from rrhh.models import Empresa
from contabilidad.models import PlanCuenta, ConfiguracionContableCostos
from contabilidad.services import resolver_cuenta_contable


# Campos de la config que se van a probar (post Sprint 2.3a)
CAMPOS_COSTO = [
    "cuenta_inventario_pt",
    "cuenta_costo_mp",
    "cuenta_costo_mod",
    "cuenta_costo_cif",
    "cuenta_sueldos_por_pagar",
]


class Command(BaseCommand):
    help = "Verifica el helper resolver_cuenta_contable (Tandas 2.2 / 2.3a)."

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("  VERIFICACIÓN TANDA 2.2 / 2.3a — resolver_cuenta_contable")
        self.stdout.write("=" * 60)

        emp = Empresa.objects.filter(activa=True).first()
        if not emp:
            self.stdout.write(self.style.ERROR("No hay empresas activas en la BD."))
            return
        self.stdout.write(f"Empresa: {emp.razon_social} (ID {emp.id})\n")

        # Limpiar config previa
        ConfiguracionContableCostos.objects.filter(empresa=emp).delete()

        # ═══════════════════════════════════════════════════════
        #  1. SIN CONFIGURACIÓN: fallback por código
        # ═══════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING("=== 1. Sin configuración explícita (fallback por código) ==="))

        for campo in CAMPOS_COSTO:
            r = resolver_cuenta_contable(emp, campo)
            marca = "✔" if (r and not r.es_agrupadora) else "✘"
            estilo = self.style.SUCCESS if marca == "✔" else self.style.ERROR
            self.stdout.write(estilo(f"  {marca} {campo:25s} → {r}"))
        self.stdout.write("")

        # ═══════════════════════════════════════════════════════
        #  2. CONFIG EXPLÍCITA con cuentas de movimiento
        # ═══════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING(
            "=== 2. Configuración explícita (cuentas de movimiento) ==="
        ))

        cuentas_mov = list(
            PlanCuenta.objects.filter(empresa=emp, activa=True, es_agrupadora=False)
            .order_by("codigo")[:len(CAMPOS_COSTO)]
        )

        if len(cuentas_mov) < len(CAMPOS_COSTO):
            self.stdout.write(self.style.WARNING(
                f"  Solo hay {len(cuentas_mov)} cuentas de movimiento. "
                f"Se necesitan {len(CAMPOS_COSTO)}. Saltando esta prueba."
            ))
        else:
            defaults = {
                campo: cuentas_mov[i] for i, campo in enumerate(CAMPOS_COSTO)
            }
            config, _ = ConfiguracionContableCostos.objects.update_or_create(
                empresa=emp,
                defaults=defaults,
            )
            try:
                for campo in CAMPOS_COSTO:
                    esperada = defaults[campo]
                    r = resolver_cuenta_contable(emp, campo)
                    ok = r and r.id == esperada.id
                    marca = "✔" if ok else "✘"
                    estilo = self.style.SUCCESS if ok else self.style.ERROR
                    self.stdout.write(estilo(
                        f"  {marca} {campo:25s} → {r}  (esperado: {esperada.codigo})"
                    ))
            finally:
                config.delete()
                self.stdout.write("  (config temporal eliminada)")
        self.stdout.write("")

        # ═══════════════════════════════════════════════════════
        #  3. CONFIG con agrupadora: debe ignorarla
        # ═══════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING(
            "=== 3. Config con cuenta agrupadora (debe ignorarla) ==="
        ))

        agrupadora = PlanCuenta.objects.filter(
            empresa=emp, activa=True, es_agrupadora=True
        ).first()
        if not agrupadora:
            self.stdout.write(self.style.WARNING("  No hay cuentas agrupadoras. Saltando."))
        else:
            config, _ = ConfiguracionContableCostos.objects.update_or_create(
                empresa=emp,
                defaults={"cuenta_inventario_pt": agrupadora},
            )
            try:
                r = resolver_cuenta_contable(emp, "cuenta_inventario_pt")
                ok = r is None or (r.id != agrupadora.id and not r.es_agrupadora)
                marca = "✔" if ok else "✘"
                estilo = self.style.SUCCESS if ok else self.style.ERROR
                self.stdout.write(estilo(
                    f"  {marca} Configurado con agrupadora {agrupadora.codigo} → resolvió {r}"
                ))
            finally:
                config.delete()
        self.stdout.write("")

        # ═══════════════════════════════════════════════════════
        #  4. CONFIG vacía: fallback por código
        # ═══════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING(
            "=== 4. Config vacía (todos los campos en None) ==="
        ))

        config, _ = ConfiguracionContableCostos.objects.update_or_create(
            empresa=emp,
            defaults={campo: None for campo in CAMPOS_COSTO},
        )
        try:
            for campo in CAMPOS_COSTO:
                r = resolver_cuenta_contable(emp, campo)
                ok = r is not None
                marca = "✔" if ok else "✘"
                estilo = self.style.SUCCESS if ok else self.style.ERROR
                self.stdout.write(estilo(f"  {marca} {campo:25s} → {r}"))
        finally:
            config.delete()
        self.stdout.write("")

        # ═══════════════════════════════════════════════════════
        #  5. ALIAS LEGACY: "cuenta_costo_produccion" → "cuenta_costo_mod"
        # ═══════════════════════════════════════════════════════
        self.stdout.write(self.style.MIGRATE_HEADING(
            "=== 5. Alias legacy 'cuenta_costo_produccion' → 'cuenta_costo_mod' ==="
        ))
        try:
            r_legacy = resolver_cuenta_contable(emp, "cuenta_costo_produccion")
            r_nuevo = resolver_cuenta_contable(emp, "cuenta_costo_mod")
            ok = (r_legacy and r_nuevo and r_legacy.id == r_nuevo.id)
            marca = "✔" if ok else "✘"
            estilo = self.style.SUCCESS if ok else self.style.ERROR
            self.stdout.write(estilo(
                f"  {marca} legacy → {r_legacy}"
            ))
            self.stdout.write(estilo(
                f"  {marca} nuevo  → {r_nuevo}"
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✘ Error: {e}"))
        self.stdout.write("")

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("  VERIFICACIÓN COMPLETA"))
        self.stdout.write("=" * 60)