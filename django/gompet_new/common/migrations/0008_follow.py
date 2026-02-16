from django.conf import settings
from django.db import migrations, models
import django.utils.timezone
import django.db.models.deletion


def default_follow_notification_preferences() -> dict[str, bool]:
    return {
        "posts": True,
        "status_changes": True,
        "comments": False,
    }


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('common', '0007_rename_notification_organization_member_id'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Follow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('target_id', models.PositiveBigIntegerField()),
                ('notification_preferences', models.JSONField(blank=True, default=default_follow_notification_preferences)),
                ('target_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='follows', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'follows',
                'ordering': ('-created_at',),
            },
        ),
        migrations.AddIndex(
            model_name='follow',
            index=models.Index(fields=['target_type', 'target_id'], name='idx_follow_target'),
        ),
        migrations.AddConstraint(
            model_name='follow',
            constraint=models.UniqueConstraint(fields=('user', 'target_type', 'target_id'), name='uniq_user_follow_per_target'),
        ),
    ]
