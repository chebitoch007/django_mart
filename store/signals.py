from django.db.models.signals import post_migrate
from django.dispatch import receiver
from store.models import Category
from django.utils.text import slugify


@receiver(post_migrate)
def create_initial_categories(sender, **kwargs):
    if sender.name == 'store':
        CATEGORIES = [
            "🎮 Game Controllers & Input Devices",
            "🖥️ Display & Visual Enhancements",
            "🕹️ Console Accessories",
            "🧩 PC Gaming Accessories",
            "🎧 Audio & Communication",
            "🪑 Furniture & Ergonomics",
            "🔌 Power & Charging",
            "🧳 Storage & Travel",
            "🧼 Maintenance & Protection",
            "📸 Streaming & Content Creation",
            "🎲 Retro & Niche Accessories",
            "🌐 Network & Online Gaming",
            "🧠 VR / AR Accessories",
            "📱 Mobile & Cloud Gaming",
            "💎 Merchandise & Collectibles",
        ]

        for category_name in CATEGORIES:
            Category.objects.get_or_create(
                name=category_name,
                defaults={
                    'slug': slugify(category_name),
                    'is_active': True
                }
            )
        # Rebuild MPTT tree
        Category.objects.rebuild()