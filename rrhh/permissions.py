"""
Permisos personalizados y mixins para el sistema RRHH.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS


# ═══════════════════════════════════════════════════════════
#  PERMISOS POR ROL
# ═══════════════════════════════════════════════════════════

class EsSuperAdmin(BasePermission):
    """
    Permite acceso solo a super administradores.
    Un superadmin puede ver y gestionar TODAS las empresas.
    """
    message = "Se requiere ser Super Administrador."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if hasattr(request.user, "perfil"):
            return request.user.perfil.rol == "superadmin"

        return False


class EsAdminEmpresa(BasePermission):
    """
    Permite acceso a administradores de empresa (o superior).
    """
    message = "Se requiere ser Administrador de empresa."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if hasattr(request.user, "perfil"):
            return request.user.perfil.rol in ("superadmin", "admin")

        return False


class EsAdmin(BasePermission):
    """
    Permite acceso solo a administradores.
    Alias retrocompatible para `EsAdminEmpresa`.
    """
    message = "Se requiere rol Administrador."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if not hasattr(request.user, "perfil"):
            return False

        return request.user.perfil.rol in ("superadmin", "admin")


class EsRRHH(BasePermission):
    """
    Permite acceso a RRHH, admins y superadmins.
    """
    message = "Se requiere rol RRHH o Administrador."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if not hasattr(request.user, "perfil"):
            return False

        return request.user.perfil.rol in ("superadmin", "admin", "rrhh")


class EsManager(BasePermission):
    """
    Permite acceso a managers, RRHH, admins y superadmins.
    """
    message = "Se requiere rol Manager o superior."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if not hasattr(request.user, "perfil"):
            return False

        return request.user.perfil.rol in (
            "superadmin", "admin", "rrhh", "manager"
        )


# ═══════════════════════════════════════════════════════════
#  PERMISOS COMBINADOS (lectura/escritura)
# ═══════════════════════════════════════════════════════════

class SoloLecturaOEsRRHH(BasePermission):
    """
    Lectura para todos los autenticados.
    Escritura solo para RRHH, admins y superadmins.
    """
    message = "No tienes permiso para modificar este recurso."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Lectura permitida para todos los autenticados
        if request.method in SAFE_METHODS:
            return True

        # Escritura solo para RRHH+
        if request.user.is_superuser:
            return True

        if not hasattr(request.user, "perfil"):
            return False

        return request.user.perfil.rol in ("superadmin", "admin", "rrhh")


class SoloLecturaOEsAdmin(BasePermission):
    """
    Lectura para todos los autenticados.
    Escritura solo para admins y superadmins.
    """
    message = "No tienes permiso para modificar este recurso."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        if request.user.is_superuser:
            return True

        if not hasattr(request.user, "perfil"):
            return False

        return request.user.perfil.rol in ("superadmin", "admin")


class EsPropietarioOEsRRHH(BasePermission):
    """
    Solo el propio usuario o RRHH pueden acceder al objeto.
    """
    message = "No tienes permiso para acceder a este recurso."

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        if not hasattr(request.user, "perfil"):
            return False

        # RRHH+ puede acceder a todo
        if request.user.perfil.rol in ("superadmin", "admin", "rrhh"):
            return True

        # Solo si el objeto es el propio usuario
        return obj == request.user


# ═══════════════════════════════════════════════════════════
#  MIXIN: Filtrar queryset por empresa del usuario
# ═══════════════════════════════════════════════════════════

class FiltrarPorEmpresaMixin:
    """
    Filtra automáticamente el queryset por la empresa del usuario autenticado.

    - Superusuarios y superadmins: ven todas las empresas.
    - Usuarios con empresa asignada: ven solo su empresa.
    - Usuarios sin empresa y sin ser superadmin: queryset vacío.

    Uso:
        class EmpleadoViewSet(FiltrarPorEmpresaMixin, viewsets.ModelViewSet):
            queryset = Empleado.objects.all()
            serializer_class = EmpleadoSerializer
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if not user.is_authenticated:
            return qs.none()

        # Superusuarios ven todo
        if user.is_superuser:
            return qs

        # Verificar perfil
        if hasattr(user, "perfil"):
            # Superadmin o sin empresa → acceso global
            if user.perfil.tiene_acceso_global:
                return qs

            # Usuario con empresa → filtrar por su empresa
            if user.perfil.empresa:
                return qs.filter(empresa=user.perfil.empresa)

        # Sin perfil o sin empresa → vacío
        return qs.none()


# ═══════════════════════════════════════════════════════════
#  PERMISOS PARA NÓMINA
# ═══════════════════════════════════════════════════════════

class PuedeCalcularNomina(BasePermission):
    """
    Permite calcular nómina solo a RRHH, admins y superadmins.
    """
    message = "No tienes permiso para calcular nómina."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if not hasattr(request.user, "perfil"):
            return False

        return request.user.perfil.rol in ("superadmin", "admin", "rrhh")


class PuedeAprobarNomina(BasePermission):
    """
    Permite aprobar/cerrar nómina solo a admins y superadmins.
    """
    message = "No tienes permiso para aprobar nómina."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        if not hasattr(request.user, "perfil"):
            return False

        return request.user.perfil.rol in ("superadmin", "admin")