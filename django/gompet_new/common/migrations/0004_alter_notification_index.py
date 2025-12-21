from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0003_notification"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="notification",
            name="idx_notification_recipient_read",
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=("recipient", "is_read", "created_at"),
                name="idx_notification_rec_read",
            ),
        ),
    ]
