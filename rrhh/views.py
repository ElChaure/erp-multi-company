from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q

from .models import (
    Empleado,
    Departamento,
    Cargo,
    Empresa,
    Sede,
    Perfil,
)
from .forms import (
    EmpleadoForm,
    EmpresaForm,
    SedeForm,
    CargoForm,
    DepartamentoForm,
    PerfilForm,
)
from .decorators import solo_admin, solo_rrhh, solo_manager, empleado_autenticado


# ═══════════════════════════════════════════════════════════
#  AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════

def login_view(request):
    """Vista de login."""
    if request.user.is_authenticated:
        return redirect("rrhh:dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(
                    request,
                    f"Bienvenido, {user.get_full_name() or user.username}.",
                )
                next_url = request.GET.get("next") or "rrhh:dashboard"
                return redirect(next_url)
            else:
                messages.error(request, "Tu cuenta está desactivada.")
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, "rrhh/auth/login.html")


def logout_view(request):
    """Cerrar sesión."""
    logout(request)
    messages.info(request, "Has cerrado sesión correctamente.")
    return redirect("rrhh:login")


@login_required
def perfil_view(request):
    """Ver y editar el perfil del usuario autenticado."""
    perfil = request.user.perfil

    if request.method == "POST":
        perfil.telefono = request.POST.get("telefono", "").strip()
        perfil.cargo = request.POST.get("cargo", "").strip()
        perfil.save()
        messages.success(request, "Perfil actualizado.")
        return redirect("rrhh:perfil")

    return render(request, "rrhh/auth/perfil.html", {"perfil": perfil})


def acceso_denegado(request):
    """Página que se muestra cuando no tiene permisos."""
    return render(request, "rrhh/auth/acceso_denegado.html", status=403)


# ═══════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def dashboard(request):
    """Dashboard adaptado al rol del usuario."""
    user = request.user

    # Filtrar por empresa si el usuario no es global
    if user.is_superuser or user.perfil.tiene_acceso_global:
        qs_empleados = Empleado.objects.all()
        qs_empresas = Empresa.objects.filter(activa=True)
        qs_sedes = Sede.objects.filter(activa=True)
    else:
        empresa_id = user.perfil.empresa_id
        qs_empleados = Empleado.objects.filter(empresa_id=empresa_id)
        qs_empresas = Empresa.objects.filter(id=empresa_id)
        qs_sedes = Sede.objects.filter(empresa_id=empresa_id, activa=True)

    context = {
        "total_empleados": qs_empleados.count(),
        "empleados_activos": qs_empleados.filter(estatus="activo").count(),
        "total_departamentos": Departamento.objects.filter(activo=True).count(),
        "total_cargos": Cargo.objects.filter(activo=True).count(),
        "total_empresas": qs_empresas.count(),
        "total_sedes": qs_sedes.count(),
    }

    if not user.perfil.es_rrhh:
        context["es_vista_restringida"] = True

    return render(request, "rrhh/dashboard.html", context)


# ═══════════════════════════════════════════════════════════
#  EMPRESA
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def empresa_lista(request):
    """Listado de empresas (solo la del usuario o todas si es superadmin)."""
    query = request.GET.get("q", "")
    tipo = request.GET.get("tipo", "")

    if request.user.is_superuser or request.user.perfil.tiene_acceso_global:
        empresas = Empresa.objects.all()
    else:
        empresas = Empresa.objects.filter(id=request.user.perfil.empresa_id)

    if query:
        empresas = empresas.filter(
            Q(rif__icontains=query)
            | Q(razon_social__icontains=query)
            | Q(nombre_comercial__icontains=query)
        )

    if tipo:
        empresas = empresas.filter(tipo=tipo)

    context = {
        "empresas": empresas.order_by("razon_social"),
        "query": query,
        "tipo": tipo,
        "tipo_choices": Empresa.TIPO_CHOICES,
    }
    return render(request, "rrhh/empresa_lista.html", context)


@solo_admin
def empresa_crear(request):
    """Crear empresa (solo admin global)."""
    if request.method == "POST":
        form = EmpresaForm(request.POST, request.FILES)
        if form.is_valid():
            empresa = form.save()
            messages.success(
                request, f"Empresa {empresa.razon_social} creada exitosamente."
            )
            return redirect("rrhh:empresa_lista")
        else:
            messages.error(request, "Corrige los errores del formulario.")
    else:
        form = EmpresaForm()

    return render(
        request,
        "rrhh/empresa_form.html",
        {"form": form, "accion": "Crear"},
    )


@empleado_autenticado
def empresa_detalle(request, pk):
    """Ver detalle de una empresa."""
    empresa = get_object_or_404(Empresa, pk=pk)

    # Permiso: solo la propia o superadmin
    if not (request.user.is_superuser or request.user.perfil.tiene_acceso_global):
        if empresa.id != request.user.perfil.empresa_id:
            messages.error(request, "No tienes acceso a esta empresa.")
            return redirect("rrhh:dashboard")

    sedes = empresa.sedes.all().order_by("nombre")
    empleados = empresa.empleados.filter(estatus="activo")[:10]

    context = {
        "empresa": empresa,
        "sedes": sedes,
        "empleados_recientes": empleados,
    }
    return render(request, "rrhh/empresa_detalle.html", context)


@solo_admin
def empresa_editar(request, pk):
    """Editar empresa."""
    empresa = get_object_or_404(Empresa, pk=pk)

    if request.method == "POST":
        form = EmpresaForm(request.POST, request.FILES, instance=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, "Empresa actualizada.")
            return redirect("rrhh:empresa_detalle", pk=empresa.pk)
    else:
        form = EmpresaForm(instance=empresa)

    return render(
        request,
        "rrhh/empresa_form.html",
        {"form": form, "accion": "Editar", "empresa": empresa},
    )


@solo_admin
def empresa_eliminar(request, pk):
    """Eliminar empresa (con confirmación)."""
    empresa = get_object_or_404(Empresa, pk=pk)

    # Verificar si tiene dependencias
    sedes_count = empresa.sedes.count()
    empleados_count = empresa.empleados.count()

    if request.method == "POST":
        # Bloquear si tiene empleados o sedes activas
        if empleados_count > 0:
            messages.error(
                request,
                f"No se puede eliminar: tiene {empleados_count} empleado(s) asociado(s).",
            )
            return redirect("rrhh:empresa_detalle", pk=empresa.pk)

        nombre = empresa.razon_social
        empresa.delete()
        messages.success(request, f"Empresa {nombre} eliminada.")
        return redirect("rrhh:empresa_lista")

    return render(
        request,
        "rrhh/empresa_confirmar_eliminar.html",
        {
            "empresa": empresa,
            "sedes_count": sedes_count,
            "empleados_count": empleados_count,
        },
    )


# ═══════════════════════════════════════════════════════════
#  SEDE
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def sede_lista(request):
    """Listado de sedes."""
    query = request.GET.get("q", "")
    empresa_id = request.GET.get("empresa", "")

    if request.user.is_superuser or request.user.perfil.tiene_acceso_global:
        sedes = Sede.objects.all()
        empresas = Empresa.objects.filter(activa=True)
    else:
        empresa_id_user = request.user.perfil.empresa_id
        sedes = Sede.objects.filter(empresa_id=empresa_id_user)
        empresas = Empresa.objects.filter(id=empresa_id_user)

    if query:
        sedes = sedes.filter(
            Q(codigo__icontains=query)
            | Q(nombre__icontains=query)
            | Q(ciudad__icontains=query)
        )

    if empresa_id:
        sedes = sedes.filter(empresa_id=empresa_id)

    context = {
        "sedes": sedes.select_related("empresa").order_by("empresa__razon_social", "nombre"),
        "empresas": empresas,
        "query": query,
        "empresa_id": empresa_id,
    }
    return render(request, "rrhh/sede_lista.html", context)


@solo_rrhh
def sede_crear(request):
    """Crear sede."""
    if request.method == "POST":
        form = SedeForm(request.POST)
        if form.is_valid():
            sede = form.save()
            messages.success(request, f"Sede {sede.nombre} creada.")
            return redirect("rrhh:sede_lista")
        else:
            messages.error(request, "Corrige los errores del formulario.")
    else:
        form = SedeForm()

        # Pre-seleccionar empresa si viene por query param
        empresa_id = request.GET.get("empresa")
        if empresa_id:
            form.fields["empresa"].initial = empresa_id

    return render(
        request,
        "rrhh/sede_form.html",
        {"form": form, "accion": "Crear"},
    )


@empleado_autenticado
def sede_detalle(request, pk):
    """Ver detalle de una sede."""
    sede = get_object_or_404(Sede, pk=pk)

    if not (request.user.is_superuser or request.user.perfil.tiene_acceso_global):
        if sede.empresa_id != request.user.perfil.empresa_id:
            messages.error(request, "No tienes acceso a esta sede.")
            return redirect("rrhh:dashboard")

    empleados = sede.empleados.filter(estatus="activo").order_by("nombre")

    context = {
        "sede": sede,
        "empleados": empleados,
    }
    return render(request, "rrhh/sede_detalle.html", context)


@solo_rrhh
def sede_editar(request, pk):
    """Editar sede."""
    sede = get_object_or_404(Sede, pk=pk)

    if request.method == "POST":
        form = SedeForm(request.POST, instance=sede)
        if form.is_valid():
            form.save()
            messages.success(request, "Sede actualizada.")
            return redirect("rrhh:sede_detalle", pk=sede.pk)
    else:
        form = SedeForm(instance=sede)

    return render(
        request,
        "rrhh/sede_form.html",
        {"form": form, "accion": "Editar", "sede": sede},
    )


@solo_admin
def sede_eliminar(request, pk):
    """Eliminar sede (con confirmación)."""
    sede = get_object_or_404(Sede, pk=pk)

    empleados_count = sede.empleados.count()

    if request.method == "POST":
        if empleados_count > 0:
            messages.error(
                request,
                f"No se puede eliminar: tiene {empleados_count} empleado(s) asignado(s).",
            )
            return redirect("rrhh:sede_detalle", pk=sede.pk)

        nombre = sede.nombre
        sede.delete()
        messages.success(request, f"Sede {nombre} eliminada.")
        return redirect("rrhh:sede_lista")

    return render(
        request,
        "rrhh/sede_confirmar_eliminar.html",
        {"sede": sede, "empleados_count": empleados_count},
    )


# ═══════════════════════════════════════════════════════════
#  EMPLEADOS
# ═══════════════════════════════════════════════════════════

@solo_manager
def empleado_lista(request):
    """Lista de empleados."""
    query = request.GET.get("q", "")
    estatus = request.GET.get("estatus", "")
    empresa_id = request.GET.get("empresa", "")

    # Filtro por empresa según permisos
    if request.user.is_superuser or request.user.perfil.tiene_acceso_global:
        empleados = Empleado.objects.all()
        empresas = Empresa.objects.filter(activa=True)
    else:
        empresa_id_user = request.user.perfil.empresa_id
        empleados = Empleado.objects.filter(empresa_id=empresa_id_user)
        empresas = Empresa.objects.filter(id=empresa_id_user)

    if query:
        empleados = empleados.filter(
            Q(numero_empleado__icontains=query)
            | Q(nombre__icontains=query)
            | Q(apellido_paterno__icontains=query)
            | Q(cedula__icontains=query)
            | Q(email__icontains=query)
        )

    if estatus:
        empleados = empleados.filter(estatus=estatus)

    if empresa_id:
        empleados = empleados.filter(empresa_id=empresa_id)

    context = {
        "empleados": empleados.select_related(
            "empresa", "sede", "cargo", "departamento"
        ),
        "empresas": empresas,
        "query": query,
        "estatus": estatus,
        "empresa_id": empresa_id,
        "estatus_choices": Empleado.ESTATUS_CHOICES,
    }
    return render(request, "rrhh/empleado_lista.html", context)


@solo_rrhh
def empleado_crear(request):
    if request.method == "POST":
        form = EmpleadoForm(request.POST)
        if form.is_valid():
            empleado = form.save(commit=False)
            empleado.created_by = request.user
            empleado.updated_by = request.user
            empleado.save()
            messages.success(
                request, f"Empleado {empleado.nombre_completo} creado."
            )
            return redirect("rrhh:empleado_lista")
        else:
            messages.error(request, "Corrige los errores del formulario.")
    else:
        form = EmpleadoForm()

    return render(
        request,
        "rrhh/empleado_form.html",
        {"form": form, "accion": "Crear"},
    )


@empleado_autenticado
def empleado_detalle(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)

    # Permiso: misma empresa o superadmin
    if not (request.user.is_superuser or request.user.perfil.tiene_acceso_global):
        if empleado.empresa_id != request.user.perfil.empresa_id:
            messages.error(request, "No tienes acceso a este empleado.")
            return redirect("rrhh:empleado_lista")

    return render(request, "rrhh/empleado_detalle.html", {"empleado": empleado})


@solo_rrhh
def empleado_editar(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)

    if request.method == "POST":
        form = EmpleadoForm(request.POST, instance=empleado)
        if form.is_valid():
            emp = form.save(commit=False)
            emp.updated_by = request.user
            emp.save()
            messages.success(request, "Empleado actualizado.")
            return redirect("rrhh:empleado_detalle", pk=empleado.pk)
    else:
        form = EmpleadoForm(instance=empleado)

    return render(
        request,
        "rrhh/empleado_form.html",
        {"form": form, "accion": "Editar", "empleado": empleado},
    )


@solo_admin
def empleado_eliminar(request, pk):
    empleado = get_object_or_404(Empleado, pk=pk)

    if request.method == "POST":
        nombre = empleado.nombre_completo
        empleado.delete()
        messages.success(request, f"Empleado {nombre} eliminado.")
        return redirect("rrhh:empleado_lista")

    return render(
        request,
        "rrhh/empleado_confirmar_eliminar.html",
        {"empleado": empleado},
    )


# ═══════════════════════════════════════════════════════════
#  CARGO
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def cargo_lista(request):
    query = request.GET.get("q", "")
    activo = request.GET.get("activo", "")

    cargos = Cargo.objects.all()

    if query:
        cargos = cargos.filter(
            Q(codigo__icontains=query) | Q(nombre__icontains=query)
        )

    if activo == "1":
        cargos = cargos.filter(activo=True)
    elif activo == "0":
        cargos = cargos.filter(activo=False)

    context = {
        "cargos": cargos,
        "query": query,
        "activo": activo,
    }
    return render(request, "rrhh/cargo_lista.html", context)


@solo_rrhh
def cargo_crear(request):
    if request.method == "POST":
        form = CargoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Cargo creado.")
            return redirect("rrhh:cargo_lista")
    else:
        form = CargoForm()
    return render(request, "rrhh/cargo_form.html", {"form": form, "accion": "Crear"})


@solo_rrhh
def cargo_editar(request, pk):
    cargo = get_object_or_404(Cargo, pk=pk)
    if request.method == "POST":
        form = CargoForm(request.POST, instance=cargo)
        if form.is_valid():
            form.save()
            messages.success(request, "Cargo actualizado.")
            return redirect("rrhh:cargo_lista")
    else:
        form = CargoForm(instance=cargo)
    return render(
        request,
        "rrhh/cargo_form.html",
        {"form": form, "accion": "Editar", "cargo": cargo},
    )


# ═══════════════════════════════════════════════════════════
#  DEPARTAMENTO
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def departamento_lista(request):
    query = request.GET.get("q", "")
    empresa_id = request.GET.get("empresa", "")

    if request.user.is_superuser or request.user.perfil.tiene_acceso_global:
        departamentos = Departamento.objects.all()
        empresas = Empresa.objects.filter(activa=True)
    else:
        empresa_id_user = request.user.perfil.empresa_id
        departamentos = Departamento.objects.filter(empresa_id=empresa_id_user)
        empresas = Empresa.objects.filter(id=empresa_id_user)

    if query:
        departamentos = departamentos.filter(
            Q(codigo__icontains=query) | Q(nombre__icontains=query)
        )

    if empresa_id:
        departamentos = departamentos.filter(empresa_id=empresa_id)

    context = {
        "departamentos": departamentos.select_related("empresa", "padre"),
        "empresas": empresas,
        "query": query,
        "empresa_id": empresa_id,
    }
    return render(request, "rrhh/departamento_lista.html", context)


@solo_rrhh
def departamento_crear(request):
    if request.method == "POST":
        form = DepartamentoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Departamento creado.")
            return redirect("rrhh:departamento_lista")
    else:
        form = DepartamentoForm()
    return render(
        request,
        "rrhh/departamento_form.html",
        {"form": form, "accion": "Crear"},
    )


@solo_rrhh
def departamento_editar(request, pk):
    departamento = get_object_or_404(Departamento, pk=pk)
    if request.method == "POST":
        form = DepartamentoForm(request.POST, instance=departamento)
        if form.is_valid():
            form.save()
            messages.success(request, "Departamento actualizado.")
            return redirect("rrhh:departamento_lista")
    else:
        form = DepartamentoForm(instance=departamento)
    return render(
        request,
        "rrhh/departamento_form.html",
        {"form": form, "accion": "Editar", "departamento": departamento},
    )

# ═══════════════════════════════════════════════════════════
#  CARGO — Eliminar
# ═══════════════════════════════════════════════════════════

@solo_admin
def cargo_eliminar(request, pk):
    """Eliminar cargo (solo admin)."""
    cargo = get_object_or_404(Cargo, pk=pk)

    # Verificar si tiene empleados asignados
    empleados_count = cargo.empleados.count()

    if request.method == "POST":
        if empleados_count > 0:
            messages.error(
                request,
                f"No se puede eliminar: tiene {empleados_count} empleado(s) asignado(s).",
            )
            return redirect("rrhh:cargo_lista")

        nombre = cargo.nombre
        cargo.delete()
        messages.success(request, f"Cargo {nombre} eliminado.")
        return redirect("rrhh:cargo_lista")

    return render(
        request,
        "rrhh/cargo_confirmar_eliminar.html",
        {"cargo": cargo, "empleados_count": empleados_count},
    )


# ═══════════════════════════════════════════════════════════
#  DEPARTAMENTO — Eliminar
# ═══════════════════════════════════════════════════════════

@solo_admin
def departamento_eliminar(request, pk):
    """Eliminar departamento (solo admin)."""
    departamento = get_object_or_404(Departamento, pk=pk)

    # Verificar si tiene empleados o subdepartamentos
    empleados_count = departamento.empleados.count()
    subdepartamentos_count = departamento.subdepartamentos.count()

    if request.method == "POST":
        if empleados_count > 0:
            messages.error(
                request,
                f"No se puede eliminar: tiene {empleados_count} empleado(s) asignado(s).",
            )
            return redirect("rrhh:departamento_lista")

        if subdepartamentos_count > 0:
            messages.error(
                request,
                f"No se puede eliminar: tiene {subdepartamentos_count} subdepartamento(s).",
            )
            return redirect("rrhh:departamento_lista")

        nombre = departamento.nombre
        departamento.delete()
        messages.success(request, f"Departamento {nombre} eliminado.")
        return redirect("rrhh:departamento_lista")

    return render(
        request,
        "rrhh/departamento_confirmar_eliminar.html",
        {
            "departamento": departamento,
            "empleados_count": empleados_count,
            "subdepartamentos_count": subdepartamentos_count,
        },
    )

@empleado_autenticado
def cargo_detalle(request, pk):
    """Ver detalle de un cargo."""
    cargo = get_object_or_404(Cargo, pk=pk)

    # Empleados con este cargo
    empleados = Empleado.objects.filter(cargo=cargo).select_related(
        "empresa", "sede", "departamento"
    ).order_by("-fecha_ingreso")

    # Calcular estadísticas
    empleados_activos_count = empleados.filter(estatus="activo").count()

    # Calcular rango salarial
    rango_salarial = None
    rango_salarial_pct = None
    if cargo.salario_min and cargo.salario_max:
        rango_salarial = cargo.salario_max - cargo.salario_min
        if cargo.salario_min > 0:
            rango_salarial_pct = (rango_salarial / cargo.salario_min) * 100

    context = {
        "cargo": cargo,
        "empleados": empleados,
        "empleados_activos_count": empleados_activos_count,
        "rango_salarial": rango_salarial,
        "rango_salarial_pct": rango_salarial_pct,
    }
    return render(request, "rrhh/cargo_detalle.html", context)

@empleado_autenticado
def departamento_detalle(request, pk):
    """Ver detalle de un departamento."""
    departamento = get_object_or_404(
        Departamento.objects.select_related("empresa", "padre", "responsable"),
        pk=pk,
    )

    # Permiso: misma empresa o superadmin
    if not (request.user.is_superuser or request.user.perfil.tiene_acceso_global):
        if departamento.empresa_id != request.user.perfil.empresa_id:
            messages.error(request, "No tienes acceso a este departamento.")
            return redirect("rrhh:departamento_lista")

    # Empleados del departamento
    empleados = Empleado.objects.filter(departamento=departamento).select_related(
        "empresa", "sede", "cargo"
    ).order_by("-fecha_ingreso")

    # Subdepartamentos
    subdepartamentos = departamento.subdepartamentos.select_related("responsable").order_by("nombre")

    # Estadísticas
    empleados_activos_count = empleados.filter(estatus="activo").count()
    costo_nomina = sum(
        emp.salario_base for emp in empleados if emp.estatus == "activo"
    )

    # Porcentaje del presupuesto consumido (si hay presupuesto)
    porcentaje_presupuesto = None
    if departamento.presupuesto_anual and departamento.presupuesto_anual > 0:
        costo_anual = costo_nomina * 12
        porcentaje_presupuesto = (costo_anual / departamento.presupuesto_anual) * 100

    context = {
        "departamento": departamento,
        "empleados": empleados,
        "subdepartamentos": subdepartamentos,
        "empleados_activos_count": empleados_activos_count,
        "costo_nomina": costo_nomina,
        "porcentaje_presupuesto": porcentaje_presupuesto,
    }
    return render(request, "rrhh/departamento_detalle.html", context)


# ═══════════════════════════════════════════════════════════
#  API JSON (endpoints simples)
# ═══════════════════════════════════════════════════════════

@solo_rrhh
def api_empleados(request):
    empleados = Empleado.objects.all()[:20]
    data = [
        {
            "id": e.id,
            "numero_empleado": e.numero_empleado,
            "nombre_completo": e.nombre_completo,
            "cedula": e.cedula_completa,
            "email": e.email,
            "estatus": e.estatus,
        }
        for e in empleados
    ]
    return JsonResponse({"empleados": data, "total": Empleado.objects.count()})


@solo_rrhh
def api_sedes_por_empresa(request, empresa_id):
    """Endpoint AJAX para filtrar sedes por empresa."""
    sedes = Sede.objects.filter(empresa_id=empresa_id, activa=True).values(
        "id", "codigo", "nombre", "es_principal"
    )
    return JsonResponse({"sedes": list(sedes)})


@solo_rrhh
def api_departamentos_por_empresa(request, empresa_id):
    """Endpoint AJAX para filtrar departamentos por empresa."""
    departamentos = Departamento.objects.filter(
        empresa_id=empresa_id, activo=True
    ).values("id", "codigo", "nombre")
    return JsonResponse({"departamentos": list(departamentos)})
    
# ═══════════════════════════════════════════════════════════
#  PORTAL DEL EMPLEADO
# ═══════════════════════════════════════════════════════════

@empleado_autenticado
def mi_portal(request):
    """
    Portal del empleado: recibos de pago, saldo de vacaciones y datos personales.

    Para empleados sin registro vinculado (admin, rrhh puros) muestra un
    mensaje indicando que no tienen ficha de empleado.
    """
    user = request.user
    perfil = getattr(user, "perfil", None)
    empleado = getattr(perfil, "empleado", None) if perfil else None

    context = {
        "empleado": empleado,
        "tiene_ficha": empleado is not None,
    }
    return render(request, "rrhh/mi_portal/index.html", context)    