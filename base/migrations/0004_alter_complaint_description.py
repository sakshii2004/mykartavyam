# Generated by Django 5.0.7 on 2024-08-17 11:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0003_customuser_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='complaint',
            name='description',
            field=models.CharField(blank=True, max_length=300, null=True),
        ),
    ]
