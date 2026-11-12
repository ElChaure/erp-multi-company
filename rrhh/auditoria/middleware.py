"""
Middleware para capturar el contexto del usuario en cada request.

Guarda el usuario actual, IP y user-agent en un thread-local,
que los signals usan para llenar la auditoría.
"""
import threading


# Thread-local para guardar el contexto
_local = threading.local()


def get_current_user():
    """Devuelve el usuario actual (o None)."""
    return getattr(_local, "usuario", None)


def get_current_ip():
    """Devuelve la IP actual (o None)."""
    return getattr(_local, "ip", None)


def get_current_user_agent():
    """Devuelve el user-agent actual (o '')"""
    return getattr(_local, "user_agent", "")


def get_current_url():
    """Devuelve la URL actual (o '')."""
    return getattr(_local, "url", "")


def get_current_method():
    """Devuelve el método HTTP actual (o '')."""
    return getattr(_local, "metodo_http", "")


class AuditoriaContextMiddleware:
    """
    Middleware que captura el contexto del request y lo guarda en thread-local.

    El thread-local se limpia al finalizar el request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Capturar contexto
        _local.usuario = getattr(request, "user", None) if hasattr(request, "user") else None
        _local.ip = self._get_client_ip(request)
        _local.user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
        _local.url = request.path[:500]
        _local.metodo_http = request.method

        # Si el usuario no está autenticado, dejarlo en None
        if _local.usuario and not _local.usuario.is_authenticated:
            _local.usuario = None

        try:
            response = self.get_response(request)
        finally:
            # Limpiar el contexto
            _local.usuario = None
            _local.ip = None
            _local.user_agent = ""
            _local.url = ""
            _local.metodo_http = ""

        return response

    def _get_client_ip(self, request):
        """Obtiene la IP real del cliente, considerando proxies."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip