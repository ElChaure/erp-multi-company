"""
Vistas API del Dashboard Ejecutivo.
"""
from django.http import HttpResponse
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from rrhh.permissions import EsRRHH, EsManager
from rrhh.models import Empresa

from . import services


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _empresa_id_desde_request(request):
    """
    Devuelve el empresa_id a filtrar según el usuario y query params.
    """
    user = request.user

    if not hasattr(user, "perfil"):
        return None

    perfil = user.perfil

    if perfil.es_superadmin or user.is_superuser:
        empresa_param = request.query_params.get("empresa")
        if empresa_param:
            try:
                return int(empresa_param)
            except (ValueError, TypeError):
                return None
        return None

    if perfil.empresa_id:
        return perfil.empresa_id

    return None


def _meses_desde_request(request, default=12):
    """
    Lee el parámetro ?meses=N, validando rango [1, 36].
    """
    try:
        meses = int(request.query_params.get("meses", default))
    except (ValueError, TypeError):
        return default
    return max(1, min(meses, 36))


def _empresa_para_pdf(request, empresa_id):
    """
    Devuelve la instancia de Empresa para el PDF.
    - Si empresa_id viene explícito, la busca.
    - Si no, usa la empresa del usuario.
    """
    if empresa_id:
        return Empresa.objects.filter(id=empresa_id).first()

    if hasattr(request.user, "perfil") and request.user.perfil.empresa:
        return request.user.perfil.empresa

    return None


# ═══════════════════════════════════════════════════════════
#  ENDPOINT PRINCIPAL
# ═══════════════════════════════════════════════════════════

class DashboardResumenView(APIView):
    """
    Devuelve todos los KPIs del dashboard ejecutivo.

    Params opcionales:
    - empresa (int): solo superadmin puede filtrar por empresa.
    - meses (int): meses para la evolución de nómina (default 12, rango 1-36).
    """
    permission_classes = [IsAuthenticated, EsManager]

    @extend_schema(
        summary="Dashboard ejecutivo — resumen completo",
        description="Devuelve headcount, nómina, ausencias, alertas, "
                    "actividad reciente y próximos eventos en un solo payload.",
        parameters=[
            OpenApiParameter(
                name="empresa",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="ID de empresa (solo superadmin).",
            ),
            OpenApiParameter(
                name="meses",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Meses para la evolución de nómina (1-36, default 12).",
            ),
        ],
        tags=["Dashboard"],
    )
    def get(self, request):
        empresa_id = _empresa_id_desde_request(request)
        meses = _meses_desde_request(request, default=12)
        data = services.dashboard_completo(empresa_id=empresa_id, meses=meses)
        return Response(data, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════
#  ENDPOINT DE EXPORTACIÓN PDF
# ═══════════════════════════════════════════════════════════

class DashboardExportPDFView(APIView):
    """
    Genera un PDF ejecutivo con los KPIs y tablas del dashboard.

    Params opcionales:
    - empresa (int): solo superadmin.
    - meses (int): meses para evolución (aunque no la incluimos, queda para futuro).
    """
    permission_classes = [IsAuthenticated, EsRRHH]

    @extend_schema(
        summary="Exportar dashboard a PDF",
        description="Genera un PDF ejecutivo con KPIs y tablas del dashboard.",
        parameters=[
            OpenApiParameter(
                name="empresa",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                required=False,
                description="ID de empresa (solo superadmin).",
            ),
        ],
        tags=["Dashboard"],
    )
    def get(self, request):
        from rrhh.reportes.exportadores.pdf import generar_pdf

        empresa_id = _empresa_id_desde_request(request)
        empresa = _empresa_para_pdf(request, empresa_id)

        # Obtener datos
        data = services.dashboard_completo(empresa_id=empresa_id, meses=12)

        # ─── Construir filas para el PDF ────────────────────
        # El PDF será de dos columnas: Concepto | Valor

        hc = data["headcount"]
        np_data = data["nomina"]["ultimo_periodo"]
        aus = data["ausencias"]["resumen"]
        alertas = data["alertas"]["items"]

        filas = []

        # Sección: Headcount
        filas.append({"seccion": "─── HEADCOUNT ───", "valor": ""})
        filas.append({"seccion": "Total empleados", "valor": str(hc["total"])})
        filas.append({"seccion": "Empleados activos", "valor": str(hc["activos"])})
        filas.append({"seccion": "En licencia", "valor": str(hc["licencias"])})
        filas.append({"seccion": "De vacaciones", "valor": str(hc["vacaciones"])})
        filas.append({"seccion": "Nuevos este mes", "valor": f"+{hc['nuevos_mes']}"})
        filas.append({"seccion": "Bajas este mes", "valor": f"-{hc['bajas_mes']}"})
        filas.append({"seccion": "Rotación mensual", "valor": f"{hc['rotacion_pct']}%"})

        # Sección: Nómina (último periodo)
        filas.append({"seccion": "", "valor": ""})
        filas.append({"seccion": "─── ÚLTIMO PERIODO DE NÓMINA ───", "valor": ""})
        if np_data.get("periodo"):
            p = np_data["periodo"]
            filas.append({
                "seccion": "Periodo",
                "valor": f"{p['tipo_display']} #{p['numero_periodo']} ({p['fecha_inicio']} → {p['fecha_fin']})",
            })
            filas.append({"seccion": "Estatus", "valor": p["estatus_display"]})
            filas.append({
                "seccion": "Total percepciones",
                "valor": f"Bs. {np_data['total_percepciones']:,.2f}",
            })
            filas.append({
                "seccion": "Total deducciones",
                "valor": f"Bs. {np_data['total_deducciones']:,.2f}",
            })
            filas.append({
                "seccion": "Neto pagado",
                "valor": f"Bs. {np_data['total_neto']:,.2f}",
            })
            filas.append({
                "seccion": "Aportes patronales",
                "valor": f"Bs. {np_data['total_aportes_patronales']:,.2f}",
            })
            filas.append({
                "seccion": "Costo total empresa",
                "valor": f"Bs. {np_data['total_costo_empresa']:,.2f}",
            })
            filas.append({
                "seccion": "Empleados procesados",
                "valor": str(np_data["empleados_procesados"]),
            })
        else:
            filas.append({"seccion": "Sin periodos de nómina registrados", "valor": "—"})

        # Sección: Ausencias
        filas.append({"seccion": "", "valor": ""})
        filas.append({"seccion": "─── AUSENCIAS ───", "valor": ""})
        filas.append({"seccion": "Solicitudes pendientes", "valor": str(aus["pendientes"])})
        filas.append({"seccion": "Solicitudes aprobadas", "valor": str(aus["aprobadas"])})
        filas.append({"seccion": "Empleados ausentes hoy", "valor": str(aus["en_disfrute_hoy"])})

        # Sección: Alertas
        filas.append({"seccion": "", "valor": ""})
        filas.append({"seccion": "─── ALERTAS OPERATIVAS ───", "valor": ""})
        if alertas:
            for a in alertas:
                filas.append({
                    "seccion": f"• {a['titulo']}",
                    "valor": str(a["total"]),
                })
        else:
            filas.append({"seccion": "Sin alertas pendientes", "valor": "✓"})

        # ─── Columnas del PDF ───────────────────────────────
        columnas = [
            {"key": "seccion", "label": "Concepto", "width": 400, "align": "left"},
            {"key": "valor", "label": "Valor", "width": 200, "align": "right"},
        ]

        # ─── Metadata ───────────────────────────────────────
        usuario = request.user
        metadata = {
            "Generado por": usuario.get_full_name() or usuario.username,
            "Fecha": timezone.now().strftime("%d/%m/%Y %H:%M"),
        }

        if not empresa:
            metadata["Alcance"] = "Todas las empresas"

        # ─── Generar PDF ────────────────────────────────────
        try:
            pdf_bytes = generar_pdf(
                titulo="Dashboard Ejecutivo de RRHH",
                subtitulo=empresa.razon_social if empresa else "",
                columnas=columnas,
                datos=filas,
                empresa=empresa,
                metadata=metadata,
                orientacion="portrait",
            )
        except RuntimeError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ─── Respuesta ──────────────────────────────────────
        filename = f"dashboard_rrhh_{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response


# ═══════════════════════════════════════════════════════════
#  ENDPOINTS POR SECCIÓN
# ═══════════════════════════════════════════════════════════

class DashboardHeadcountView(APIView):
    permission_classes = [IsAuthenticated, EsManager]

    @extend_schema(tags=["Dashboard"])
    def get(self, request):
        empresa_id = _empresa_id_desde_request(request)
        return Response({
            "kpis": services.kpis_headcount(empresa_id),
            "por_departamento": services.kpis_headcount_por_departamento(empresa_id),
            "por_cargo": services.kpis_headcount_por_cargo(empresa_id),
        })


class DashboardNominaView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    @extend_schema(tags=["Dashboard"])
    def get(self, request):
        empresa_id = _empresa_id_desde_request(request)
        meses = _meses_desde_request(request, default=12)
        return Response({
            "ultimo_periodo": services.kpis_nomina_ultimo_periodo(empresa_id),
            "evolucion": services.kpis_nomina_evolucion(empresa_id, meses=meses),
            "por_departamento": services.kpis_nomina_por_departamento(empresa_id),
        })


class DashboardAusenciasView(APIView):
    permission_classes = [IsAuthenticated, EsManager]

    @extend_schema(tags=["Dashboard"])
    def get(self, request):
        empresa_id = _empresa_id_desde_request(request)
        return Response({
            "resumen": services.kpis_ausencias_resumen(empresa_id),
            "saldos_vacaciones": services.kpis_saldos_vacaciones(empresa_id),
        })


class DashboardAlertasView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    @extend_schema(tags=["Dashboard"])
    def get(self, request):
        empresa_id = _empresa_id_desde_request(request)
        return Response(services.kpis_alertas(empresa_id))


class DashboardActividadView(APIView):
    permission_classes = [IsAuthenticated, EsRRHH]

    @extend_schema(tags=["Dashboard"])
    def get(self, request):
        empresa_id = _empresa_id_desde_request(request)
        return Response(services.kpis_actividad_reciente(empresa_id, limit=10))


class DashboardEventosView(APIView):
    permission_classes = [IsAuthenticated, EsManager]

    @extend_schema(tags=["Dashboard"])
    def get(self, request):
        empresa_id = _empresa_id_desde_request(request)
        try:
            dias = int(request.query_params.get("dias", 30))
        except (ValueError, TypeError):
            dias = 30
        return Response(services.kpis_proximos_eventos(empresa_id, dias=dias))