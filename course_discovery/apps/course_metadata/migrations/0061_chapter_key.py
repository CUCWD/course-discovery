# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2018-10-19 00:42
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0060_auto_20181019_0037'),
    ]

    operations = [
        migrations.AddField(
            model_name='chapter',
            name='key',
            field=models.CharField(default=None, max_length=255, unique=True),
            preserve_default=False,
        ),
    ]