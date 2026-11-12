"""
Templatetags personalizados para los reportes.

Uso en templates:
    {% load reporte_extras %}
    {{ diccionario|get_item:"clave" }}
"""
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Devuelve el valor de un diccionario por su clave.

    Uso:
        {{ mi_dict|get_item:"nombre" }}

    Soporta:
        - dict con claves strings
        - dict con claves int
        - objetos (accede al atributo)
        - None (devuelve "")
    """
    if dictionary is None:
        return ""

    # Si es un dict
    if isinstance(dictionary, dict):
        return dictionary.get(key, "")

    # Si es un objeto, intentar como atributo
    try:
        return getattr(dictionary, key, "")
    except Exception:
        return ""