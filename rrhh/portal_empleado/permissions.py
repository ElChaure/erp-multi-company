"""
Permisos personalizados para el Portal del Empleado.
"""
from rest_framework import permissions


class IsCuentaEmpleado(permissions.BasePermission):
    """
    Permite el acceso solo a usuarios autenticados que tengan
    una CuentaEmpleado activa.

    Usar en todos los endpoints del portal del empleado.
    """
    message = "Debes estar autenticado como empleado para acceder a este recurso."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Verificar que tenga cuenta_empleado
        cuenta = getattr(request.user, "cuenta_empleado", None)
        if not cuenta:
            return False

        # Verificar que esté activa
        if not cuenta.activo:
            return False

        return True