# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-07-25 17:43
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0093_courserun_invitation_only'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='hidden',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='organization',
            name='slug',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='wordpress_post_id',
            field=models.BigIntegerField(blank=True, editable=False, help_text='This is the Wordpress Post id generated from the marketing frontend.', null=True),
        ),
    ]
