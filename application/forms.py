from wtforms import DateField, Field, IntegerField, StringField, URLField
from wtforms.form import Form
from wtforms.validators import ValidationError
from wtforms.widgets import TextInput


def curie_check(form, field):
    if len(field.data.split(":")) != 2:
        raise ValidationError("curie should be in the format {namespace}:{identifier}")


class CurieField(Field):
    widget = TextInput()

    def __init__(self, **kwargs):
        super(CurieField, self).__init__(validators=[curie_check], **kwargs)


class FormBuilder:
    field_types = {
        "curie": CurieField,
        "datetime": DateField,
        "integer": IntegerField,
        "string": StringField,
        "text": StringField,
        "url": URLField,
    }

    def with_field(self, name, datatype):
        field = FormBuilder.field_types.get(datatype)
        self.fields.append((name.lower(), field))

    def build(self):
        class TheForm(Form):
            pass

        for name, field in self.fields:
            setattr(TheForm, name, field())

        self.fields = []
        return TheForm()

    def __init__(self):
        self.fields = []
