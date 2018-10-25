# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-10-21 19:38
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0068_sequential_course_run'),
    ]

    operations = [
        migrations.AddField(
            model_name='sequential',
            name='wordpress_post_id',
            field=models.BigIntegerField(blank=True, editable=False, help_text='This is the Wordpress Post id generated from the marketing frontend.', null=True),
        ),
    ]
