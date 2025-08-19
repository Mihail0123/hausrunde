from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django import forms

from .models import CustomUser


class CustomUserCreationForm(forms.ModelForm):
    """Create user with password1/password2 (hash on save)."""
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = ('email', 'first_name', 'last_name', 'phone_number')

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Passwords do not match')
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class CustomUserChangeForm(forms.ModelForm):
    """Edit user; password shown as hashed (read-only field)."""
    password = ReadOnlyPasswordHashField(
        label='Password',
        help_text=(
            "Raw passwords are not stored, so there is no way to see this user's password. "
            "You can change the password using the “Change password” form."
        ),
    )

    class Meta:
        model = CustomUser
        fields = (
            'email', 'first_name', 'last_name', 'phone_number',
            'password', 'is_active', 'is_staff', 'is_superuser',
            'groups', 'user_permissions',
        )

    def clean_password(self):
        # keep the existing hashed password
        return self.initial.get('password')


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser

    list_display = ('id', 'email', 'first_name', 'last_name', 'phone_number', 'is_staff', 'is_active')
    list_filter  = ('is_staff', 'is_active', 'is_superuser')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-date_joined',) if hasattr(CustomUser, 'date_joined') else ('email',)

    # if date_joined exists
    _date_fields = ('last_login',) + (('date_joined',) if hasattr(CustomUser, 'date_joined') else tuple())

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': _date_fields}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'first_name', 'last_name', 'phone_number',
                'password1', 'password2',
                'is_staff', 'is_active', 'is_superuser', 'groups'
            ),
        }),
    )
    readonly_fields = _date_fields
