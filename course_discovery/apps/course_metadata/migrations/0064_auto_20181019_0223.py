# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-10-19 02:23
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0063_auto_20181019_0217'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chapter',
            name='max_effort',
            field=models.DurationField(blank=True, help_text='Average number of hours:minutes:seconds [hh:mm:ss] needed to complete this chapter.', null=True),
        ),
        migrations.AlterField(
            model_name='chapter',
            name='min_effort',
            field=models.DurationField(blank=True, help_text='Estimated number of hours:minutes:seconds [hh:mm:ss] needed to complete this chapter.', null=True),
        ),
    ]