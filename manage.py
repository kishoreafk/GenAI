import os
import django

# Set the correct settings module (use your actual Django project folder name)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AI.settings')

# Initialize Django
django.setup()

# Now import Django models
from django.contrib.auth.models import AbstractUser, BaseUserManager, PermissionsMixin

print("Django settings configured successfully!")
