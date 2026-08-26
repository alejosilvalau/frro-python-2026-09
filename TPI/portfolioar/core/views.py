from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .business import AuthManager


def home(request):
    if request.user.is_authenticated:
        return redirect('portfolio:dashboard')
    return render(request, 'core/home.html')


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            auth_manager = AuthManager()
            auth_manager.login(request, email, password)
            return redirect('portfolio:dashboard')
        except ValueError as e:
            return render(request, 'core/login.html', {'error': str(e)})

    return render(request, 'core/login.html')


def register_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        phone = request.POST.get('phone')
        birthdate = request.POST.get('birthdate')

        if password != password_confirm:
            return render(request, 'core/register.html', {'error': 'Las contraseñas no coinciden'})

        try:
            auth_manager = AuthManager()
            auth_manager.register(first_name, last_name, email, password, phone, birthdate)
            return redirect('core:login')
        except ValueError as e:
            return render(request, 'core/register.html', {'error': str(e)})

    return render(request, 'core/register.html')


@login_required
def logout_view(request):
    auth_manager = AuthManager()
    auth_manager.logout(request)
    return redirect('core:home')


@login_required
def profile_view(request):
    return render(request, 'core/profile.html', {'user': request.user})


@login_required
def change_password_view(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        new_password_confirm = request.POST.get('new_password_confirm')

        if new_password != new_password_confirm:
            return render(request, 'core/change_password.html', {'error': 'Las contraseñas no coinciden'})

        try:
            auth_manager = AuthManager()
            auth_manager.change_password(request.user, old_password, new_password)
            return redirect('core:profile')
        except ValueError as e:
            return render(request, 'core/change_password.html', {'error': str(e)})

    return render(request, 'core/change_password.html')
