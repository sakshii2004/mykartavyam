# Generated by Django 5.0.7 on 2024-11-06 12:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0012_complaint_posted_to_twitter'),
    ]

    operations = [
        migrations.AlterField(
            model_name='complaint',
            name='title',
            field=models.CharField(max_length=100),
        ),
    ]
