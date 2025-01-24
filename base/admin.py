from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Category
from .models import Complaint
from .models import CustomUser, Badge

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('phone_number', 'name', 'is_staff', 'is_active',)
    list_filter = ('is_staff', 'is_active',)
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Personal info', {'fields': ('name', 'about_me', 'profile_picture')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'password1', 'password2', 'is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}
        ),
    )
    search_fields = ('phone_number',)
    ordering = ('phone_number',)
    filter_horizontal = ('groups', 'user_permissions',)

admin.site.register(CustomUser, CustomUserAdmin)   

admin.site.register(Category)
admin.site.register(Complaint)
admin.site.register(Badge)

