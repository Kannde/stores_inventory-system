import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0008_storesettings_skroda'),
        ('sales', '0003_sale_escrow'),
    ]

    operations = [
        migrations.CreateModel(
            name='SkrodaTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('skroda_id', models.CharField(max_length=100, unique=True)),
                ('reference_code', models.CharField(blank=True, max_length=50)),
                ('status', models.CharField(
                    choices=[
                        ('draft', 'Draft'), ('negotiation', 'Negotiation'), ('agreed', 'Agreed'),
                        ('funded', 'Funded'), ('shipped', 'Shipped'), ('agent_received', 'Agent Received'),
                        ('delivered', 'Delivered'), ('completed', 'Completed'), ('disputed', 'Disputed'),
                        ('cancelled', 'Cancelled'), ('refunded', 'Refunded'),
                    ],
                    default='draft', max_length=30,
                )),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('checkout_url', models.TextField(blank=True)),
                ('invite_link', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sale', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='skroda_transaction',
                    to='sales.sale',
                )),
                ('store', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='skroda_transactions',
                    to='core.store',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='SkrodaWebhookEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.CharField(max_length=100, unique=True)),
                ('event_type', models.CharField(max_length=60)),
                ('payload', models.JSONField()),
                ('processed_at', models.DateTimeField(auto_now_add=True)),
                ('store', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='skroda_webhook_events',
                    to='core.store',
                )),
            ],
        ),
    ]
