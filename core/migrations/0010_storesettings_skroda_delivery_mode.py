from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_storesettings_skroda_seller_phone'),
    ]

    operations = [
        migrations.AddField(
            model_name='storesettings',
            name='skroda_delivery_mode',
            field=models.CharField(
                choices=[
                    ('agent_preferred', 'Agent preferred (use agent if available, fall back to direct)'),
                    ('agent_required', "Agent required (hold transaction if no agent in buyer's city)"),
                    ('direct_only', 'Direct only (seller ships directly, no agent)'),
                ],
                default='agent_preferred',
                max_length=20,
            ),
        ),
    ]
