from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_remove_pin_unique_together'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='skroda_enabled',
            field=models.BooleanField(default=False, help_text='Enable Skroda escrow payments at checkout'),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='skroda_secret_key',
            field=models.CharField(blank=True, max_length=200, help_text='Skroda secret API key (sk_live_... or sk_test_...)'),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='skroda_webhook_secret',
            field=models.CharField(blank=True, max_length=200, help_text='Skroda webhook signing secret'),
        ),
        migrations.AddField(
            model_name='storesettings',
            name='skroda_fee_paid_by',
            field=models.CharField(
                choices=[('buyer', 'Buyer pays fee'), ('seller', 'Seller pays fee')],
                default='buyer',
                max_length=10,
            ),
        ),
    ]
