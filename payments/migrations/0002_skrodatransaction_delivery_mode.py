from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='skrodatransaction',
            name='delivery_mode',
            field=models.CharField(
                choices=[
                    ('agent_preferred', 'Agent Preferred'),
                    ('agent_required', 'Agent Required'),
                    ('direct_only', 'Direct Only'),
                ],
                default='agent_preferred',
                max_length=20,
            ),
        ),
    ]
