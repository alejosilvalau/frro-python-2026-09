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
    TRADING_CURRENCY_CHOICES = [('ARS', 'Pesos (ARS)'), ('USD', 'Dólares (USD)')]
    TIPO_CHOICES = [
        ('accion', 'Acción'),
        ('cedear', 'CEDEAR'),
        ('bono', 'Bono'),
        ('letra', 'Letra'),
    ]

    CEDEAR_KIND_CHOICES = [
        ('company', 'Empresa'),
        ('etf', 'ETF'),
    ]
    ISSUER_CHOICES = [
        ('national', 'Nacional / soberano'),
        ('provincial', 'Provincial'),
        ('municipal', 'Municipal'),
        ('bcra', 'BCRA'),
        ('corporate', 'Corporativo'),
        ('trust', 'Fideicomiso'),
        ('other', 'Otro'),
    ]
    RATE_REFERENCE_CHOICES = [
        ('fixed', 'Tasa fija'),
        ('cer', 'CER'),
        ('tamar', 'TAMAR'),
        ('dollar_linked', 'Dólar linked'),
        ('dual', 'Dual'),
        ('other', 'Otra'),
    ]
    PAYMENT_STYLE_CHOICES = [
        ('capitalizable', 'Capitalizable'),
        ('periodic_coupon', 'Cupón periódico'),
        ('step_up', 'Step-up'),
        ('discount', 'A descuento'),
        ('zero_coupon', 'Cero cupón'),
        ('other', 'Otra'),
    ]

    ticker = models.CharField(max_length=20, unique=True)
    company_name = models.CharField(max_length=200)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='accion')
    trading_currency = models.CharField(
        max_length=3, choices=TRADING_CURRENCY_CHOICES, null=True, blank=True,
    )
    sector = models.ForeignKey(Sector, on_delete=models.SET_NULL, null=True, blank=True, related_name='stocks')
    cedear_kind = models.CharField(max_length=12, choices=CEDEAR_KIND_CHOICES, null=True, blank=True)
    issuer_type = models.CharField(max_length=12, choices=ISSUER_CHOICES, null=True, blank=True)
    rate_reference = models.CharField(max_length=16, choices=RATE_REFERENCE_CHOICES, null=True, blank=True)
    payment_style = models.CharField(max_length=20, choices=PAYMENT_STYLE_CHOICES, null=True, blank=True)
    instrument_family = models.CharField(max_length=30, blank=True)
    underlying_ticker = models.CharField(max_length=20, blank=True)
    classification_source = models.CharField(max_length=255, blank=True)
    classification_date = models.DateField(null=True, blank=True)
    classification_manual = models.BooleanField(default=False)

    class Meta:
        db_table = 'stock'
        verbose_name = 'instrumento'
        verbose_name_plural = 'instrumentos'
        ordering = ['tipo', 'ticker']

    def __str__(self):
        return f"{self.ticker} - {self.company_name}"
