from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, username=None, email=None, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        email = self.normalize_email(email)
        if username is None:
            username = email
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username=None, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    objects = UserManager()
    phone = models.CharField(max_length=20, blank=True)
    birthdate = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'user'
        verbose_name = 'usuario'
        verbose_name_plural = 'usuarios'

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Sector(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    primary = models.BooleanField(default=False)

    class Meta:
        db_table = 'sector'
        verbose_name = 'sector'
        verbose_name_plural = 'sectores'

    def __str__(self):
        return self.name


class Broker(models.Model):
    name = models.CharField(max_length=100)
    link = models.URLField(blank=True)

    class Meta:
        db_table = 'broker'
        verbose_name = 'broker'
        verbose_name_plural = 'brokers'

    def __str__(self):
        return self.name


class Stock(models.Model):
    ticker = models.CharField(max_length=20, unique=True)
    company_name = models.CharField(max_length=200)
    sector = models.ForeignKey(Sector, on_delete=models.SET_NULL, null=True, blank=True, related_name='stocks')

    class Meta:
        db_table = 'stock'
        verbose_name = 'acción'
        verbose_name_plural = 'acciones'

    def __str__(self):
        return f"{self.ticker} - {self.company_name}"
