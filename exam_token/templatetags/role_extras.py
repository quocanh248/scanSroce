from django import template

register = template.Library()


@register.filter
def has_group(user, group_name: str) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return user.groups.filter(name=group_name).exists()


@register.filter
def has_any_group(user, group_names: str) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    names = [x.strip() for x in str(group_names or '').split(',') if x.strip()]
    if not names:
        return False
    return user.groups.filter(name__in=names).exists()
