"""
Genera los saldos de vacaciones anuales para todos los empleados.

Uso:
    python manage.py generar_saldos_anuales --anio 2026
    python manage.py generar_saldos_anuales --anio 2026 --empresa-id 1
    python manage.py generar_saldos_anuales --anio 2026 --empleado-id 5
    python manage.py generar_saldos_anuales --anio 2026 --todas-empresas
    python manage.py generar_saldos_anuales --anio 2026 --dry-run
    python manage.py generar_saldos_anuales --anio 2026 --incluir-egresados
    python manage.py generar_saldos_anuales --anio 2026 --recalcular

Se ejecuta típicamente:
    - Al cierre del año (diciembre) para causar el saldo del próximo año
    - Al inicio del año para asegurar que todos tengan su saldo
    - Manualmente por RRHH cuando ingresa un empleado nuevo
"""
from django.core.management.base import BaseCommand, CommandError

from rrhh.models import Empleado, Empresa
from rrhh.ausencias.vacaciones_services import (
    generar_saldo_anual,
    generar_saldos_masivos,
    recalcular_saldo,
)


class Command(BaseCommand):
    help = (
        "Genera los saldos de vacaciones anuales para los empleados. "
        "Crea (o actualiza) un SaldoVacaciones por empleado y año."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--anio",
            type=int,
            required=True,
            help="Año para el cual generar los saldos (ej: 2026).",
        )
        parser.add_argument(
            "--empresa-id",
            type=int,
            help="ID de empresa específica.",
        )
        parser.add_argument(
            "--empleado-id",
            type=int,
            help="ID de empleado específico (sobrescribe --empresa-id).",
        )
        parser.add_argument(
            "--todas-empresas",
            action="store_true",
            help="Procesar todas las empresas activas.",
        )
        parser.add_argument(
            "--incluir-egresados",
            action="store_true",
            help="Incluir empleados con estatus 'baja'.",
        )
        parser.add_argument(
            "--recalcular",
            action="store_true",
            help="Si el saldo ya existe, recalcular sus días de derecho.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra lo que haría, sin guardar cambios.",
        )

    def handle(self, *args, **options):
        anio = options["anio"]
        empresa_id = options.get("empresa_id")
        empleado_id = options.get("empleado_id")
        todas = options["todas_empresas"]
        incluir_egresados = options["incluir_egresados"]
        recalcular = options["recalcular"]
        dry_run = options["dry_run"]

        # Validar combinaciones
        if not (empresa_id or empleado_id or todas):
            raise CommandError(
                "Debes especificar --empresa-id N, --empleado-id N "
                "o --todas-empresas."
            )

        # Encabezado
        self.stdout.write(self.style.NOTICE(
            f"\n═══ Generación de saldos de vacaciones ═══"
        ))
        self.stdout.write(f"Año: {anio}")
        self.stdout.write(
            f"Modo: {'DRY-RUN (sin guardar)' if dry_run else 'REAL'}"
        )
        self.stdout.write("")

        # Caso: empleado específico
        if empleado_id:
            try:
                empleado = Empleado.objects.select_related(
                    "empresa"
                ).get(pk=empleado_id)
            except Empleado.DoesNotExist:
                raise CommandError(f"No existe el empleado con ID {empleado_id}.")

            self.stdout.write(
                f"Procesando empleado: {empleado.numero_empleado} - "
                f"{empleado.nombre_completo}\n"
            )

            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f"  [DRY] Se generaría saldo para el año {anio}."
                ))
                return

            existia = empleado.saldos_vacaciones.filter(anio=anio).exists()

            if existia and recalcular:
                saldo = empleado.saldos_vacaciones.get(anio=anio)
                saldo = recalcular_saldo(saldo)
                self.stdout.write(self.style.SUCCESS(
                    f"  ✅ Recalculado: {saldo.dias_derecho} días de derecho "
                    f"(pendientes: {saldo.dias_pendientes})"
                ))
            else:
                saldo = generar_saldo_anual(empleado, anio)
                accion = "Actualizado" if existia else "Creado"
                self.stdout.write(self.style.SUCCESS(
                    f"  ✅ {accion}: {saldo.dias_derecho} días de derecho "
                    f"(pendientes: {saldo.dias_pendientes})"
                ))
            return

        # Caso: empresa(s)
        if todas:
            empresas = Empresa.objects.filter(activa=True)
        else:
            empresas = Empresa.objects.filter(id=empresa_id)
            if not empresas.exists():
                raise CommandError(f"No existe la empresa con ID {empresa_id}.")

        self.stdout.write(
            f"Empresas a procesar: {empresas.count()}\n"
        )

        total_creados = 0
        total_actualizados = 0
        total_omitidos = 0
        total_errores = 0

        for empresa in empresas:
            self.stdout.write(self.style.NOTICE(
                f"─── {empresa.razon_social} ───"
            ))

            if dry_run:
                empleados = Empleado.objects.filter(
                    empresa=empresa,
                    fecha_ingreso__year__lte=anio,
                )
                if not incluir_egresados:
                    empleados = empleados.filter(estatus="activo")

                self.stdout.write(
                    self.style.WARNING(
                        f"  [DRY] Se procesarían {empleados.count()} empleados."
                    )
                )
                continue

            try:
                resultado = generar_saldos_masivos(
                    empresa=empresa,
                    anio=anio,
                    incluir_egresados=incluir_egresados,
                )

                self.stdout.write(
                    f"  Creados: {resultado['creados']} | "
                    f"Actualizados: {resultado['actualizados']} | "
                    f"Omitidos: {resultado['omitidos']} | "
                    f"Errores: {len(resultado['errores'])}"
                )

                # Mostrar errores si hay
                if resultado["errores"]:
                    for err in resultado["errores"][:10]:  # solo primeros 10
                        self.stdout.write(self.style.ERROR(
                            f"    ❌ {err['empleado']}: {err['error']}"
                        ))

                total_creados += resultado["creados"]
                total_actualizados += resultado["actualizados"]
                total_omitidos += resultado["omitidos"]
                total_errores += len(resultado["errores"])

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"  ❌ Error en empresa {empresa.razon_social}: {e}"
                ))
                total_errores += 1

        # Resumen
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("═══ Resumen ═══"))
        self.stdout.write(f"  Creados:       {total_creados}")
        self.stdout.write(f"  Actualizados:  {total_actualizados}")
        self.stdout.write(f"  Omitidos:      {total_omitidos}")
        self.stdout.write(f"  Errores:       {total_errores}")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "\n💡 Ejecuta sin --dry-run para guardar los cambios."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n🎉 Proceso completado."
            ))