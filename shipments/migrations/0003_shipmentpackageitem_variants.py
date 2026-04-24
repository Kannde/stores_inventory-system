from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shipments', '0002_shipmentpackageitem_cost_price_unit_price_shortage'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipmentpackageitem',
            name='variant_size',
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='shipmentpackageitem',
            name='variant_color',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
