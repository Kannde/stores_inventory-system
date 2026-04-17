from django import forms
from django.contrib.auth import get_user_model

from .models import Store, StoreStaff


User = get_user_model()


class AdminStoreForm(forms.ModelForm):
    owner = forms.ModelChoiceField(
        queryset=User.objects.filter(is_superuser=False).order_by('username'),
        required=False,
        empty_label='— No owner —',
    )

    class Meta:
        model = Store
        fields = ['name', 'phone', 'location', 'description', 'logo', 'currency_symbol', 'is_active', 'owner']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class OwnerForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text='Leave blank to keep current password.',
    )
    store = forms.ModelChoiceField(
        queryset=Store.objects.all().order_by('name'),
        required=False,
        empty_label='— No store assigned —',
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['password'].required = True
            self.fields['password'].help_text = ''
        if self.instance.pk:
            try:
                self.fields['store'].initial = self.instance.owned_store
            except Exception:
                pass

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
            new_store = self.cleaned_data.get('store')
            try:
                current_store = user.owned_store
            except Exception:
                current_store = None
            if new_store != current_store:
                if current_store:
                    Store.objects.filter(pk=current_store.pk).update(owner=None)
                if new_store:
                    Store.objects.filter(pk=new_store.pk).update(owner=user)
        return user


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)


class StoreSettingsForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'phone', 'location', 'description', 'logo', 'currency_symbol']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class StaffForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        required=False,
        help_text='Optional username for staff login.',
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='Leave blank to keep the current password.',
    )

    class Meta:
        model = StoreStaff
        fields = ['name', 'phone', 'role', 'pin', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].widget.attrs['autocomplete'] = 'new-password'
        user = getattr(self.instance, 'user', None)
        if user:
            self.fields['username'].initial = user.username

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if not username:
            return ''

        qs = User.objects.filter(username__iexact=username)
        if self.instance.user_id:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError('That username is already in use.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username', '').strip()
        password = cleaned_data.get('password')
        if username and not self.instance.user_id and not password:
            self.add_error('password', 'Set a password when creating a new login.')
        return cleaned_data

    def save(self, store, commit=True):
        staff_member = super().save(commit=False)
        staff_member.store = store

        username = self.cleaned_data.get('username', '').strip()
        password = self.cleaned_data.get('password')

        if username:
            user = staff_member.user or User(username=username)
            user.username = username
            user.first_name = self.cleaned_data['name']
            user.is_active = self.cleaned_data['is_active']
            if password:
                user.set_password(password)
            if commit:
                user.save()
            staff_member.user = user
        elif staff_member.user_id:
            user = staff_member.user
            user.first_name = self.cleaned_data['name']
            user.is_active = self.cleaned_data['is_active']
            if password:
                user.set_password(password)
            if commit:
                user.save()

        if commit:
            staff_member.save()
        return staff_member
