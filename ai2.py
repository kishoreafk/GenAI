from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.contrib.auth import get_user_model

# Custom User Manager
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, role='participant', **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, role='admin', **extra_fields)

# Custom User Model
class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('participant', 'Participant'),
        ('judge', 'Judge'),
    ]

    username = None  # Remove username field
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='participant')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} ({self.role})"

# Middleware for Role-Based Access Control
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

def role_required(allowed_roles):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated and request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            return redirect('no_permission')
        return _wrapped_view
    return decorator

# Views Example
from django.contrib.auth import login, logout, authenticate
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
@role_required(['admin'])
def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')

@login_required
@role_required(['judge'])
def judge_dashboard(request):
    return render(request, 'judge_dashboard.html')

@login_required
@role_required(['participant'])
def participant_dashboard(request):
    return render(request, 'participant_dashboard.html')

# Problem Submission System
class Problem(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    input_format = models.TextField()
    output_format = models.TextField()
    test_cases = models.JSONField()  # Stores input-output pairs
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return self.title

class Submission(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    code = models.TextField()
    language = models.CharField(max_length=50, choices=[('python', 'Python'), ('java', 'Java'), ('cpp', 'C++')])
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')], default='pending')
    result = models.TextField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.problem.title}"

# Test Case Evaluation
import subprocess

def evaluate_submission(submission):
    problem = submission.problem
    test_cases = problem.test_cases
    passed = True
    results = []

    for test in test_cases:
        input_data = test["input"]
        expected_output = test["output"]
        
        try:
            process = subprocess.run(
                ["python3"],
                input=submission.code.encode(),
                capture_output=True,
                text=True,
                timeout=5
            )
            actual_output = process.stdout.strip()
            if actual_output != expected_output:
                passed = False
            results.append({"input": input_data, "expected": expected_output, "actual": actual_output})
        except Exception as e:
            passed = False
            results.append({"error": str(e)})
    
    submission.status = 'accepted' if passed else 'rejected'
    submission.result = results
    submission.save()

# URL Configurations
from django.urls import path
from . import views

urlpatterns = [
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('judge-dashboard/', views.judge_dashboard, name='judge_dashboard'),
    path('participant-dashboard/', views.participant_dashboard, name='participant_dashboard'),
]
