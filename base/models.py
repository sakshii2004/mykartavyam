from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils.timezone import now, timedelta
from .constants import STATE_CHOICES



class Badge(models.Model):
    name = models.CharField(max_length=100, blank=False, null=False)  
    min_complaints = models.PositiveIntegerField(blank=False, null=False)  
    badge_icon = models.ImageField(upload_to='badges/', blank=False, null=False)

    def __str__(self):
        return f"{self.name} - {self.min_complaints} Complaints"
      
    
class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, email=None, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('The Phone Number field must be set')
        
        email = self.normalize_email(email)
        user = self.model(phone_number=phone_number, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(phone_number, email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    DISABLED_OPTIONS = [
        ('FALSE', 'FALSE'),
        ('TRUE', 'TRUE'),
    ]
    phone_number = models.CharField(max_length=15, unique=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    about_me = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    current_badge = models.ForeignKey(Badge, on_delete=models.SET_NULL, null=True, blank=True)
    disabled = models.CharField(max_length=20, choices=DISABLED_OPTIONS, default='FALSE')
    created = models.DateTimeField(auto_now_add = True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.phone_number

class Category(models.Model):
    name = models.CharField(max_length=100, null=False, blank = False)
    abbreviation = models.CharField(max_length=5, null=False, blank = False)
    disabled = models.BooleanField(default=False)

    def __str__(self):
        return self.name 

class Complaint(models.Model):
    STATUS_CHOICES = [
        ('AWAITING_APPROVAL', 'AWAITING APPROVAL'),
        ('OPEN', 'OPEN'),
        ('AUTO_CLOSED', 'AUTO CLOSED'),
        ('RESOLVED', 'RESOLVED'),
        ('REOPENED', 'REOPENED'),
        ('FORCE_CLOSED', 'FORCE CLOSED')]
    
    reference_id = models.CharField(max_length = 50, null=True, blank = False)
    title = models.CharField(max_length = 80, null=False, blank = False) #max length 50 characters
    category = models.ForeignKey(Category, on_delete = models.SET_NULL, null=True, blank = False, related_name='complain_set')
    description = models.TextField(null=True, blank=True)
    landmark = models.CharField(max_length = 80, null=True, blank = True) #migrate db
    citizen = models.ForeignKey(CustomUser, on_delete = models.CASCADE)
    status =  models.CharField(max_length=20, choices=STATUS_CHOICES, default='AWAITING_APPROVAL')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=False, verbose_name='Latitude')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=False, verbose_name='Longitude')    
    image = models.ImageField(upload_to='complaint_images/', null=False, blank=False)  
    created = models.DateTimeField(auto_now_add = True)
    opened = models.DateTimeField(null=True, blank=True)
    reopened = models.DateTimeField(null=True, blank=True)
    district = models.CharField(max_length=100, null=True, blank=False)
    state = models.CharField(max_length=100, choices=STATE_CHOICES, null=True, blank=False) 
    #pincode = models.CharField(max_length=10, null=True, blank=True)
    posted_on_x = models.BooleanField(default=False)

    def __str__(self):
        return self.title
    

class ModeratorApproval(models.Model):
    ACTION_CHOICES = [        
        ('APPROVED_BY_MOD', 'APPROVED_BY_MOD'),
        ('APPROVED_BY_AI', 'APPROVED_BY_AI'),
        ('REJECTED', 'REJECTED'), 
        ('DELETED', 'DELETED'), 
        ('DISABLE_USER', 'DISABLE_USER'),
        ('ENABLE_USER', 'ENABLE_USER'),
    ]

    user = models.ForeignKey(CustomUser, on_delete = models.SET_NULL, null=True)
    complaint = models.ForeignKey(Complaint, on_delete = models.SET_NULL, null=True)
    reference_id = models.CharField(max_length = 50, null=True, blank = False)
    title = models.CharField(max_length = 80, null=True, blank = False)
    moderator = models.ForeignKey(CustomUser, on_delete = models.SET_NULL, null=True, related_name='moderated_complaints')
    created = models.DateTimeField(auto_now_add = True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='APPROVED_BY_MOD')

class AutocloseDuration(models.Model):
    duration = models.IntegerField(null=False, blank=False, default=15)
    created = models.DateTimeField(auto_now_add = True)

class OTP(models.Model):
    phone_number = models.CharField(max_length=15, unique=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return now() > self.created_at + timedelta(minutes=5) 





