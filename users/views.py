@login_required
def edit_profile(request):
    if request.method == 'POST':
        # Add old password verification
        old_password = request.POST.get('old_password')
        if not request.user.check_password(old_password):
            messages.error(request, 'Current password is incorrect')
            return redirect('edit_profile')
        # ... rest of the code