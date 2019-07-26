# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-07-25 15:27
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields
import sortedm2m.fields
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0085_courserun_wordpress_post_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='Chapter',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('location', models.CharField(max_length=255, unique=True)),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, verbose_name='UUID')),
                ('lms_web_url', models.URLField(blank=True, null=True)),
                ('min_effort', models.DurationField(blank=True, help_text='Estimated number of hours:minutes:seconds [hh:mm:ss] needed to complete this chapter.', null=True)),
                ('max_effort', models.DurationField(blank=True, help_text='Average number of hours:minutes:seconds [hh:mm:ss] needed to complete this chapter.', null=True)),
                ('title', models.CharField(blank=True, default=None, max_length=255, null=True)),
                ('goal_override', models.TextField(blank=True, default=None, help_text='Goal description specific for this chapter within the course.', null=True)),
                ('slug', models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ('hidden', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.AddField(
            model_name='courserun',
            name='chapters',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, related_name='course_runs', to='course_metadata.Chapter'),
        ),
    ]
