"""
Management command: python manage.py seed_data
CSV uses semicolon (;) as delimiter.
"""
import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from listings.models import Listing


def parse_float(val):
    if not val or str(val).strip().upper() in ('N/A', '', 'PRIX À CONSULTER', 'PRIX A CONSULTER'):
        return None
    cleaned = str(val).replace('\xa0', '').replace(' ', '').replace('TND', '').replace('DT', '').replace('€', '').replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_int(val):
    f = parse_float(val)
    return int(f) if f is not None else None


def parse_surface(val):
    if not val or str(val).strip().upper() == 'N/A':
        return None
    cleaned = str(val).replace('²', '').replace('m²', '').replace('m2', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_date(val):
    if not val or str(val).strip().upper() == 'N/A':
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


class Command(BaseCommand):
    help = 'Load mubawab_data.csv and tayara_data.csv into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-dir',
            default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'data'),
            help='Path to folder containing the CSV files',
        )

    def handle(self, *args, **options):
        data_dir = os.path.abspath(options['data_dir'])
        self.stdout.write(f'Looking for CSV files in: {data_dir}')

        files = {
            'mubawab': os.path.join(data_dir, 'mubawab_data.csv'),
            'tayara':  os.path.join(data_dir, 'tayara_data.csv'),
        }

        Listing.objects.all().delete()
        self.stdout.write('Cleared existing listings.')

        total = 0
        for source, filepath in files.items():
            if not os.path.exists(filepath):
                self.stdout.write(self.style.WARNING(f'  File not found: {filepath}  -- skipping'))
                continue

            count = 0
            with open(filepath, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    prix_raw = row.get('Prix', '') or ''
                    devise   = 'DT' if source == 'tayara' else 'TND'
                    if 'DT' in prix_raw.upper():
                        devise = 'DT'
                    elif 'TND' in prix_raw.upper():
                        devise = 'TND'

                    titre = (row.get('Titre') or '').strip()
                    if not titre or titre.upper() == 'N/A':
                        titre = 'Sans titre'

                    Listing.objects.create(
                        titre          = titre,
                        lien           = (row.get('Lien') or '').strip() or None,
                        prix           = parse_float(prix_raw),
                        devise         = devise,
                        localisation   = (row.get('Localisation') or '').strip() or None,
                        description    = (row.get('Description') or '').strip() or None,
                        pieces         = parse_int(row.get('Pieces')),
                        chambres       = parse_int(row.get('Chambres')),
                        salles_de_bain = parse_int(row.get('SallesDeBain')),
                        surface        = parse_surface(row.get('Surface')),
                        type_bien      = (row.get('Type') or '').strip() or None,
                        date_post      = parse_date(row.get('DatePost')),
                        source         = source,
                    )
                    count += 1

            self.stdout.write(self.style.SUCCESS(f'  [{source}] Imported {count} listings'))
            total += count

        self.stdout.write(self.style.SUCCESS(f'\nTotal: {total} listings loaded into DB'))
