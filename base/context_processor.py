def group_check(request):
    if request.user.is_authenticated:
        return {
            'is_moderator': request.user.groups.filter(name='moderator').exists(),
            'is_admin': request.user.groups.filter(name='admin').exists(),
        }
    return {
        'is_moderator': False,
        'is_admin': False,
    }