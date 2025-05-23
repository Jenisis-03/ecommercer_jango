from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.core.mail import send_mail
from .models import CustomUser
import random

def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def signup(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return redirect('signup')
        
        user = CustomUser.objects.create_user(
            username=name,
            email=email,
            password=password
        )
        messages.success(request, 'Account created successfully')
        return redirect('login')
    return render(request, 'accounts/signup.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            user = CustomUser.objects.get(email=email)
            if user.check_password(password):
                otp = generate_otp()
                user.otp = otp
                user.save()
                
                # Send OTP via email
                send_mail(
                    'Login OTP',
                    f'Your OTP for login is: {otp}',
                    'your_email@gmail.com',
                    [email],
                    fail_silently=False,
                )
                
                return redirect('verify_otp')
            else:
                messages.error(request, 'Invalid credentials')
        except CustomUser.DoesNotExist:
            messages.error(request, 'User does not exist')
    
    return render(request, 'accounts/login.html')

def verify_otp(request):
    if request.method == 'POST':
        otp = request.POST.get('otp')
        try:
            user = CustomUser.objects.get(otp=otp)
            user.otp_verified = True
            user.otp = None
            user.save()
            login(request, user)
            return redirect('dashboard')
        except CustomUser.DoesNotExist:
            messages.error(request, 'Invalid OTP')
    
    return render(request, 'accounts/verify_otp.html')

def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'accounts/dashboard.html')

def signout(request):
    logout(request)
    return redirect('login')
