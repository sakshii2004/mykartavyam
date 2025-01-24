from django.forms import ModelForm
from django import forms
from .models import Category, Complaint, CustomUser, Badge
import re

class UserProfileForm(forms.ModelForm):
    profile_picture = forms.ImageField(widget=forms.FileInput(attrs={'id': 'id_profile_picture'}))
    class Meta:
        model = CustomUser
        fields = ['name', 'phone_number', 'email', 'about_me', 'profile_picture']
        
    def __init__(self, *args, **kwargs):
        super(UserProfileForm, self).__init__(*args, **kwargs)
        self.fields['phone_number'].widget.attrs.update({'readonly': 'readonly', 'class':'edit-profile-input uneditable'})
        self.fields['name'].widget.attrs.update({'readonly': 'readonly', 'class':'edit-profile-input uneditable'})
        self.fields['email'].widget.attrs.update({'class':'edit-profile-input'})
        self.fields['about_me'].widget.attrs.update({'class':'edit-profile-textarea'})

    def clean_profile_picture(self):
        profile_picture = self.cleaned_data.get('profile_picture')
        if not profile_picture or not hasattr(profile_picture, 'content_type'):
            return profile_picture
        valid_mime_types = ['image/jpeg', 'image/png', 'image/jpg']
        mime_type = profile_picture.content_type
        if mime_type not in valid_mime_types:
            raise forms.ValidationError("Unsupported file type. Please upload a JPG or PNG image.")
        max_file_size = 5 * 1024 * 1024 
        if profile_picture.size > max_file_size:
            raise forms.ValidationError("File size exceeds 5 MB. Please upload a smaller image.")
        return profile_picture

    def clean_about_me(self):
        about_me = self.cleaned_data.get('about_me', '').strip()
        if len(about_me) > 200:
            about_me = about_me[:200]
        return about_me 

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            raise forms.ValidationError("Invalid email address. Please enter a valid email.")
        return email   

class ComplaintForm(ModelForm):
    class Meta:
        model = Complaint
        fields = ['title', 'category', 'landmark', 'description', 'image', 'district', 'state', 'latitude', 'longitude']
        widgets = {
            'description': forms.Textarea(attrs={'class': 'create-complaint-textarea'}),
        }
    
    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        super(ComplaintForm, self).__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(disabled=False)
        # making certain categories uneditable later
        if instance and instance.pk:
            self.fields['title'].disabled = True
            self.fields['category'].disabled = True
            self.fields['description'].disabled = True
            self.fields['image'].disabled = True
            self.fields['latitude'].disabled = True
            self.fields['longitude'].disabled = True

        self.fields['latitude'].widget.attrs.update({'id': 'latitude', 'placeholder': 'latitude'})
        self.fields['longitude'].widget.attrs.update({'id': 'longitude', 'placeholder': 'longitude'})

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if title and len(title) > 80:
            title = title[:75] 
        return title

    def clean_landmark(self):
        landmark = self.cleaned_data.get('landmark')
        if landmark and len(landmark) > 80:
            landmark = landmark[:75]  
        return landmark

    def clean_description(self):
        description = self.cleaned_data.get('description')
        if description and len(description) > 300:
            description = description[:300] 
        return description
    
    def clean_district(self):
        district = self.cleaned_data.get('district')
        if district and len(district) > 20:
            district = district[:20] 
            district = district.title()
        return district


class CategoryForm(ModelForm):
    class Meta:
        model = Category
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(CategoryForm, self).__init__(*args, **kwargs) 
        self.fields['name'].widget.attrs.update({'class': 'category-input',  'placeholder': 'Category Name'})
        self.fields['abbreviation'].widget.attrs.update({'class': 'category-input',  'placeholder': 'Category Abbreviation'})  

    def clean_name(self):
        name = self.cleaned_data.get('name', '')
        return name.strip().upper()

    def clean_abbreviation(self):
        abbreviation = self.cleaned_data.get('abbreviation', '')
        return abbreviation.strip().upper()    


class BadgeForm(ModelForm):
    class Meta:
        model = Badge
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(BadgeForm, self).__init__(*args, **kwargs) 
        self.fields['name'].widget.attrs.update({'class': 'badges-form-input',  'placeholder': 'Badge Name'})
        self.fields['min_complaints'].widget.attrs.update({'class': 'badges-form-input',  'placeholder': 'Minimum Complaints Required'}) 
        self.fields['badge_icon'].widget.attrs.update({'class': 'badges-form-input',  'placeholder': 'Category Abbreviation'})   

