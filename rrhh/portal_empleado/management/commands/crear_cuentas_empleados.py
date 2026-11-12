"""
Comando de management: crear_cuentas_empleados

Crea cuentas de autoservicio (User + CuentaEmpleado) para los empleados
activos de una empresa. Opcionalmente resetea passwords de cuentas existentes.

Uso:
    # Ver qué haría, sin guardar nada
    python manage.py crear_cuentas_empleados --empresa-id 1 --dry-run

    # Crear cuentas para empleados que NO las tengan (omite existentes)
    python manage.py crear_cuentas_empleados --empresa-id 1

    # Crear + resetear passwords de cuentas existentes
    python manage.py crear_cuentas_empleados --empresa-id 1 --reset-passwords

    # Todas las empresas activas
    python manage.py crear_cuentas_empleados --todas-empresas

    # Password distinto a la cédula
    python manage.py crear_cuentas_empleados --empresa-id 1 --password "MiClave123"

    # Solo un empleado específico
    python manage.py crear_cuentas_empleados --empleado-id 5
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from rrhh.models import Empleado, Empresa
from rrhh.portal_empleado.models import CuentaEmpleado


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def _normalizar_cedula(cedula):
    """Quita prefijos y separadores de la cédula."""
    if not cedula:
        return ""
    return (
        str(cedula).strip()
        .replace("V-", "").replace("E-", "")
        .replace("V", "").replace("E", "")
        .replace(".", "").replace("-", "").replace(" ", "")
        .strip()
    )


def _generar_username(empleado):
    """
    Genera el username a partir de la cédula + número de empleado.
    Ej: cédula=12345678, numero=EMP-0001 → "12345678_emp_0001"
    """
    cedula = _normalizar_cedula(empleado.cedula)
    numero = (empleado.numero_empleado or "").strip().lower().replace("-", "_")
    return f"{cedula}_{numero}"


def _generar_password(empleado, password_override=None):
    """Devuelve el password a asignar (cédula por defecto)."""
    if password_override:
        return password_override
    return _normalizar_cedula(empleado.cedula)


# ═══════════════════════════════════════════════════════════
# COMANDO
# ═══════════════════════════════════════════════════════════

class Command(BaseCommand):
    help = (
        "Crea cuentas de autoservicio (User + CuentaEmpleado) para "
        "los empleados activos de una empresa. Con --reset-passwords "
        "también actualiza el password de las cuentas existentes."
    )

    def add_arguments(self, parser):
        # Filtros
        parser.add_argument(
            "--empresa-id",
            type=int,
            help="ID de la empresa a procesar.",
        )
        parser.add_argument(
            "--empleado-id",
            type=int,
            help="ID de un empleado específico (sobrescribe --empresa-id).",
        )
        parser.add_argument(
            "--todas-empresas",
            action="store_true",
            help="Procesar todas las empresas activas.",
        )
        # Comportamiento
        parser.add_argument(
            "--password",
            type=str,
            help="Password a asignar (default: la cédula del empleado).",
        )
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="También resetea el password de cuentas existentes.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra lo que haría, sin guardar cambios.",
        )

    # ─────────────────────────────────────────────────────
    # HANDLE
    # ─────────────────────────────────────────────────────

    def handle(self, *args, **options):
        empresa_id = options.get("empresa_id")
        empleado_id = options.get("empleado_id")
        todas = options["todas_empresas"]
        password_override = options.get("password")
        reset_passwords = options["reset_passwords"]
        dry_run = options["dry_run"]

        if not (empresa_id or empleado_id or todas):
            raise CommandError(
                "Debes especificar --empresa-id N, --empleado-id N "
                "o --todas-empresas."
            )

        self.stdout.write(self.style.NOTICE(
            "\n═══ Creación de cuentas de empleado ═══\n"
        ))
        self.stdout.write(f"Modo: {'DRY-RUN (sin guardar)' if dry_run else 'REAL'}")
        self.stdout.write(
            f"Reset passwords existentes: {'SÍ' if reset_passwords else 'NO'}\n"
        )

        # Acumuladores globales
        total_creados = 0
        total_reseteados = 0
        total_omitidos = 0
        total_errores = 0
        detalle_acciones = []

        # Determinar el queryset de empresas/empleados
        if empleado_id:
            try:
                empleado = Empleado.objects.select_related("empresa").get(pk=empleado_id)
            except Empleado.DoesNotExist:
                raise CommandError(f"No existe el empleado con ID {empleado_id}.")

            empresas_a_procesar = [empleado.empresa]
            empleados_filtro = Empleado.objects.filter(pk=empleado.id)
        else:
            if todas:
                empresas_a_procesar = list(Empresa.objects.filter(activa=True))
            else:
                try:
                    empresa = Empresa.objects.get(pk=empresa_id)
                except Empresa.DoesNotExist:
                    raise CommandError(f"No existe la empresa con ID {empresa_id}.")
                empresas_a_procesar = [empresa]
            empleados_filtro = None  # se calcula por empresa

        if not empresas_a_procesar:
            raise CommandError("No hay empresas para procesar.")

        # Procesar cada empresa
        for empresa in empresas_a_procesar:
            self.stdout.write(self.style.NOTICE(
                f"\n─── {empresa.razon_social} ───"
            ))

            if empleados_filtro is not None:
                empleados = empleados_filtro
            else:
                empleados = Empleado.objects.filter(
                    empresa=empresa,
                    estatus="activo",
                ).order_by("numero_empleado")

            total_empresa = empleados.count()
            self.stdout.write(f"Empleados activos: {total_empresa}\n")

            if total_empresa == 0:
                self.stdout.write(self.style.WARNING(
                    "  (sin empleados activos en esta empresa)\n"
                ))
                continue

            for empleado in empleados:
                resultado = self._procesar_empleado(
                    empleado=empleado,
                    password_override=password_override,
                    reset_passwords=reset_passwords,
                    dry_run=dry_run,
                )
                detalle_acciones.append(resultado)

                # Actualizar contadores
                accion = resultado["accion"]
                if accion == "creado":
                    total_creados += 1
                elif accion == "reseteado":
                    total_reseteados += 1
                elif accion == "omitido":
                    total_omitidos += 1
                elif accion == "error":
                    total_errores += 1

        # ─── Resumen final ─────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("═══ Resumen ═══"))
        self.stdout.write(f"  Creados:      {total_creados}")
        self.stdout.write(f"  Reseteados:   {total_reseteados}")
        self.stdout.write(f"  Omitidos:     {total_omitidos}")
        self.stdout.write(f"  Errores:      {total_errores}")

        # ─── Detalle línea por línea ───────────────────────
        if detalle_acciones:
            self.stdout.write("")
            self.stdout.write(self.style.NOTICE("═══ Detalle ═══"))

            for r in detalle_acciones:
                accion = r["accion"]
                numero = r.get("numero_empleado", "?")
                nombre = r.get("nombre", "?")
                username = r.get("username", "—")

                if accion == "creado":
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✅ {numero} {nombre}"
                    ))
                    self.stdout.write(
                        f"      username: {username}"
                    )
                    self.stdout.write(
                        f"      password: {r.get('password', '—')}"
                    )
                elif accion == "reseteado":
                    self.stdout.write(self.style.WARNING(
                        f"  🔄 {numero} {nombre} (password reseteado)"
                    ))
                    self.stdout.write(
                        f"      username: {username}"
                    )
                    self.stdout.write(
                        f"      nuevo password: {r.get('password', '—')}"
                    )
                elif accion == "omitido":
                    self.stdout.write(
                        f"  ⏭️  {numero} {nombre} "
                        f"(ya tenía cuenta: {username})"
                    )
                elif accion == "error":
                    self.stdout.write(self.style.ERROR(
                        f"  ❌ {numero} {nombre}: {r.get('error', '?')}"
                    ))

        # Cierre
        self.stdout.write("")
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "💡 Ejecutá sin --dry-run para guardar los cambios."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "🎉 Proceso completado."
            ))

    # ─────────────────────────────────────────────────────
    # PROCESAR UN EMPLEADO
    # ─────────────────────────────────────────────────────

    @transaction.atomic
    def _procesar_empleado(self, empleado, password_override, reset_passwords, dry_run):
        """
        Crea o resetea la cuenta de un empleado.

        Returns:
            dict con: accion, numero_empleado, nombre, username, password, error
        """
        numero = empleado.numero_empleado
        nombre = empleado.nombre_completo

        # Validaciones previas
        if not empleado.cedula:
            return {
                "accion": "error",
                "numero_empleado": numero,
                "nombre": nombre,
                "error": "El empleado no tiene cédula.",
            }

        # ¿Ya tiene cuenta?
        cuenta_existente = getattr(empleado, "cuenta_empleado", None)

        if cuenta_existente:
            if reset_passwords:
                # Resetear password
                username = cuenta_existente.usuario.username
                password = _generar_password(empleado, password_override)

                if not dry_run:
                    cuenta_existente.usuario.set_password(password)
                    cuenta_existente.usuario.save(update_fields=["password"])

                return {
                    "accion": "reseteado",
                    "numero_empleado": numero,
                    "nombre": nombre,
                    "username": username,
                    "password": password,
                }
            else:
                # Omitir
                return {
                    "accion": "omitido",
                    "numero_empleado": numero,
                    "nombre": nombre,
                    "username": cuenta_existente.usuario.username,
                }

        # ─── Crear cuenta nueva ────────────────────────────
        try:
            username = _generar_username(empleado)
            password = _generar_password(empleado, password_override)

            # Verificar colisión de username
            if User.objects.filter(username=username).exists():
                return {
                    "accion": "error",
                    "numero_empleado": numero,
                    "nombre": nombre,
                    "error": f"El username '{username}' ya existe pero no está "
                             f"vinculado a este empleado. Revisar manualmente.",
                }

            if dry_run:
                return {
                    "accion": "creado",
                    "numero_empleado": numero,
                    "nombre": nombre,
                    "username": username,
                    "password": password,
                }

            # Crear User
            user = User.objects.create_user(
                username=username,
                email=empleado.email or "",
                password=password,
                first_name=empleado.nombre,
                last_name=f"{empleado.apellido_paterno} {empleado.apellido_materno}".strip(),
            )

            # Crear CuentaEmpleado
            CuentaEmpleado.objects.create(
                empleado=empleado,
                usuario=user,
                activo=True,
                email_verificado=True,
                creado_por=None,  # creado por comando (sistema)
            )

            # Crear Perfil si el user es nuevo y no tiene
            # (solo si el modelo Perfil existe)
            try:
                from rrhh.models import Perfil
                if not hasattr(user, "perfil"):
                    Perfil.objects.create(
                        usuario=user,
                        rol="empleado",
                        empresa=empleado.empresa,
                        empleado=empleado,
                    )
            except ImportError:
                pass  # Perfil no existe, ok
            except Exception as e:
                # No rompemos el flujo por un error de Perfil
                self.stdout.write(self.style.WARNING(
                    f"  ⚠️  No se pudo crear Perfil para {numero}: {e}"
                ))

            return {
                "accion": "creado",
                "numero_empleado": numero,
                "nombre": nombre,
                "username": username,
                "password": password,
            }

        except Exception as e:
            return {
                "accion": "error",
                "numero_empleado": numero,
                "nombre": nombre,
                "error": str(e),
            }