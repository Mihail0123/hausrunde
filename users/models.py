from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
# Create your models here.

class CustomUserManager(BaseUserManager):
    """
    Creates user with email instead of username
    Sets password with set_password()
    Allows to create superuser
    """
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('Users must have an email address'))

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
   username = None
   email = models.EmailField(_('email address'), unique=True)

   first_name = models.CharField(_('first name'), max_length=30,)
   last_name = models.CharField(_('last name'), max_length=30,)
   phone_number = models.CharField(_('phone number'), max_length=30, blank=True, null=True)

   USERNAME_FIELD = 'email'
   REQUIRED_FIELDS = []

   objects = CustomUserManager()

   def __str__(self):
       return self.email