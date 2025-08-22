import random
from decimal import Decimal
from datetime import timedelta

import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from factory import Faker, LazyFunction, post_generation
from factory.django import DjangoModelFactory, ImageField

from .models import Ad, AdImage, Booking, Review

# Rough bounding boxes for major German cities: (lat_min, lat_max, lon_min, lon_max)
CITY_BBOXES = {
    "berlin": (52.33, 52.65, 13.10, 13.75),
    "hamburg": (53.40, 53.65, 9.80, 10.25),
    "munich": (48.06, 48.22, 11.45, 11.72),
    "cologne": (50.87, 50.99, 6.85, 7.10),
    "frankfurt": (50.03, 50.17, 8.55, 8.80),
    "dusseldorf": (51.15, 51.30, 6.70, 6.90),
    "stuttgart": (48.70, 48.85, 9.05, 9.30),
    "leipzig": (51.25, 51.40, 12.25, 12.50),
    "dresden": (51.00, 51.12, 13.60, 13.90),
    "nuremberg": (49.37, 49.52, 11.00, 11.20),
}

def rand_city() -> str:
    return random.choice(list(CITY_BBOXES.keys()))

def rand_point_in_city(city_key: str):
    lat_min, lat_max, lon_min, lon_max = CITY_BBOXES[city_key]
    lat = round(random.uniform(lat_min, lat_max), 6)
    lon = round(random.uniform(lon_min, lon_max), 6)
    return lat, lon

HOUSING_TYPES = tuple(v for v, _ in Ad.HousingType.choices)

CAPTION_POOL = {
    "apartment": ["Living room", "Kitchen", "Bedroom"],
    "house": ["Facade", "Backyard", "Dining room"],
    "studio": ["Open space", "Kitchenette", "Bathroom"],
    "loft": ["Loft view", "Mezzanine", "Industrial vibe"],
    "room": ["Room", "Desk", "Wardrobe"],
    "townhouse": ["Front", "Stairs", "Master bedroom"],
    "villa": ["Pool", "Garden", "Terrace"],
}
COLOR_BY_TYPE = {
    "apartment": "lightblue",
    "house": "lightgreen",
    "studio": "khaki",
    "loft": "lightgray",
    "room": "lavender",
    "townhouse": "peachpuff",
    "villa": "lightgoldenrodyellow",
}

# ---------------------------------------------------------------------------

class UserFactory(DjangoModelFactory):
    """
    Demo user. Your CustomUser has no 'username' field, so we only set email & names.
    Password is hashed in @post_generation.
    """
    class Meta:
        model = get_user_model()
        django_get_or_create = ("email",)

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = Faker("first_name")
    last_name = Faker("last_name")

    @post_generation
    def password(self, create, extracted, **kwargs):
        pwd = extracted or "Passw0rd!"
        self.set_password(pwd)
        if create:
            self.save()

class OwnerFactory(UserFactory):
    """Listing owner user."""
    pass

class TenantFactory(UserFactory):
    """Tenant user."""
    pass

# ---------------------------------------------------------------------------

class AdFactory(DjangoModelFactory):
    """Airbnb-like listing with map pin and realistic attributes."""
    class Meta:
        model = Ad

    # service param used across fields (NOT passed to the model)
    class Params:
        city = factory.LazyFunction(rand_city)

    owner = factory.SubFactory(OwnerFactory)

    title = factory.LazyAttribute(
        lambda o: f"{random.choice(['Cozy', 'Sunny', 'Modern', 'Quiet'])} "
                  f"{random.choice(['Studio', 'Apartment', 'Loft', 'Room'])} in {o.city.capitalize()}"
    )
    description = Faker("paragraph", nb_sentences=5)
    location = factory.LazyAttribute(lambda o: f"{o.city.capitalize()}, Germany")

    price = factory.LazyFunction(lambda: Decimal(random.randrange(35, 220)))  # per night
    rooms = factory.LazyFunction(lambda: random.randint(1, 4))
    area = factory.LazyFunction(lambda: random.randint(18, 120))

    housing_type = factory.LazyFunction(lambda: random.choice(HOUSING_TYPES))

    # Map pin consistently within the same city bbox
    latitude = factory.LazyAttribute(lambda o: rand_point_in_city(o.city)[0])
    longitude = factory.LazyAttribute(lambda o: rand_point_in_city(o.city)[1])

    is_active = True
    is_demo = True  # mark seeded ads for easy purge

class AdImageFactory(DjangoModelFactory):
    """Generated placeholder image 1280x720."""
    class Meta:
        model = AdImage

    ad = factory.SubFactory(AdFactory)
    image = ImageField(width=1280, height=720, format="JPEG")
    caption = factory.LazyAttribute(
        lambda o: random.choice(CAPTION_POOL.get(getattr(o.ad, "housing_type", "apartment"), ["Photo"]))
    )

class BookingFactory(DjangoModelFactory):
    """Booking (PENDING by default); use trait `past_confirmed` for reviews."""
    class Meta:
        model = Booking

    ad = factory.SubFactory(AdFactory)
    tenant = factory.SubFactory(TenantFactory)

    @staticmethod
    def _future_window():
        start = timezone.localdate() + timedelta(days=random.randint(5, 20))
        end = start + timedelta(days=random.randint(2, 7))
        return start, end

    date_from = LazyFunction(lambda: BookingFactory._future_window()[0])
    date_to = LazyFunction(lambda: BookingFactory._future_window()[1])

    status = factory.LazyFunction(lambda: getattr(Booking, "PENDING", "PENDING"))

    class Params:
        past_confirmed = factory.Trait(
            status=factory.LazyFunction(lambda: getattr(Booking, "CONFIRMED", "CONFIRMED")),
            date_to=LazyFunction(lambda: timezone.localdate() - timedelta(days=random.randint(5, 20))),
            date_from=LazyFunction(lambda: timezone.localdate() - timedelta(days=random.randint(25, 40))),
        )

class ReviewFactory(DjangoModelFactory):
    """One review per booking."""
    class Meta:
        model = Review

    booking = factory.SubFactory(BookingFactory, past_confirmed=True)
    ad = factory.LazyAttribute(lambda o: o.booking.ad)
    tenant = factory.LazyAttribute(lambda o: o.booking.tenant)

    rating = factory.LazyFunction(lambda: random.randint(4, 5))
    text = Faker("sentence", nb_words=12)
