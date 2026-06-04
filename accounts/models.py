import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from datetime import timedelta


# ==================== MANAGERS ====================

class AdminManager(BaseUserManager):
    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('role', 'main_admin')
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)  # ← ده الناقص

        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class CustomerManager(BaseUserManager):
    def create_customer(self, phone_number, **extra_fields):
        if not phone_number:
            raise ValueError('Phone number is required')
        customer = self.model(phone_number=phone_number, **extra_fields)
        customer.set_unusable_password()
        customer.save(using=self._db)
        return customer


class ProviderManager(BaseUserManager):
    def create_provider(self, phone_number, **extra_fields):
        if not phone_number:
            raise ValueError('Phone number is required')
        provider = self.model(phone_number=phone_number, **extra_fields)
        provider.set_unusable_password()
        provider.save(using=self._db)
        return provider

class Specialization(models.Model):
    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'specializations'
        verbose_name = 'Specialization'
        ordering = ['name']

    def __str__(self):
        return self.name
# ==================== ADMIN ====================

class Admin(AbstractBaseUser, PermissionsMixin):

    ROLE_CHOICES = [
        ('main_admin', 'Main Admin'),
        ('staff_admin', 'Staff Admin'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff_admin')

    # Staff Admin بيتعمل من مين
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_admins'
    )

    # Permissions مرنة لل Staff Admin
    custom_permissions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom permissions for staff admins. e.g: {'can_approve_providers': true}"
    )
    groups = models.ManyToManyField(
        'auth.Group',
        blank=True,
        related_name='admin_set',      # ← التغيير
        related_query_name='admin',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        blank=True,
        related_name='admin_set',      # ← التغيير
        related_query_name='admin',
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=True)  # عشان يدخل Django Admin Panel
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = AdminManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name', 'phone_number']

    class Meta:
        db_table = 'admins'
        verbose_name = 'Admin'
        verbose_name_plural = 'Admins'

    def __str__(self):
        return f"{self.name} ({self.role})"

    def has_custom_permission(self, perm):
        if self.role == 'main_admin':
            return True
        return self.custom_permissions.get(perm, False)


# ==================== CUSTOMER ====================
# City & Region Models
class City(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cities'
        verbose_name = 'City'
        ordering = ['name']

    def __str__(self):
        return self.name


class Region(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        related_name='regions'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'regions'
        verbose_name = 'Region'
        ordering = ['name']
        unique_together = ('name', 'city')

    def __str__(self):
        return f"{self.name} - {self.city.name}"
    

class Customer(AbstractBaseUser):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True, null=True, blank=True)  # اختياري
    device_token = models.CharField(max_length=255, null=True, blank=True)
    # عشان نعرف لو رقم التليفون اتتأكد
    is_phone_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = CustomerManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['name']

    class Meta:
        db_table = 'customers'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return f"{self.name} - {self.phone_number}"

class CustomerAddress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        related_name='customer_addresses'
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        related_name='customer_addresses'
    )
    district = models.CharField(max_length=100)
    street = models.CharField(max_length=255)
    building_no = models.CharField(max_length=20, blank=True)
    floor_no = models.CharField(max_length=10, blank=True)
    apartment_no = models.CharField(max_length=10, blank=True)
    label = models.CharField(max_length=50, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customer_addresses'
        verbose_name = 'Customer Address'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.customer.name} - {self.city}, {self.region}"

    def save(self, *args, **kwargs):
        if self.is_default:
            CustomerAddress.objects.filter(
                customer=self.customer,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
# ==================== PROVIDER ====================

class Provider(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    address = models.TextField(blank=True)
    device_token = models.CharField(max_length=255, null=True, blank=True)
    specialization = models.ForeignKey(
        'Specialization',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='providers'
    )
    national_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    commercial_registration = models.CharField(max_length=50, unique=True, null=True, blank=True)
    contract_image = models.URLField(blank=True, null=True)
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_services = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_reviews = models.PositiveIntegerField(default=0)
    is_phone_verified = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = ProviderManager()
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['name', 'specialization']

    class Meta:
        db_table = 'providers'
        verbose_name = 'Provider'
        verbose_name_plural = 'Providers'

    def __str__(self):
        return f"{self.name} - {self.specialization}"

    def update_rating(self, new_rating):
        total = (self.average_rating * self.total_reviews) + new_rating
        self.total_reviews += 1
        self.average_rating = total / self.total_reviews
        self.save(update_fields=['average_rating', 'total_reviews'])


class ProviderAddress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        related_name='provider_addresses'
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.SET_NULL,
        null=True,
        related_name='provider_addresses'
    )
    district = models.CharField(max_length=100)        # ← أضفناه
    street = models.CharField(max_length=255, blank=True)
    building_no = models.CharField(max_length=20, blank=True)
    label = models.CharField(max_length=50, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'provider_addresses'
        verbose_name = 'Provider Address'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.provider.name} - {self.city}, {self.region}"

    def save(self, *args, **kwargs):
        if self.is_default:
            ProviderAddress.objects.filter(
                provider=self.provider,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    
# ==================== OTP ====================

class OTPVerification(models.Model):

    USER_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('provider', 'Provider'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=20)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)  # عشان نمنع brute force

    class Meta:
        db_table = 'otp_verifications'
        verbose_name = 'OTP Verification'
        indexes = [
            models.Index(fields=['phone_number', 'user_type']),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_valid(self):
        return not self.is_used and not self.is_expired() and self.attempts < 3

    def __str__(self):
        return f"OTP for {self.phone_number} - {'Valid' if self.is_valid() else 'Invalid'}"
    
# في models.py - ضيف ده في الآخر

import secrets

class BiometricToken(models.Model):
    USER_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('provider', 'Provider'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100)       # UUID اليوزر
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    token = models.CharField(
    max_length=128,
    unique=True,
    default=secrets.token_urlsafe)
    expires_at = models.DateTimeField(null=True, blank=True)
    device_id = models.CharField(max_length=255)     # معرّف الجهاز من الموبايل
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'biometric_tokens'
        # كل جهاز يقدر يكون عنده token واحد بس لكل يوزر
        unique_together = ('user_id', 'user_type', 'device_id')

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=90)
        super().save(*args, **kwargs)

    def is_valid(self):
        return self.is_active and timezone.now() < self.expires_at

    def __str__(self):
        return f"{self.user_type}:{self.user_id} - {self.device_id}"

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(64)
    
# reviews/models.py
import uuid
from django.db import models
from accounts.models import Customer, Provider


class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    customer = models.ForeignKey(
    Customer,
    on_delete=models.CASCADE,
    related_name='provider_reviews'   )

    provider = models.ForeignKey(
    Provider,
    on_delete=models.CASCADE,
    related_name='provider_reviews' )

    rating = models.PositiveSmallIntegerField()  # 1 → 5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reviews'
        # كل عميل يقدر يقيّم فني مرة واحدة بس
        unique_together = ('customer', 'provider')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer.name} → {self.provider.name}: {self.rating}★"

class PreviousWork(models.Model):
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name='previous_works'
    )
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES)
    media_url = models.URLField()          # Cloudinary URL
    thumbnail_url = models.URLField(blank=True, null=True)  # للفيديو بس
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'previous_works'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.provider.name} - {self.media_type} - {self.title or self.id}"