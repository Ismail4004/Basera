from django import forms

from catalog.models import Region

from . import choices
from .models import GrowProfile


def _choice_field(options, message):
    return forms.ChoiceField(
        choices=[(code, label) for code, label, _ in options],
        widget=forms.RadioSelect,
        error_messages={"required": message, "invalid_choice": message},
    )


class GrowProfileForm(forms.ModelForm):
    """US-06: describe one growing space.

    The region list comes from the Region table; every other answer is one of the
    fixed choices in choices.py. The user is never a form field: the view sets it
    from the logged-in account, so a profile can only be saved for yourself.
    """

    name = forms.CharField(
        max_length=100,
        error_messages={"required": "Please give this profile a name."},
    )
    region = forms.ModelChoiceField(
        queryset=Region.objects.all(),
        empty_label="Select your region",
        error_messages={"required": "Please choose a region.", "invalid_choice": "Please choose a region."},
    )
    space_type = _choice_field(choices.SPACE_TYPES, "Please choose indoor or outdoor.")
    sunlight = _choice_field(choices.SUNLIGHT, "Please choose how much sun your space gets.")
    soil_type = _choice_field(choices.SOILS, "Please choose your soil.")
    water_availability = _choice_field(choices.WATER, "Please choose how much water you can provide.")
    purpose = _choice_field(choices.PURPOSES, "Please choose what you want the plants to do.")

    class Meta:
        model = GrowProfile
        fields = ["name", "region", "space_type", "sunlight", "soil_type", "water_availability", "purpose"]

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def cards(self, field_name, options):
        """The options for one radio group, with the current answer ticked.

        The template draws these as big selectable cards (label plus hint), so it
        needs more than Django's default radio widget gives.
        """
        current = self[field_name].value()
        return [
            {"code": code, "label": label, "hint": hint, "checked": code == current,
             "id": f"id_{field_name}_{code}"}
            for code, label, hint in options
        ]

    def groups(self):
        """All five radio groups, in page order, for the template."""
        spec = [
            ("space_type", "Space type", choices.SPACE_TYPES, 2),
            ("sunlight", "Sunlight", choices.SUNLIGHT, 3),
            ("soil_type", "Soil", choices.SOILS, 4),
            ("water_availability", "Water you can provide", choices.WATER, 3),
            ("purpose", "What do you want the plants to do?", choices.PURPOSES, 3),
        ]
        return [
            {"name": name, "title": title, "cols": cols, "options": self.cards(name, options),
             "errors": self[name].errors}
            for name, title, options, cols in spec
        ]
