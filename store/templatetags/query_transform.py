# store/templatetags/query_transform.py
from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """
    Usage in templates:
      <a href="?{% query_transform sort='price_asc' %}">Sort</a>
      <a href="?{% query_transform page=None %}">Remove page</a>

    - Passing None removes that param.
    - Takes request from context (make sure 'django.template.context_processors.request' enabled).
    """
    request = context.get('request')
    if request is None:
        return ''

    params = request.GET.copy()
    for k, v in kwargs.items():
        # allow passing Python None via templates: {% query_transform page=None %}
        if v is None or (isinstance(v, str) and v.lower() == 'none'):
            if k in params:
                params.pop(k)
        else:
            params[k] = str(v)
    qs = params.urlencode()
    return qs
