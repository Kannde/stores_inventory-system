from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_storesettings_skroda'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='skroda_seller_phone',
            field=models.CharField(
                blank=True,
                max_length=30,
                help_text='Phone number the store owner registered on Skroda (e.g. 0241234567)',
            ),
        ),
    ]
