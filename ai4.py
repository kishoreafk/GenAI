from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.contrib.auth import get_user_model
import subprocess
import docker

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

# Code Execution Sandbox
client = docker.from_env()

def execute_code(submission):
    try:
        container = client.containers.run(
            "python:3.8",
            command=f"python3 -c {submission.code}",
            mem_limit="128m",
            cpu_period=100000,
            cpu_quota=50000,
            detach=True,
            stdout=True,
            stderr=True,
            remove=True,
            network_disabled=True
        )
        logs = container.logs().decode("utf-8")
        return logs.strip()
    except Exception as e:
        return str(e)

# Test Case Evaluation
def evaluate_submission(submission):
    problem = submission.problem
    test_cases = problem.test_cases
    passed = True
    results = []

    for test in test_cases:
        input_data = test["input"]
        expected_output = test["output"]
        
        actual_output = execute_code(submission)
        if actual_output != expected_output:
            passed = False
        results.append({"input": input_data, "expected": expected_output, "actual": actual_output})
    
    submission.status = 'accepted' if passed else 'rejected'
    submission.result = results
    submission.save()

# Real-Time Leaderboard
class Leaderboard(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    score = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.user.email} - {self.score}"

    @staticmethod
    def update_leaderboard(user, points):
        leaderboard_entry, created = Leaderboard.objects.get_or_create(user=user)
        leaderboard_entry.score += points
        leaderboard_entry.save()

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Submission)
def update_leaderboard_on_submission(sender, instance, **kwargs):
    if instance.status == 'accepted':
        Leaderboard.update_leaderboard(instance.user, points=10)

# URL Configurations
from django.urls import path
from . import views

urlpatterns = [
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('judge-dashboard/', views.judge_dashboard, name='judge_dashboard'),
    path('participant-dashboard/', views.participant_dashboard, name='participant_dashboard'),
]