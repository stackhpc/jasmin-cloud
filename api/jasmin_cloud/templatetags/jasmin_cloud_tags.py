"""
Custom template tags for the cloud-auth package.
"""

from django import template
from django.urls import NoReverseMatch, reverse
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

from cloud_auth.settings import auth_settings
from ..settings import cloud_settings


register = template.Library()


@register.simple_tag()
def jasmin_cloud_current_cloud():
    """
    Insert the name of the current cloud.
    """
    return cloud_settings.AVAILABLE_CLOUDS[cloud_settings.CURRENT_CLOUD]['label']


@register.simple_tag(takes_context = True)
def cloud_auth_login(context):
    """
    Include a login snippet using cloud-auth.
    """
    login_url = reverse('cloud_auth:login')
    snippet = "<li><a href='{href}?{param}={next}'>Sign in</a></li>"
    snippet = format_html(
        snippet,
        href = login_url,
        param = auth_settings.NEXT_URL_PARAM,
        next = escape(context['request'].path)
    )
    return mark_safe(snippet)


@register.simple_tag(takes_context = True)
def cloud_auth_logout(context):
    """
    Include a logout snippet using cloud-auth.
    """
    logout_url = reverse('cloud_auth:logout')
    snippet = """<li class="dropdown">
        <a href="#" class="dropdown-toggle" data-toggle="dropdown">
            {user}
            <b class="caret"></b>
        </a>
        <ul class="dropdown-menu">
            <li><a href='{href}?{param}={next}'>Sign out</a></li>
        </ul>
    </li>"""
    snippet = format_html(
        snippet,
        user = escape(context['user']),
        href = logout_url,
        param = auth_settings.NEXT_URL_PARAM,
        next = escape(context['request'].path)
    )
    return mark_safe(snippet)
