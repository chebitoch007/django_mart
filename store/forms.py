# store/forms.py (file, not directory)
from django import forms
from .models import Review, Product, Category

class CategoryChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        depth = self.get_depth(obj)
        return f"{'—' * depth} {obj.name}"

    def get_depth(self, obj, depth=0):
        if obj.parent:
            return self.get_depth(obj.parent, depth + 1)
        return depth

class ProductForm(forms.ModelForm):
    category = CategoryChoiceField(
        queryset=Category.objects.all().select_related('parent'),
        widget=forms.Select(attrs={'style': 'width: 300px;'})
    )

    class Meta:
        model = Product
        fields = '__all__'


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment']
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
        }