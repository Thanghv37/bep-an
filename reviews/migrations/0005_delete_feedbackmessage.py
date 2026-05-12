from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0004_feedbackmessage'),
    ]

    operations = [
        migrations.DeleteModel(
            name='FeedbackMessage',
        ),
    ]
