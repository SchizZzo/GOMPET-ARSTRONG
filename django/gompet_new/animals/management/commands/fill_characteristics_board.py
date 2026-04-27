from copy import deepcopy

from django.core.management.base import BaseCommand
from django.db import transaction

from animals.models import Animal


DEFAULT_CHARACTERISTICS_BOARD = [
    {"bool": True, "title": "vaccinated"},
    {"bool": False, "title": "neutered"},
    {"bool": False, "title": "dewormed"},
    {"bool": False, "title": "has_chip"},
    {"bool": False, "title": "accepts_cats"},
    {"bool": False, "title": "accepts_dogs"},
    {"bool": False, "title": "clean"},
    {"bool": False, "title": "hypoallergenic"},
    {"bool": False, "title": "no_separation_anxiety"},
    {"bool": False, "title": "suitable_for_apartment"},
    {"bool": False, "title": "vigorous"},
    {"bool": False, "title": "children_friendly"},
    {"bool": False, "title": "learns_fast"},
    {"bool": False, "title": "special_diet"},
    {"bool": False, "title": "calm_at_home"},
    {"bool": False, "title": "can_live_in_a_city"},
    {"bool": False, "title": "needs_mental_stimulation"},
    {"bool": False, "title": "gentle"},
    {"bool": False, "title": "watchdog"},
    {"bool": False, "title": "has_health_book"},
]


class Command(BaseCommand):
    help = (
        "Uzupełnia animals.characteristic_board domyślną listą cech. "
        "Domyślnie aktualizuje tylko puste rekordy."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Nadpisz characteristic_board dla wszystkich zwierząt.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        force = options["force"]

        queryset = Animal.objects.all().only("id", "characteristic_board")
        if not force:
            queryset = queryset.filter(characteristic_board__in=[None, []])

        animals_to_update = []
        for animal in queryset.iterator(chunk_size=500):
            animal.characteristic_board = deepcopy(DEFAULT_CHARACTERISTICS_BOARD)
            animals_to_update.append(animal)

        if not animals_to_update:
            self.stdout.write(
                self.style.WARNING("Brak rekordów do aktualizacji.")
            )
            return

        Animal.objects.bulk_update(animals_to_update, ["characteristic_board"], batch_size=500)
        self.stdout.write(
            self.style.SUCCESS(
                f"Zaktualizowano characteristic_board dla {len(animals_to_update)} zwierząt."
            )
        )
