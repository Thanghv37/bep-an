import django.core.validators
from django.db import migrations, models


def wipe_dish_reviews(apps, schema_editor):
    """User confirmed: xóa sạch đánh giá like/dislike cũ, bắt đầu lại với 1-5 sao."""
    DishReview = apps.get_model('reviews', 'DishReview')
    DishReview.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0007_alter_dishsuggestion_count_dishsuggestionvote'),
    ]

    operations = [
        migrations.RunPython(wipe_dish_reviews, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='dishreview',
            name='evaluation',
        ),
        migrations.AddField(
            model_name='dishreview',
            name='rating',
            field=models.PositiveSmallIntegerField(
                default=5,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5),
                ],
                verbose_name='Số sao (1-5)',
            ),
            preserve_default=False,
        ),
    ]
