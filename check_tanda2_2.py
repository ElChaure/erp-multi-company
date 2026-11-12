# check_tanda2_2.py
from rrhh.models import Empresa
from contabilidad.models import PlanCuenta, ConfiguracionContableCostos
from contabilidad.services import resolver_cuenta_contable

emp = Empresa.objects.first()
print("Empresa:", emp)

# ─── 1. Sin configuración: debe caer a la constante ───
print("\n=== Sin configuración ===")
c = resolver_cuenta_contable(emp, "cuenta_inventario_pt")
print("cuenta_inventario_pt →", c)
assert c is None or c.codigo.startswith("110303"), "Debe ser 110303 o None"

c = resolver_cuenta_contable(emp, "cuenta_costo_produccion")
print("cuenta_costo_produccion →", c)
assert c is None or c.codigo.startswith("5102"), "Debe ser 5102 o None"

c = resolver_cuenta_contable(emp, "cuenta_sueldos_por_pagar")
print("cuenta_sueldos_por_pagar →", c)
assert c is None or c.codigo.startswith("210102"), "Debe ser 210102 o None"

# ─── 2. Con configuración explícita: debe preferirla ───
print("\n=== Con configuración explícita ===")
# Buscar cualquier cuenta del plan
cuentas = PlanCuenta.objects.filter(empresa=emp, activa=True).order_by("codigo")
print("Cuentas disponibles:", cuentas.count())
if cuentas.count() >= 3:
    c1, c2, c3 = cuentas[0], cuentas[1], cuentas[2]
    config, _ = ConfiguracionContableCostos.objects.update_or_create(
        empresa=emp,
        defaults={
            "cuenta_inventario_pt": c1,
            "cuenta_costo_produccion": c2,
            "cuenta_sueldos_por_pagar": c3,
        },
    )
    r1 = resolver_cuenta_contable(emp, "cuenta_inventario_pt")
    r2 = resolver_cuenta_contable(emp, "cuenta_costo_produccion")
    r3 = resolver_cuenta_contable(emp, "cuenta_sueldos_por_pagar")
    print(f"inventario_pt  → {r1.codigo} (esperado {c1.codigo})")
    print(f"costo_produccion → {r2.codigo} (esperado {c2.codigo})")
    print(f"sueldos_por_pagar → {r3.codigo} (esperado {c3.codigo})")
    assert r1.id == c1.id
    assert r2.id == c2.id
    assert r3.id == c3.id

    # Limpiar
    config.delete()

print("\n✅ Tanda 2.2 OK")