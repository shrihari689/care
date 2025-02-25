# Generated by Django 2.2.11 on 2022-02-14 15:34

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facility', '0283_merge_20220128_0315'),
    ]

    operations = [
        migrations.AddField(
            model_name='patientconsultation',
            name='HBA1C',
            field=models.FloatField(default=None, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name='HBA1C parameter for reference to current blood sugar levels'),
        ),
    ]
