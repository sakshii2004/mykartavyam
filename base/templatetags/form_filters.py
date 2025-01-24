from django import template

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})

@register.filter
def truncate_with_ellipsis(value, max_length):
    if len(value) > max_length:
        return value[:max_length] + "..."
    return value