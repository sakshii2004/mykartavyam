# Generated by Django 5.0.7 on 2024-12-30 09:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0024_autocloseduration_remove_complaint_posted_to_twitter_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='disabled',
            field=models.BooleanField(default=False),
        ),
    ]
