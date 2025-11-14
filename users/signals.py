from django.db.models.signals import pre_save
from django.dispatch import receiver
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
from .models import Profile
import sys

@receiver(pre_save, sender=Profile)
def optimize_profile_image(sender, instance, **kwargs):
    '''
    Automatically optimize profile images before saving.
    Resize large images and reduce quality for web.
    '''
    if not instance.profile_image:
        return

    try:
        img = Image.open(instance.profile_image)

        # Convert to RGB if necessary
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        # Resize if too large
        max_size = (800, 800)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.LANCZOS)

        # Save optimized image
        output = BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)

        instance.profile_image = InMemoryUploadedFile(
            output,
            'ImageField',
            f"{instance.profile_image.name.split('.')[0]}.jpg",
            'image/jpeg',
            sys.getsizeof(output),
            None
        )

    except Exception as e:
        # Log error but don't prevent save
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error optimizing profile image: {str(e)}")