# check_tanda3.py — Verificación Tanda 3 (ejecutar con: python manage.py shell < check_tanda3.py)
import inspect

# ─── 1. Constantes cargables ───
from contabilidad.constants import (
    CUENTA_SUELDOS_POR_PAGAR,
    CUENTA_INVENTARIO_PT,
    CUENTA_COSTO_PRODUCCION,
    NOMBRE_SUELDOS_POR_PAGAR,
    ORIGEN_NOMINA,
    ORIGEN_COSTOS,
    ORIGEN_ACTIVOS,
    ORIGEN_COMPROBANTE_BORRADOR,
)

print("CUENTA_SUELDOS_POR_PAGAR =", CUENTA_SUELDOS_POR_PAGAR)
print("CUENTA_INVENTARIO_PT =", CUENTA_INVENTARIO_PT)
print("CUENTA_COSTO_PRODUCCION =", CUENTA_COSTO_PRODUCCION)
print("NOMBRE_SUELDOS_POR_PAGAR =", NOMBRE_SUELDOS_POR_PAGAR)
print("ORIGEN_NOMINA =", ORIGEN_NOMINA)
print("ORIGEN_COSTOS =", ORIGEN_COSTOS)
print("ORIGEN_ACTIVOS =", ORIGEN_ACTIVOS)
print("ORIGEN_COMPROBANTE_BORRADOR =", ORIGEN_COMPROBANTE_BORRADOR)

assert CUENTA_SUELDOS_POR_PAGAR == "210102"
assert CUENTA_INVENTARIO_PT == "110303"
assert CUENTA_COSTO_PRODUCCION == "5102"
print("OK: constantes cargadas")

# ─── 2. Verificar que ya no hay códigos hardcodeados en los servicios ───
from contabilidad import services as cont_services
from costos import services as cost_services

src_cont = inspect.getsource(cont_services)
src_cost = inspect.getsource(cost_services)

# Buscamos los strings EXACTOS entre comillas simples y dobles
hardcoded_cont = ('"210102"' in src_cont) or ("'210102'" in src_cont)
hardcoded_cost_1 = ('"110303"' in src_cost) or ("'110303'" in src_cost)
hardcoded_cost_2 = ('"5102"' in src_cost) or ("'5102'" in src_cost)

assert not hardcoded_cont, "Aun hay 210102 hardcodeado en contabilidad/services.py"
assert not hardcoded_cost_1, "Aun hay 110303 hardcodeado en costos/services.py"
assert not hardcoded_cost_2, "Aun hay 5102 hardcodeado en costos/services.py"
print("OK: no hay codigos de cuenta hardcodeados en los servicios")

# ─── 3. Smoke test: buscar cuenta de sueldos por pagar ───
from rrhh.models import Empresa
from contabilidad.services import _obtener_cuenta_sueldos_por_pagar

emp = Empresa.objects.first()
if emp:
    cuenta = _obtener_cuenta_sueldos_por_pagar(emp)
    if cuenta:
        print(f"Cuenta encontrada: {cuenta.codigo} - {cuenta.nombre}")
    else:
        print("AVISO: no se encontro cuenta de Sueldos por Pagar (revisar seed_plan_cuentas)")
else:
    print("No hay empresas (ok)")

print()
print("=" * 60)
print("TANDA 3 VERIFICADA CORRECTAMENTE")
print("=" * 60)