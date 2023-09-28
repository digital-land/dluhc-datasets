from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, URLField
from wtforms.validators import DataRequired, ValidationError


# change to a regex validator
def curie_check(form, field):
    if len(field.data.split(":")) != 2:
        raise ValidationError(
            f"{field.name} is a curie and should be in the format 'namespace:identifier'"
        )


class FormBuilder:
    field_types = {
        "curie": StringField,
        "string": StringField,
        "text": TextAreaField,
        "url": URLField,
    }

    def build(self):
        class TheForm(FlaskForm):
            pass

        for field in self.fields:
            form_field = self.field_types.get(field.datatype)
            if form_field is not None:
                if field.datatype == "curie":
                    setattr(TheForm, field.field, form_field(validators=[curie_check]))
                else:
                    setattr(TheForm, field.field, form_field())

        if self.include_edit_notes:
            setattr(TheForm, "edit_notes", TextAreaField(validators=[DataRequired()]))

        return TheForm()

    def form_fields(self):
        return sorted(self.fields)

    def __init__(self, fields, include_edit_notes=False):
        skip_fields = {"entity", "end-date", "start-date", "entry-date", "prefix"}
        self.fields = []
        self.include_edit_notes = include_edit_notes
        for field in fields:
            if field.field not in skip_fields:
                self.fields.append(field)
