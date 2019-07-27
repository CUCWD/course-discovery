# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-07-25 16:48
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0091_auto_20190725_1645'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chapter',
            name='max_effort',
            field=models.DurationField(blank=True, help_text='Average number of hours:minutes:seconds [hh:mm:ss] needed to complete this chapter. This numberis calculated automatically by the Sequentials added.', null=True),
        ),
        migrations.AlterField(
            model_name='chapter',
            name='min_effort',
            field=models.DurationField(blank=True, help_text='Estimated number of hours:minutes:seconds [hh:mm:ss] needed to complete this chapter. This numberis calculated automatically by the Sequentials added.', null=True),
        ),
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