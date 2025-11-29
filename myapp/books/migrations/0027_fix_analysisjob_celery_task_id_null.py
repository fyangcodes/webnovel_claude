# Generated manually to fix celery_task_id constraint issue

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0026_alter_bookentity_options_bookentity_order_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='analysisjob',
            name='celery_task_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
