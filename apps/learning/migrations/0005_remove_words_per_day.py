# Generated manually on 2025-06-29 11:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('learning', '0004_remove_learning_unit'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='learningplan',
            name='words_per_day',
        ),
    ] 