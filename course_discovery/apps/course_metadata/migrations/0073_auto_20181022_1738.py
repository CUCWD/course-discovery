# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-10-22 17:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0072_auto_20181022_1736'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courserun',
            name='max_effort',
            field=models.DurationField(blank=True, help_text='Average number of hours:minutes:seconds [hh:mm:ss] needed to complete this chapter. This number is calculated automatically by the Chapters added.', null=True),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='min_effort',
            field=models.DurationField(blank=True, help_text='Estimated number of hours:minutes:seconds [hh:mm:ss] needed to complete this chapter. This number is calculated automatically by the Chapters added.', null=True),
        ),
    ]
