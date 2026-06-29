def current_staff(request):
    staff = None
    if getattr(request, 'user', None) and request.user.is_authenticated:
        staff = getattr(request.user, 'can_bo', None)
    return {'current_can_bo': staff}
