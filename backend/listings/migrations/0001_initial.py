from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Listing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titre',           models.CharField(max_length=500)),
                ('lien',            models.URLField(blank=True, max_length=1000, null=True)),
                ('prix',            models.FloatField(blank=True, null=True)),
                ('devise',          models.CharField(default='TND', max_length=20)),
                ('localisation',    models.CharField(blank=True, max_length=300, null=True)),
                ('description',     models.TextField(blank=True, null=True)),
                ('pieces',          models.IntegerField(blank=True, null=True)),
                ('chambres',        models.IntegerField(blank=True, null=True)),
                ('salles_de_bain',  models.IntegerField(blank=True, null=True)),
                ('surface',         models.FloatField(blank=True, null=True)),
                ('type_bien',       models.CharField(blank=True, max_length=200, null=True)),
                ('date_post',       models.DateField(blank=True, null=True)),
                ('source',          models.CharField(
                    choices=[('mubawab', 'Mubawab'), ('tayara', 'Tayara')],
                    default='mubawab', max_length=20,
                )),
            ],
            options={
                'verbose_name': 'Annonce',
                'verbose_name_plural': 'Annonces',
                'ordering': ['-date_post', 'id'],
            },
        ),
    ]
