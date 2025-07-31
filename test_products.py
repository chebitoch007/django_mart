import os
import django
from django.core.files import File
from django.utils.text import slugify
from store.models import Category, Product, ProductImage, Review, ProductVariant
from django.contrib.auth import get_user_model
import random
from faker import Faker
import requests

# Initialize Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')
django.setup()

fake = Faker()
User = get_user_model()


def create_categories():
    print("Creating categories...")
    # Get categories from constants
    from store.constants import CATEGORIES

    created_categories = []

    # Create top-level categories
    for top_name, subcategories in CATEGORIES.items():
        top_category, _ = Category.objects.get_or_create(
            name=top_name,
            defaults={
                'slug': slugify(top_name),
                'description': fake.paragraph(),
                'is_active': True
            }
        )
        created_categories.append(top_category)
        print(f"Created top-level category: {top_name}")

        # Create subcategories
        for sub_name in subcategories.keys():
            sub_category, _ = Category.objects.get_or_create(
                name=sub_name,
                parent=top_category,
                defaults={
                    'slug': slugify(sub_name),
                    'description': fake.paragraph(),
                    'is_active': True
                }
            )
            created_categories.append(sub_category)
            print(f"Created subcategory: {sub_name} under {top_name}")

    return created_categories


def download_image(url, filename):
    """Download an image and save it locally"""
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return filename
    except Exception as e:
        print(f"Error downloading image: {e}")
    return None

def create_products(categories):
    print("\nCreating products...")
    products_data = [
        {
            "name": "Wireless Gaming Headset",
            "description": "7.1 surround sound with noise-cancelling microphone",
            "price": 89.99,
            "discount_price": 69.99,
            "stock": 100,
            "category": "Headsets & Audio",  # Under Gaming Accessories
            "image_url": "https://picsum.photos/800/800?random=1"
        },
        {
            "name": "Bluetooth Earbuds",
            "description": "True wireless with 24hr battery life",
            "price": 59.99,
            "stock": 200,
            "category": "Audio & Headphones",  # Under Electronics
            "image_url": "https://picsum.photos/800/800?random=2"
        },
        {
            "name": "Mechanical Gaming Keyboard",
            "description": "RGB backlit with customizable macros",
            "price": 99.99,
            "stock": 50,
            "category": "Controllers & Input Devices",  # Under Gaming Accessories
            "image_url": "https://picsum.photos/800/800?random=3"
        },
        {
            "name": "Smart Fitness Tracker",
            "description": "Heart rate monitor and sleep tracker",
            "price": 49.99,
            "discount_price": 39.99,
            "stock": 150,
            "category": "Wearable Technology",  # Under Electronics
            "image_url": "https://picsum.photos/800/800?random=4"
        },
        {
            "name": "Wireless Charging Pad",
            "description": "Fast charging for all Qi-compatible devices",
            "price": 29.99,
            "stock": 300,
            "category": "Mobile Accessories",  # Under Electronics
            "image_url": "https://picsum.photos/800/800?random=5"
        },
        {
            "name": "4K Action Camera",
            "description": "Waterproof with image stabilization",
            "price": 199.99,
            "stock": 75,
            "category": "Cameras & Photography",  # Under Electronics
            "image_url": "https://picsum.photos/800/800?random=6"
        },
    ]

    created_products = []
    for data in products_data:
        try:
            # Find category by name
            category = Category.objects.get(name=data["category"])

            # Create product
            product = Product.objects.create(
                category=category,
                name=data["name"],
                description=data["description"],
                short_description=fake.sentence(),
                price=data["price"],
                discount_price=data.get("discount_price"),
                stock=data["stock"],
                available=True,
                featured=random.choice([True, False]),
                rating=round(random.uniform(3.5, 5.0), 1),
                review_count=random.randint(5, 100),
                is_dropship=random.choice([True, False]),
                supplier=fake.company(),
                shipping_time=f"{random.randint(5, 15)}-{random.randint(16, 30)} days",
                commission_rate=round(random.uniform(5.0, 20.0), 2),
                package_dimensions=f"{random.randint(5, 20)}x{random.randint(5, 20)}x{random.randint(1, 10)} cm",
                package_weight=round(random.uniform(0.1, 2.0), 2)
            )

            # Download and add main image
            image_path = download_image(data["image_url"], f"product_{product.id}.jpg")
            if image_path:
                with open(image_path, 'rb') as img_file:
                    product.image.save(f"product_{product.id}.jpg", File(img_file), save=True)
                os.remove(image_path)

            # Create additional images
            for i in range(1, 4):
                image_url = f"https://picsum.photos/800/800?random={product.id}{i}"
                image_path = download_image(image_url, f"product_{product.id}_additional_{i}.jpg")
                if image_path:
                    with open(image_path, 'rb') as img_file:
                        product_image = ProductImage.objects.create(
                            product=product,
                            image=File(img_file),
                            color=fake.color_name(),
                            alt_text=f"{data['name']} - Image {i}"
                        )
                    os.remove(image_path)

            # Create variants
            colors = ["Black", "White", "Blue", "Red", "Silver"]
            sizes = ["S", "M", "L", "XL"] if "Clothing" in data["category"] else ["Standard"]

            for color in random.sample(colors, min(3, len(colors))):
                for size in random.sample(sizes, min(2, len(sizes))):
                    ProductVariant.objects.create(
                        product=product,
                        size=size,
                        color=color,
                        price=product.price * random.uniform(0.9, 1.1),
                        quantity=random.randint(5, 50)
                    )

            created_products.append(product)
            print(f"Created product: {data['name']} in {data['category']}")
        except Category.DoesNotExist:
            print(f"Category not found: {data['category']}")
            continue

        return created_products

def create_reviews(products):
    print("\nCreating reviews...")
    # Create test users
    users = []
    for _ in range(10):
        user, created = User.objects.get_or_create(
            username=fake.user_name(),
            defaults={
                'email': fake.email(),
                'first_name': fake.first_name(),
                'last_name': fake.last_name(),
            }
        )
        if created:
            user.set_password('testpassword')
            user.save()
        users.append(user)

    # Create reviews
    for product in products:
        for _ in range(random.randint(5, 15)):
            Review.objects.create(
                product=product,
                user=random.choice(users),
                rating=random.randint(1, 5),
                title=fake.sentence(),
                comment=fake.paragraph(),
                approved=True
            )
        # Update product rating
        product.update_rating()

    print(f"Created reviews for {len(products)} products")


def run():
    # Clear existing test data
    print("Clearing existing test data...")
    Product.objects.all().delete()
    Category.objects.all().delete()

    # Create categories
    categories = create_categories()

    # Create products
    products = create_products(categories)

    # Create reviews
    create_reviews(products)

    print("\nTest data generation complete!")


if __name__ == "__main__":
    run()
