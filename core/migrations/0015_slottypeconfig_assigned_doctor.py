from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_alter_token_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='slottypeconfig',
            name='assigned_doctor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='slot_type_configs',
                to='core.doctorprofile',
            ),
        ),
    ]
