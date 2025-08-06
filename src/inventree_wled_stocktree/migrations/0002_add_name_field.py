# Generated manually for adding name field to WledInstance

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventree_wled_stocktree', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='wledinstance',
            name='name',
            field=models.CharField(blank=True, max_length=100, verbose_name='Custom Name'),
        ),
    ]
