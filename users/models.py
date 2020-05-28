from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager
)
from django.db import transaction
from rest_framework.authtoken.models import Token
import datetime
from django.utils import timezone

def expiry_time():
       return timezone.now() + timezone.timedelta(minutes=10)


class UserManager(BaseUserManager):
    def create_user(self, email, password, **other_fields):
        email = self.normalize_email(email)
        user = self.model(email=email)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password, **other_fields):
        
        other_fields.setdefault('is_staff', True)
        other_fields.setdefault('is_active', True)

        user = self.create_user(email, password)
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)

        return user


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(max_length = 100, unique=True, verbose_name='E-mail')
    password = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    reference_id = models.CharField(max_length=50)
    date_time_created = models.DateTimeField(auto_now_add=True)

    REQUIRED_FIELDS = ['password']
    USERNAME_FIELD = 'email'

    objects = UserManager()

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            Token.objects.get_or_create(user=self)

    def __str__(self):
        return self.email

class Vendor(models.Model):
    email = models.EmailField(max_length=100, unique = True, verbose_name = 'E-mail')
    business_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=50)
    date_time_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

class Customer(models.Model):
    first_name = models.CharField( max_length=100)
    last_name = models.CharField( max_length=100)
    email = models.EmailField(max_length=100,  unique = True, verbose_name = 'E-mail')
    phone_number = models.CharField(max_length=50)
    date_time_created = models.DateTimeField(auto_now_add=True)
    amount_outstanding = models.FloatField(default = 0.00)

    def __str__(self):
        return self.email
    def update_balance(self, amount):
        return self.amount_outstanding + amount

class Menu(models.Model):
    BOOL_CHOICES = ((True, 'Yes'), (False, 'No'))

    vendor = models.ForeignKey(Vendor, on_delete = models.CASCADE)
    name = models.CharField( max_length=100)
    description = models.CharField( max_length=200)
    price = models.FloatField(default = 0.00)
    quantity = models.IntegerField()
    is_recurring = models.BooleanField(choices = BOOL_CHOICES)
    avaliable = models.BooleanField(choices = BOOL_CHOICES, default= True)
    frequency_of_reocurrence = models.CharField(max_length=10, blank=True)
    date_time_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class OrderStatus(models.Model):
    name = models.CharField(max_length=50)

class PaymentStatus(models.Model):
    name = models.CharField(max_length=50)  



class Order(models.Model):
    BOOL_CHOICES = ((True, 'Yes'), (False, 'No'))

    customer = models.ForeignKey(Customer, on_delete = models.CASCADE)
    vendor = models.ForeignKey(Vendor, on_delete = models.CASCADE)
    description = models.CharField(max_length=200)
    items_ordered = models.IntegerField()
    amount_due = models.FloatField(default = 0.00)
    amount_paid = models.FloatField(default = 0.00)
    amount_outstanding = models.FloatField(default = 0.00)
    payment_status = models.ForeignKey(PaymentStatus, on_delete = models.CASCADE)
    order_status = models.ForeignKey(OrderStatus, on_delete = models.CASCADE)
    cancel_expiry = models.DateTimeField(default = expiry_time(), blank=True)
    delivery_date_time = models.DateTimeField(default = timezone.now(), blank=True)
    date_time_created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.description

class OrderedItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE)

class MessageStatus(models.Model):
    name = models.CharField(max_length=50)

class Notification(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete = models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete = models.CASCADE)
    message_status = models.ForeignKey(MessageStatus, on_delete = models.CASCADE)
    message = models.CharField(max_length = 255)
    date_time_created = models.DateTimeField(auto_now_add=True)