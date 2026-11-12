from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def rol_requerido(*roles):
    """Verifica que el usuario tenga uno de los roles especificados."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not hasattr(request.user, "perfil"):
                messages.error(request, "No tienes un perfil asignado.")
                return redirect("rrhh:acceso_denegado")

            perfil = request.user.perfil

            # Superusuarios y superadmins siempre pasan
            if request.user.is_superuser or perfil.rol == "superadmin":
                return view_func(request, *args, **kwargs)

            if perfil.rol not in roles:
                messages.error(
                    request,
                    f"Acceso denegado. Se requiere rol: {', '.join(roles)}.",
                )
                return redirect("rrhh:acceso_denegado")

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def solo_admin(view_func):
    return rol_requerido("admin")(view_func)


def solo_rrhh(view_func):
    return rol_requerido("admin", "rrhh")(view_func)


def solo_manager(view_func):
    return rol_requerido("admin", "rrhh", "manager")(view_func)


def empleado_autenticado(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper