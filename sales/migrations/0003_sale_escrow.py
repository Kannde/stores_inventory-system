from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0002_sale_customer_name_sale_customer_phone_creditaccount_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sale',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending_payment', 'Pending Payment'),
                    ('completed', 'Completed'),
                    ('refunded', 'Refunded'),
                    ('partial_refund', 'Partial Refund'),
                ],
                default='completed',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='sale',
            name='payment_method',
            field=models.CharField(
                choices=[
                    ('cash', 'Cash'),
                    ('momo', 'Mobile Money'),
                    ('card', 'Card'),
                    ('credit', 'Credit'),
                    ('mixed', 'Mixed'),
                    ('escrow', 'Escrow (Skroda)'),
                ],
                default='cash',
                max_length=10,
            ),
        ),
    ]
