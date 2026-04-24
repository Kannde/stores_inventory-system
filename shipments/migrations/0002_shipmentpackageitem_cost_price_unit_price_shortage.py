from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shipments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipmentpackageitem',
            name='cost_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Actual cost per unit on receipt',
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='shipmentpackageitem',
            name='unit_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Selling price to set on product',
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='shipmentpackageitem',
            name='shortage_reason',
            field=models.CharField(
                blank=True,
                help_text='Reason items were short (damaged, missing, short-shipped)',
                max_length=300,
            ),
        ),
    ]
