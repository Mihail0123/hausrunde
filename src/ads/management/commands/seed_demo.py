from __future__ import annotations

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

# Import from the project package (settings use 'src.settings')
from src.ads.models import Ad, AdImage, Booking, Review
from src.ads.factories import (
    OwnerFactory,
    TenantFactory,
    AdFactory,
    AdImageFactory,
    BookingFactory,
    ReviewFactory,
)


class Command(BaseCommand):
    """
    Seed the database with realistic demo data:
    - Owners and tenants (password: Passw0rd!)
    - Ads distributed across major German cities with map pins (latitude/longitude)
    - 2–3 photos per ad (generated placeholders)
    - One past CONFIRMED booking per ad (for reviews)
    - Several future PENDING bookings per ad with small overlaps
    - Optional reviews for ~60% of past bookings

    All seeded ads are marked with is_demo=True so they can be wiped easily.
    """

    help = "Seed the DB with realistic demo data (DE cities, pins, photos, bookings, reviews)."

    def add_arguments(self, parser):
        # Randomness & wiping
        parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility.")
        parser.add_argument("--wipe-demo", action="store_true", help="Delete only demo ads (is_demo=True) before seeding.")
        parser.add_argument("--wipe-all", action="store_true", help="Delete ALL ads/images/bookings/reviews before seeding.")
        # Sizes
        parser.add_argument("--owners", type=int, default=4, help="How many owners to create.")
        parser.add_argument("--tenants", type=int, default=8, help="How many tenants to create.")
        parser.add_argument("--ads", type=int, default=100, help="How many ads to create.")
        parser.add_argument("--images-min", type=int, default=2, help="Min images per ad.")
        parser.add_argument("--images-max", type=int, default=3, help="Max images per ad.")
        parser.add_argument("--overlaps", type=int, default=2, help="How many future overlapping PENDING bookings per ad.")
        parser.add_argument("--with-reviews", action="store_true", help="Create reviews for part of past bookings.")

    @transaction.atomic
    def handle(self, *args, **opts):
        seed = opts.get("seed")
        if seed is not None:
            random.seed(seed)

        # --- Wipe phase -------------------------------------------------------
        if opts["wipe_all"]:
            self.stdout.write(self.style.WARNING("Wiping ALL ads/images/bookings/reviews..."))
            # Delete in dependency order to avoid surprises
            Review.objects.all().delete()
            Booking.objects.all().delete()
            AdImage.objects.all().delete()
            Ad.objects.all().delete()
        elif opts["wipe_demo"]:
            self.stdout.write(self.style.WARNING("Wiping DEMO ads (is_demo=True)..."))
            # FK cascade will remove images/bookings/reviews
            Ad.objects.filter(is_demo=True).delete()

        owners_n = opts["owners"]
        tenants_n = opts["tenants"]
        ads_n = opts["ads"]
        img_min = opts["images_min"]
        img_max = opts["images_max"]
        overlaps = opts["overlaps"]
        with_reviews = opts["with_reviews"]

        # --- Users ------------------------------------------------------------
        owners = [OwnerFactory(password="Passw0rd!") for _ in range(owners_n)]
        tenants = [TenantFactory(password="Passw0rd!") for _ in range(tenants_n)]
        self.stdout.write(
            self.style.SUCCESS(
                f"Users created: owners={owners_n}, tenants={tenants_n} (password: Passw0rd!)"
            )
        )

        # --- Ads + images -----------------------------------------------------
        ads: list[Ad] = []
        for i in range(ads_n):
            # Round-robin assign owners
            ad = AdFactory(owner=owners[i % owners_n])
            ads.append(ad)

        for ad in ads:
            for _ in range(random.randint(img_min, img_max)):
                AdImageFactory(ad=ad)

        # --- Bookings (past confirmed + future PENDING overlaps) -------------
        today = timezone.localdate()
        for ad in ads:
            # Past confirmed booking (for potential reviews)
            t = random.choice(tenants)
            past_from = today - timedelta(days=random.randint(35, 50))
            past_to = past_from + timedelta(days=random.randint(2, 7))
            BookingFactory(
                ad=ad,
                tenant=t,
                date_from=past_from,
                date_to=past_to,
                status=Booking.CONFIRMED,
            )

            # Future overlapping pending bookings
            base_start = today + timedelta(days=random.randint(10, 20))
            base_end = base_start + timedelta(days=random.randint(3, 7))
            for _ in range(overlaps):
                shift = random.randint(-1, 1)  # small overlap shift
                start = base_start + timedelta(days=shift)
                end = base_end + timedelta(days=shift)
                t2 = random.choice(tenants)
                # Ensure the tenant is not the ad owner
                if t2.id == ad.owner_id:
                    t2 = random.choice([u for u in tenants if u.id != ad.owner_id])
                BookingFactory(
                    ad=ad,
                    tenant=t2,
                    date_from=start,
                    date_to=end,
                    status=Booking.PENDING,
                )

        # --- Optional reviews for ~60% of finished bookings -------------------
        if with_reviews:
            finished = list(
                Booking.objects.filter(status=Booking.CONFIRMED, date_to__lt=today)
            )
            random.shuffle(finished)
            target = finished[: int(len(finished) * 0.6)]
            for b in target:
                if Review.objects.filter(booking=b).exists():
                    continue
                ReviewFactory(booking=b)

        self.stdout.write(self.style.SUCCESS(f"Seeding done: ads={len(ads)}"))