# Generated by Django 5.0.7 on 2024-10-20 15:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0008_complaint_city_complaint_pincode_complaint_state'),
    ]

    operations = [
        migrations.RenameField(
            model_name='complaint',
            old_name='city',
            new_name='district',
        ),
    ]
