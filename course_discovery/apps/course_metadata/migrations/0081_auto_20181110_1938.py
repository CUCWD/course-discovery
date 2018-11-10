# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-11-10 19:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0080_auto_20181110_1806'),
    ]

    operations = [
        migrations.CreateModel(
            name='SimulationMode',
            fields=[
                ('code', models.CharField(max_length=50, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('description_override', models.CharField(blank=True, default=None, help_text='Short description for simulation type.', max_length=255, null=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='simulation',
            name='simulation_mode',
        ),
        migrations.AddField(
            model_name='simulation',
            name='simulation_modes',
            field=models.ManyToManyField(blank=True, related_name='simulation_modes', to='course_metadata.SimulationMode'),
        ),
    ]
