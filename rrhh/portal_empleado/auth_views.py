"""
Vistas de autenticación del Portal del Empleado.

Endpoints:
    POST /api/v1/empleado/auth/registro/            → Autoregistro
    POST /api/v1/empleado/auth/login/               → Login flexible (cédula, email, Nº empleado, username)
    POST /api/v1/empleado/auth/login-username/      → Login por username (compatibilidad)
    POST /api/v1/empleado/auth/verificar-empleado/  → Verificar si un empleado puede registrarse
    POST /api/v1/empleado/auth/refresh/             → Refrescar access token
    POST /api/v1/empleado/auth/logout/              → Invalidar refresh (blacklist)
    POST /api/v1/empleado/auth/cambiar-password/    → Cambio de contraseña
"""
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

from rrhh.models import Empleado
from .models import CuentaEmpleado
from .permissions import IsCuentaEmpleado
from .serializers import (
    CuentaEmpleadoSerializer,
    LoginFlexibleSerializer,
    LoginUsernameSerializer,
    RegistroSerializer,
    CambioPasswordSerializer,
    VerificarEmpleadoSerializer,
    _normalizar_numero_empleado,
)


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _get_client_ip(request):
    """Devuelve la IP del cliente desde el request."""
    if request is None:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _build_tokens_response(user, cuenta, identificador="", request=None):
    """
    Genera la respuesta con los tokens JWT + datos de la cuenta.

    Args:
        user: instancia de User de Django
        cuenta: instancia de CuentaEmpleado
        identificador: lo que el empleado escribió para loguearse (para guardarlo)
        request: request original (para obtener la IP)
    """
    refresh = RefreshToken.for_user(user)

    # Registrar login con IP y último identificador
    cuenta.registrar_login(
        ip=_get_client_ip(request),
        identificador=identificador,
    )

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "cuenta": CuentaEmpleadoSerializer(cuenta).data,
    }


def _normalizar_cedula(cedula_raw):
    """
    Normaliza una cédula quitando prefijos y separadores.
    Ej: "V-12.345.678" → "12345678"
    """
    if not cedula_raw:
        return ""
    return (
        cedula_raw.strip()
        .replace("V-", "")
        .replace("E-", "")
        .replace("V", "")
        .replace("E", "")
        .replace(".", "")
        .replace("-", "")
        .replace(" ", "")
        .strip()
    )


def _encontrar_usuario_por_identifier(identifier):
    """
    Busca un usuario por cédula, email, número de empleado o username.

    Orden de búsqueda:
        1. Por username directo
        2. Por email
        3. Por cédula
        4. Por número de empleado (normalizado y original)

    Returns:
        User o None
    """
    if not identifier:
        return None

    ident = identifier.strip()
    if not ident:
        return None

    # ─── 1. Por username directo ─────────────────────────
    user = User.objects.filter(username=ident).first()
    if user:
        return user

    # ─── 2. Por email ─────────────────────────────────────
    user = User.objects.filter(email__iexact=ident).first()
    if user:
        return user

    # ─── 3. Por cédula ────────────────────────────────────
    cedula_limpia = _normalizar_cedula(ident)
    if cedula_limpia:
        empleado = Empleado.objects.filter(cedula=cedula_limpia).first()
        if empleado:
            cuenta = getattr(empleado, "cuenta_empleado", None)
            if cuenta:
                return cuenta.usuario

    # ─── 4. Por número de empleado ───────────────────────
    numero_norm = _normalizar_numero_empleado(ident)
    # Probamos con varias variantes por si la normalización no cubre todos los casos
    variantes = set()
    for variante in (numero_norm, ident, ident.upper(), ident.lower()):
        if variante:
            variantes.add(variante)
            # También sin guiones
            variantes.add(variante.replace("-", ""))
            variantes.add(variante.replace(" ", ""))

    for variante in variantes:
        empleado = Empleado.objects.filter(numero_empleado=variante).first()
        if empleado:
            cuenta = getattr(empleado, "cuenta_empleado", None)
            if cuenta:
                return cuenta.usuario

    return None


# ═══════════════════════════════════════════════════════════
#  REGISTRO (AUTOREGISTRO)
# ═══════════════════════════════════════════════════════════

class RegistroView(APIView):
    """
    Autoregistro del empleado.

    Request:
        POST /api/v1/empleado/auth/registro/
        {
            "cedula": "12345678",
            "numero_empleado": "EMP-0001",
            "password": "MiClave123",
            "password_confirm": "MiClave123"
        }

    Response 201:
        {
            "access": "...",
            "refresh": "...",
            "cuenta": {...}
        }
    """
    permission_classes = [AllowAny]
    serializer_class = RegistroSerializer

    @transaction.atomic
    def post(self, request):
        serializer = RegistroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        empleado = serializer.validated_data["empleado"]
        password = serializer.validated_data["password"]
        cedula_limpia = serializer.validated_data["cedula_limpia"]
        numero_normalizado = serializer.validated_data["numero_normalizado"]

        # Generar username único (cédula + número de empleado normalizado)
        username = f"{cedula_limpia}_{numero_normalizado}".lower()
        # Sanitizar (por si el número tiene guiones)
        username = username.replace("-", "_").replace(".", "").replace(" ", "")

        # Verificar colisión de username (raro, pero posible)
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1

        # Crear User de Django
        user = User.objects.create_user(
            username=username,
            email=empleado.email,
            password=password,
            first_name=empleado.nombre,
            last_name=f"{empleado.apellido_paterno} {empleado.apellido_materno}".strip(),
        )

        # Crear CuentaEmpleado (auto-activada, email verificado por decisión de diseño)
        cuenta = CuentaEmpleado.objects.create(
            empleado=empleado,
            usuario=user,
            activo=True,
            email_verificado=True,
            creado_por=None,  # Autoregistro
        )

        # Generar tokens (identificador = cédula, que fue lo que usó)
        data = _build_tokens_response(
            user, cuenta,
            identificador=cedula_limpia,
            request=request,
        )
        return Response(data, status=status.HTTP_201_CREATED)


# ═══════════════════════════════════════════════════════════
#  LOGIN FLEXIBLE (RECOMENDADO)
# ═══════════════════════════════════════════════════════════

class LoginView(APIView):
    """
    Login flexible: acepta cédula, número de empleado, email o username.

    Request:
        POST /api/v1/empleado/auth/login/
        {
            "identifier": "12345678",       // cédula
            "password": "MiClave123"
        }

        // También acepta:
        // "identifier": "EMP-0001"        // número de empleado
        // "identifier": "juan@acme.com"   // email
        // "identifier": "12345678_emp_0001" // username

    Response 200:
        {
            "access": "...",
            "refresh": "...",
            "cuenta": {...}
        }
    """
    permission_classes = [AllowAny]
    serializer_class = LoginFlexibleSerializer

    def post(self, request):
        serializer = LoginFlexibleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        identifier = serializer.validated_data["identifier"].strip()
        password = serializer.validated_data["password"]

        # Buscar el usuario (por cédula, email, Nº empleado o username)
        user = _encontrar_usuario_por_identifier(identifier)
        if user is None:
            return Response(
                {"detail": "Credenciales inválidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Autenticar (verifica la contraseña)
        auth_user = authenticate(
            request,
            username=user.username,
            password=password,
        )
        if auth_user is None:
            return Response(
                {"detail": "Credenciales inválidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Verificar que tenga CuentaEmpleado
        cuenta = getattr(auth_user, "cuenta_empleado", None)
        if not cuenta:
            return Response(
                {"detail": "Este usuario no tiene cuenta de empleado."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not cuenta.activo:
            return Response(
                {"detail": "Tu cuenta está inactiva. Contactá a RRHH."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Generar tokens (guardando el identificador usado)
        data = _build_tokens_response(
            auth_user, cuenta,
            identificador=identifier,
            request=request,
        )
        return Response(data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════
#  LOGIN POR USERNAME (COMPATIBILIDAD)
# ═══════════════════════════════════════════════════════════

class LoginUsernameView(APIView):
    """
    Login tradicional por username.

    Se mantiene para compatibilidad con frontends o apps que ya lo usan.

    Request:
        POST /api/v1/empleado/auth/login-username/
        {
            "username": "12345678_emp_0001",
            "password": "MiClave123"
        }
    """
    permission_classes = [AllowAny]
    serializer_class = LoginUsernameSerializer

    def post(self, request):
        serializer = LoginUsernameSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"].strip()
        password = serializer.validated_data["password"]

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response(
                {"detail": "Credenciales inválidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        cuenta = getattr(user, "cuenta_empleado", None)
        if not cuenta:
            return Response(
                {"detail": "Este usuario no tiene cuenta de empleado."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not cuenta.activo:
            return Response(
                {"detail": "Tu cuenta está inactiva. Contactá a RRHH."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = _build_tokens_response(
            user, cuenta,
            identificador=username,
            request=request,
        )
        return Response(data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════
#  VERIFICAR EMPLEADO (para autoregistro)
# ═══════════════════════════════════════════════════════════

class VerificarEmpleadoView(APIView):
    """
    Verifica si un empleado puede registrarse.

    Útil para que el frontend valide antes de mostrar el formulario.

    Request:
        POST /api/v1/empleado/auth/verificar-empleado/
        {
            "cedula": "12345678",
            "numero_empleado": "EMP-0001"
        }

    Response 200 (puede registrarse):
        {
            "puede_registrarse": true,
            "empleado": {
                "numero_empleado": "EMP-0001",
                "nombre": "Juan Pérez"
            }
        }

    Response 200 (no puede registrarse):
        {
            "puede_registrarse": false,
            "motivo": "Este empleado ya tiene una cuenta creada.",
            "empleado": {...}
        }
    """
    permission_classes = [AllowAny]
    serializer_class = VerificarEmpleadoSerializer

    def post(self, request):
        serializer = VerificarEmpleadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cedula_raw = serializer.validated_data["cedula"].strip()
        numero_raw = serializer.validated_data["numero_empleado"].strip()

        # Normalizar
        cedula_limpia = _normalizar_cedula(cedula_raw)
        numero_norm = _normalizar_numero_empleado(numero_raw)

        # Buscar con variantes
        empleado = None
        variantes = {numero_norm, numero_raw, numero_raw.upper(), numero_raw.lower()}
        variantes = {v for v in variantes if v}
        variantes.add(numero_raw.replace("-", ""))
        variantes.add(numero_raw.replace(" ", ""))

        for numero in variantes:
            empleado = Empleado.objects.filter(
                cedula=cedula_limpia,
                numero_empleado=numero,
                estatus="activo",
            ).first()
            if empleado:
                break

        if not empleado:
            return Response({
                "puede_registrarse": False,
                "motivo": "No encontramos un empleado activo con esos datos.",
            }, status=status.HTTP_200_OK)

        # Verificar si ya tiene cuenta
        if hasattr(empleado, "cuenta_empleado"):
            return Response({
                "puede_registrarse": False,
                "motivo": "Este empleado ya tiene una cuenta creada.",
                "empleado": {
                    "numero_empleado": empleado.numero_empleado,
                    "nombre": empleado.nombre_completo,
                },
            }, status=status.HTTP_200_OK)

        return Response({
            "puede_registrarse": True,
            "empleado": {
                "numero_empleado": empleado.numero_empleado,
                "nombre": empleado.nombre_completo,
            },
        }, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════
#  REFRESH
# ═══════════════════════════════════════════════════════════

class RefreshView(APIView):
    """
    Refresca el access token.

    Request:
        POST /api/v1/empleado/auth/refresh/
        { "refresh": "..." }

    Response 200:
        { "access": "..." }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Falta el refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(refresh_token)
            access = str(refresh.access_token)
            return Response({"access": access}, status=status.HTTP_200_OK)
        except TokenError as e:
            return Response(
                {"detail": f"Token inválido: {e}"},
                status=status.HTTP_401_UNAUTHORIZED,
            )


# ═══════════════════════════════════════════════════════════
#  LOGOUT
# ═══════════════════════════════════════════════════════════

class LogoutView(APIView):
    """
    Invalida el refresh token (lo agrega a la blacklist).

    Request:
        POST /api/v1/empleado/auth/logout/
        { "refresh": "..." }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Falta el refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"detail": "Sesión cerrada correctamente."},
                status=status.HTTP_200_OK,
            )
        except TokenError as e:
            return Response(
                {"detail": f"Token inválido: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


# ═══════════════════════════════════════════════════════════
#  CAMBIO DE CONTRASEÑA
# ═══════════════════════════════════════════════════════════

class CambioPasswordView(APIView):
    """
    Cambio de contraseña del empleado logueado.

    Request:
        POST /api/v1/empleado/auth/cambiar-password/
        {
            "password_actual": "...",
            "password_nuevo": "...",
            "password_confirm": "..."
        }
    """
    permission_classes = [IsAuthenticated, IsCuentaEmpleado]
    serializer_class = CambioPasswordSerializer

    @transaction.atomic
    def post(self, request):
        serializer = CambioPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        # Verificar contraseña actual
        if not user.check_password(serializer.validated_data["password_actual"]):
            return Response(
                {"password_actual": ["La contraseña actual es incorrecta."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Cambiar contraseña
        user.set_password(serializer.validated_data["password_nuevo"])
        user.save(update_fields=["password"])

        # Invalidar todos los refresh tokens previos (forzar re-login)
        try:
            for token in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=token)
        except Exception:
            # Si falla el blacklist, no rompemos el flujo
            pass

        return Response(
            {"detail": "Contraseña actualizada. Volvé a iniciar sesión en todos tus dispositivos."},
            status=status.HTTP_200_OK,
        )