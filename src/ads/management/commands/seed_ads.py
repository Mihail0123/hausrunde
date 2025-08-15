from decimal import Decimal
import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from src.ads.models import Ad
from faker import Faker

class Command(BaseCommand):
    help = "Seed database with demo users and ads"

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=5, help="How many users to create")
        parser.add_argument("--ads", type=int, default=50, help="How many ads to create")
        parser.add_argument("--password", type=str, default="Passw0rd!", help="Default password for created users")

    def handle(self, *args, **opts):
        fake = Faker()
        User = get_user_model()

        # create users
        users = []
        for i in range(opts["users"]):
            email = f"user{i+1}@example.com"
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name(),
                    "phone_number": fake.numerify(text="+49##########"),
                    "is_active": True,
                },
            )
            if created:
                user.set_password(opts["password"])
                user.save()
            users.append(user)

        # create ads
        housing_types = ["apartment", "wohnung", "house", "studio", "room", "flatshare"]
        locations = ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt", "Dresden", "Leipzig"]

        for _ in range(opts["ads"]):
            owner = random.choice(users)
            price = Decimal(random.randrange(300, 3500))
            rooms = random.randint(1, 6)

            Ad.objects.create(
                title=fake.sentence(nb_words=5),
                description=fake.paragraph(nb_sentences=5),
                location=random.choice(locations),
                price=price,
                rooms=rooms,
                housing_type=random.choice(housing_types),
                is_active=True,
                owner=owner,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(users)} users and {opts['ads']} ads. "
                f"Default user password: {opts['password']}"
            )
        )
