# Generated by Django 2.1.5 on 2020-05-27 05:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_auto_20200527_1117'),
    ]

    operations = [
        migrations.AlterField(
            model_name='item',
            name='discount_price',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
