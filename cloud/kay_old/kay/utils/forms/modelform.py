#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Support for creating Kay forms from Datastore data models.

Taken from google.appengine.ext.db.djangoforms

Terminology notes:
  - forms: always refers to the Kay newforms subpackage
  - field: always refers to a Kay forms.Field instance
  - property: always refers to a db.Property instance

Mapping between properties and fields:

+====================+===================+==============+====================+
| Property subclass  | Field subclass    | datatype     | widget; notes      |
+====================+===================+==============+====================+
| StringProperty     | TextField         | unicode      | Textarea           |
|                    |                   |              | if multiline       |
+--------------------+-------------------+--------------+--------------------+
| TextProperty       | TextField         | unicode      | Textarea           |
+--------------------+-------------------+--------------+--------------------+
| BlobProperty       | FileField         | str          | skipped in v0.96   |
+--------------------+-------------------+--------------+--------------------+
| DateTimeProperty   | DateTimeField     | datetime     | skipped            |
|                    |                   |              | if auto_now[_add]  |
+--------------------+-------------------+--------------+--------------------+
| DateProperty       | DateField         | date         | ditto              |
+--------------------+-------------------+--------------+--------------------+
| TimeProperty       | TimeField         | time         | ditto              |
+--------------------+-------------------+--------------+--------------------+
| IntegerProperty    | IntegerField      | int or long  |                    |
+--------------------+-------------------+--------------+--------------------+
| FloatProperty      | FloatField        | float        | CharField in v0.96 |
+--------------------+-------------------+--------------+--------------------+
| BooleanProperty    | BooleanField      | bool         |                    |
+--------------------+-------------------+--------------+--------------------+
| UserProperty       | TextField         | users.User   |                    |
+--------------------+-------------------+--------------+--------------------+
| StringListProperty | TextField         | list of str  | Textarea           |
+--------------------+-------------------+--------------+--------------------+
| LinkProperty       | TextField         | str          |                    |
+--------------------+-------------------+--------------+--------------------+
| ReferenceProperty  | ModelField*       | db.Model     |                    |
+--------------------+-------------------+--------------+--------------------+
| _ReverseReferenceP.| None              | <iterable>   | always skipped     |
+====================+===================+==============+====================+

"""



import itertools
import logging


from google.appengine.api import users
from google.appengine.ext import db

from kay import exceptions
from kay.utils import forms
from kay.utils import datastructures
from kay.i18n import lazy_gettext as _
from kay.exceptions import ImproperlyConfigured
from kay.models import NamedModel

def monkey_patch(name, bases, namespace):
  """A 'metaclass' for adding new methods to an existing class.

  In this version, existing methods can't be overridden; this is by
  design, to avoid accidents.

  Usage example:

    class PatchClass(TargetClass):
      __metaclass__ = monkey_patch
      def foo(self, ...): ...
      def bar(self, ...): ...

  This is equivalent to:

    def foo(self, ...): ...
    def bar(self, ...): ...
    TargetClass.foo = foo
    TargetClass.bar = bar
    PatchClass = TargetClass

  Note that PatchClass becomes an alias for TargetClass; by convention
  it is recommended to give PatchClass the same name as TargetClass.
  """

  assert len(bases) == 1, 'Exactly one base class is required'
  base = bases[0]
  for name, value in namespace.iteritems():
    if name not in ('__metaclass__', '__module__'):
      assert name not in base.__dict__, "Won't override attribute %r" % (name,)
      setattr(base, name, value)
  return base




class Property(db.Property):
  __metaclass__ = monkey_patch

  def get_form_field(self, form_class=forms.TextField, **kwargs):
    """Return a Django form field appropriate for this property.

    Args:
      form_class: a forms.Field subclass, default forms.CharField

    Additional keyword arguments are passed to the form_class constructor,
    with certain defaults:
      required: self.required
      label: prettified self.verbose_name, if not None
      widget: a forms.Select instance if self.choices is non-empty
      initial: self.default, if not None

    Returns:
       A fully configured instance of form_class, or None if no form
       field should be generated for this property.
    """
    defaults = {'required': self.required}
    if self.verbose_name is None:
      defaults['label'] = self.name.capitalize().replace('_', ' ')
    else:
      defaults['label'] = self.verbose_name
    if self.choices:
      choices = []
      if not self.required or (self.default is None and
                               'initial' not in kwargs):
        choices.append(('', '---------'))
      for choice in self.choices:
        choices.append((str(choice), unicode(choice)))
      defaults['choices'] = choices
      form_class = forms.ChoiceField
    if self.default is not None:
      defaults['default'] = self.default
    defaults.update(kwargs)
    return form_class(**defaults)

  def get_value_for_form(self, instance):
    """Extract the property value from the instance for use in a form.

    Override this to do a property- or field-specific type conversion.

    Args:
      instance: a db.Model instance

    Returns:
      The property's value extracted from the instance, possibly
      converted to a type suitable for a form field; possibly None.

    By default this returns the instance attribute's value unchanged.
    """
    return getattr(instance, self.name)

  def make_value_from_form(self, value):
    """Convert a form value to a property value.

    Override this to do a property- or field-specific type conversion.

    Args:
      value: the cleaned value retrieved from the form field

    Returns:
      A value suitable for assignment to a model instance's property;
      possibly None.

    By default this converts the value to self.data_type if it
    isn't already an instance of that type, except if the value is
    empty, in which case we return None.
    """
    if value in (None, ''):
      return None
    if not isinstance(value, self.data_type):
      value = self.data_type(value)
    return value


class UserProperty(db.Property):
  """This class exists solely to log a warning when it is used."""

  def __init__(self, *args, **kwds):
    logging.warn("Please don't use modelforms.UserProperty; "
                 "use db.UserProperty instead.")
    super(UserProperty, self).__init__(*args, **kwds)

class EmailProperty(db.EmailProperty):
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    defaults = {'form_class': forms.EmailField}
    defaults.update(kwargs)
    return super(EmailProperty, self).get_form_field(**defaults)

class StringProperty(db.StringProperty):
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for a string property.

    This sets the widget default to forms.Textarea if the property's
    multiline attribute is set.
    """
    defaults = {}
    if self.multiline:
      defaults['widget'] = forms.Textarea
    defaults.update(kwargs)
    return super(StringProperty, self).get_form_field(**defaults)


class TextProperty(db.TextProperty):
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for a text property.

    This sets the widget default to forms.Textarea.
    """
    defaults = {'widget': forms.Textarea}
    defaults.update(kwargs)
    return super(TextProperty, self).get_form_field(**defaults)


class BlobProperty(db.BlobProperty):
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for a blob property.

    """
    if not hasattr(forms, 'FileField'):
      return None
    defaults = {'form_class': forms.FileField}
    defaults.update(kwargs)
    return super(BlobProperty, self).get_form_field(**defaults)

  def get_value_for_form(self, instance):
    """Extract the property value from the instance for use in a form.

    There is no way to convert a Blob into an initial value for a file
    upload, so we always return None.
    """
    return None

  def make_value_from_form(self, value):
    """Convert a form value to a property value.

    This extracts the content from the UploadedFile instance returned
    by the FileField instance.
    """
    if value.__class__.__name__ == 'UploadedFile':
      return db.Blob(value.content)
    return super(BlobProperty, self).make_value_from_form(value)


class DateTimeProperty(db.DateTimeProperty):
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for a date-time property.

    This defaults to a DateTimeField instance, except if auto_now or
    auto_now_add is set, in which case None is returned, as such
    'auto' fields should not be rendered as part of the form.
    """
    if self.auto_now or self.auto_now_add:
      return None
    defaults = {'form_class': forms.DateTimeField}
    defaults.update(kwargs)
    return super(DateTimeProperty, self).get_form_field(**defaults)


class DateProperty(db.DateProperty):
  # TODO: 
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for a date property.

    This defaults to a DateField instance, except if auto_now or
    auto_now_add is set, in which case None is returned, as such
    'auto' fields should not be rendered as part of the form.
    """
    if self.auto_now or self.auto_now_add:
      return None
    defaults = {'form_class': forms.DateField}
    defaults.update(kwargs)
    return super(DateProperty, self).get_form_field(**defaults)


class TimeProperty(db.TimeProperty):
  # TODO: 
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for a time property.

    This defaults to a TimeField instance, except if auto_now or
    auto_now_add is set, in which case None is returned, as such
    'auto' fields should not be rendered as part of the form.
    """
    if self.auto_now or self.auto_now_add:
      return None
    defaults = {'form_class': forms.TimeField}
    defaults.update(kwargs)
    return super(TimeProperty, self).get_form_field(**defaults)


class IntegerProperty(db.IntegerProperty):
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for an integer property.

    This defaults to an IntegerField instance.
    """
    defaults = {'form_class': forms.IntegerField}
    defaults.update(kwargs)
    return super(IntegerProperty, self).get_form_field(**defaults)


class FloatProperty(db.FloatProperty):
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for an integer property.

    This defaults to a FloatField instance when using Django 0.97 or
    later.  For 0.96 this defaults to the CharField class.
    """
    defaults = {}
    if hasattr(forms, 'FloatField'):
      defaults['form_class'] = forms.FloatField
    defaults.update(kwargs)
    return super(FloatProperty, self).get_form_field(**defaults)


class BooleanProperty(db.BooleanProperty):
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for a boolean property.

    This defaults to a BooleanField.
    """
    defaults = {'form_class': forms.BooleanField}
    defaults.update(kwargs)
    return super(BooleanProperty, self).get_form_field(**defaults)

  def make_value_from_form(self, value):
    """Convert a form value to a property value.

    This is needed to ensure that False is not replaced with None.
    """
    if value is None:
      return None
    if isinstance(value, basestring) and value.lower() == 'false':
      return False
    return bool(value)


class StringListPropertySeparatedWithComma(db.StringListProperty):
  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for a StringList property.

    This defaults to a Textarea widget with a blank initial value.
    """
    defaults = {'field': forms.TextField(), 'form_class': forms.CommaSeparated,
                'min_size': 0}
    defaults.update(kwargs)
    return super(StringListProperty, self).get_form_field(**defaults)

  def get_value_for_form(self, instance):
    """Extract the property value from the instance for use in a form.

    This joins a list of strings with newlines.
    """
    value = super(StringListProperty, self).get_value_for_form(instance)
    if not value:
      return None
    if isinstance(value, list):
      value = ','.join(value)
    return value

  def make_value_from_form(self, value):
    """Convert a form value to a property value.

    This breaks the string into lines.
    """
    if not value:
      return []
    if isinstance(value, basestring):
      value = value.split(",")
    return value
  
  

class StringListProperty(db.StringListProperty):
  __metaclass__ = monkey_patch


  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for a StringList property.

    This defaults to a Textarea widget with a blank initial value.
    """
    defaults = {'field': forms.TextField(), 'form_class': forms.LineSeparated,
                'min_size': 0}
    defaults.update(kwargs)
    return super(StringListProperty, self).get_form_field(**defaults)

  def get_value_for_form(self, instance):
    """Extract the property value from the instance for use in a form.

    This joins a list of strings with newlines.
    """
    value = super(StringListProperty, self).get_value_for_form(instance)
    if not value:
      return None
    if isinstance(value, list):
      value = '\n'.join(value)
    return value

  def make_value_from_form(self, value):
    """Convert a form value to a property value.

    This breaks the string into lines.
    """
    if not value:
      return []
    if isinstance(value, basestring):
      value = value.splitlines()
    return value


class LinkProperty(db.LinkProperty):
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for a URL property.

    This defaults to a URLField instance.
    """
    defaults = {'form_class': forms.TextField}
    defaults.update(kwargs)
    return super(LinkProperty, self).get_form_field(**defaults)


class _WrapIter(object):
  """Helper class whose iter() calls a given function to get an iterator."""

  def __init__(self, function):
    self._function = function

  def __iter__(self):
    return self._function()


class ReferenceProperty(db.ReferenceProperty):
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for a reference property.

    This defaults to a ModelChoiceField instance.
    """
    defaults = {'form_class': forms.ModelField,
                'model': self.reference_class}
    defaults.update(kwargs)
    return super(ReferenceProperty, self).get_form_field(**defaults)

  def get_value_for_form(self, instance):
    """Extract the property value from the instance for use in a form.

    This return the key object for the referenced object, or None.
    """
    value = super(ReferenceProperty, self).get_value_for_form(instance)
    if value is not None:
      value = value.key()
    return value

  def make_value_from_form(self, value):
    """Convert a form value to a property value.

    This turns a key string or object into a model instance.
    """
    if value:
      if not isinstance(value, db.Model):
        value = db.get(value)
    return value


class _ReverseReferenceProperty(db._ReverseReferenceProperty):
  __metaclass__ = monkey_patch

  def get_form_field(self, **kwargs):
    """Return a Django form field appropriate for a reverse reference.

    This always returns None, since reverse references are always
    automatic.
    """
    return None


def property_clean(prop, value):
  """Apply Property level validation to value.

  Calls .make_value_from_form() and .validate() on the property and catches
  exceptions generated by either.  The exceptions are converted to
  forms.ValidationError exceptions.

  Args:
    prop: The property to validate against.
    value: The value to validate.

  Raises:
    forms.ValidationError if the value cannot be validated.
  """
  if value is not None:
    try:
      prop.validate(prop.make_value_from_form(value))
    except (db.BadValueError, ValueError), e:
      raise forms.ValidationError(unicode(e))


class ModelFormOptions(object):
  """A simple class to hold internal options for a ModelForm class.

  Instance attributes:
    model: a db.Model class, or None
    fields: list of field names to be defined, or None
    exclude: list of field names to be skipped, or None

  These instance attributes are copied from the 'Meta' class that is
  usually present in a ModelForm class, and all default to None.
  """


  def __init__(self, options=None):
    self.model = getattr(options, 'model', None)
    self.fields = getattr(options, 'fields', None)
    self.exclude = getattr(options, 'exclude', None)
    self.help_texts = getattr(options, 'help_texts', {})

class ModelFormMetaclass(forms.FormMeta):
  """The metaclass for the ModelForm class defined below.

  See the docs for ModelForm below for a usage example.
  """
  bad_attr_names = ('data', 'errors', 'raw_data')
  def __new__(cls, class_name, bases, attrs):
    """Constructor for a new ModelForm class instance.

    The signature of this method is determined by Python internals.

    """
    fields = sorted(((field_name, attrs.pop(field_name))
                     for field_name, obj in attrs.items()
                     if isinstance(obj, forms.Field)),
                    key=lambda obj: obj[1].creation_counter)
    for base in bases[::-1]:
      if hasattr(base, '_base_fields'):
        fields = base._base_fields.items() + fields
    declared_fields = datastructures.OrderedDict()
    for field_name, obj in fields:
      declared_fields[field_name] = obj
    opts = ModelFormOptions(attrs.get('Meta', None))
    attrs['_meta'] = opts

    base_models = []
    for base in bases:
      base_opts = getattr(base, '_meta', None)
      base_model = getattr(base_opts, 'model', None)
      if base_model is not None:
        base_models.append(base_model)
    if len(base_models) > 1:
      raise exceptions.ImproperlyConfigured(
          "%s's base classes define more than one model." % class_name)

    if opts.model is not None:
      if base_models and base_models[0] is not opts.model:
        raise exceptions.ImproperlyConfigured(
            '%s defines a different model than its parent.' % class_name)

      model_fields = datastructures.OrderedDict()
      for name, prop in sorted(opts.model.properties().iteritems(),
                               key=lambda prop: prop[1].creation_counter):
        if opts.fields and name not in opts.fields:
          continue
        if opts.exclude and name in opts.exclude:
          continue
        form_field = prop.get_form_field(
          help_text=opts.help_texts.get(name, None))
        if form_field is not None:
          model_fields[name] = form_field

      for bad_attr_name in ModelFormMetaclass.bad_attr_names:
        if model_fields.has_key(bad_attr_name):
          raise ImproperlyConfigured("When you use ModelForm, you can not"
                                     " use these names as field names: %s"
                                     % str(ModelFormMetaclass.bad_attr_names))
      model_fields.update(declared_fields)
      attrs['_base_fields'] = model_fields

      props = opts.model.properties()
      for name, field in model_fields.iteritems():
        prop = props.get(name)
        if prop:
          def check_for_property_field(form, value, prop=prop):
            property_clean(prop, value)
            return True
          field.validators.append(check_for_property_field)
    else:
      attrs['_base_fields'] = declared_fields
    # corresponds with form not rendered
    # maybe i should handle this in forms.FormMeta
    return super(ModelFormMetaclass, cls).__new__(cls,
                                                  class_name, bases, attrs)


class BaseModelForm(forms.Form):
  """Base class for ModelForm.

  This overrides the forms.BaseForm constructor and adds a save() method.

  This class does not have a special metaclass; the magic metaclass is
  added by the subclass ModelForm.
  """

  def __init__(self, instance=None, initial=None, **kwargs):
    """Constructor.

    Args (all optional and defaulting to None):
      data: dict of data values, typically from a POST request)
      initial: dict of initial values
      instance: Model instance to be used for additional initial values

    Except for initial and instance, these arguments are passed on to
    the forms.BaseForm constructor unchanged, but only if not None.
    Leave these blank (i.e. None)
    """
    opts = self._meta
    self.instance = instance
    object_data = {}
    if instance is not None:
      for name, prop in instance.properties().iteritems():
        if opts.fields and name not in opts.fields:
          continue
        if opts.exclude and name in opts.exclude:
          continue
        object_data[name] = prop.get_value_for_form(instance)
    if initial is not None:
      object_data.update(initial)
    kwargs['initial'] = object_data
    kwargs = dict((name, value)
                  for name, value in kwargs.iteritems()
                  if value is not None)
    super(BaseModelForm, self).__init__(**kwargs)

  def save(self, commit=True, **kwargs):
    """Save this form's cleaned data into a model instance.

    Args:
      commit: optional bool, default True; if true, the model instance
        is also saved to the datastore.

    Returns:
      A model instance.  If a model instance was already associated
      with this form instance (either passed to the constructor with
      instance=...  or by a previous save() call), that same instance
      is updated and returned; if no instance was associated yet, one
      is created by this call.

    Raises:
      ValueError if the data couldn't be validated.
    """
    if not self.is_valid:
      raise ValueError('Cannot save a non valid form')
    opts = self._meta
    instance = self.instance
    if instance is None:
      fail_message = 'created'
    else:
      fail_message = 'updated'
    if self.errors:
      raise ValueError("The %s could not be %s because the data didn't "
                       'validate.' % (opts.model.kind(), fail_message))
    cleaned_data = self.data
    converted_data = {}
    propiter = itertools.chain(
      opts.model.properties().iteritems(),
      iter([('key_name', StringProperty(name='key_name'))])
      )
    for name, prop in propiter:
      value = cleaned_data.get(name)
      if value is not None:
        converted_data[name] = prop.make_value_from_form(value)
    try:
      converted_data.update(kwargs)
      if instance is None:
        if issubclass(opts.model, NamedModel):
          logging.debug("commit argument ignored.")
          instance = opts.model.create_new_entity(**converted_data)
        else:
          instance = opts.model(**converted_data)
        self.instance = instance
      else:
        for name, value in converted_data.iteritems():
          if name == 'key_name':
            continue
          setattr(instance, name, value)
    except db.BadValueError, err:
      raise ValueError('The %s could not be %s (%s)' %
                       (opts.model.kind(), fail_message, err))
    if commit:
      instance.put()
    return instance


class ModelForm(BaseModelForm):
  """A Django form tied to a Datastore model.

  Note that this particular class just sets the metaclass; all other
  functionality is defined in the base class, BaseModelForm, above.

  Usage example:

    from google.appengine.ext import db
    from google.appengine.ext.db import djangoforms

    # First, define a model class
    class MyModel(db.Model):
      foo = db.StringProperty()
      bar = db.IntegerProperty(required=True, default=42)

    # Now define a form class
    class MyForm(djangoforms.ModelForm):
      class Meta:
        model = MyModel

  You can now instantiate MyForm without arguments to create an
  unbound form, or with data from a POST request to create a bound
  form.  You can also pass a model instance with the instance=...
  keyword argument to create an unbound (!) form whose initial values
  are taken from the instance.  For bound forms, use the save() method
  to return a model instance.

  Like Django's own corresponding ModelForm class, the nested Meta
  class can have two other attributes:

    fields: if present and non-empty, a list of field names to be
            included in the form; properties not listed here are
            excluded from the form

    exclude: if present and non-empty, a list of field names to be
             excluded from the form

  If exclude and fields are both non-empty, names occurring in both
  are excluded (i.e. exclude wins).  By default all property in the
  model have a corresponding form field defined.

  It is also possible to define form fields explicitly.  This gives
  more control over the widget used, constraints, initial value, and
  so on.  Such form fields are not affected by the nested Meta class's
  fields and exclude attributes.

  If you define a form field named 'key_name' it will be treated
  specially and will be used as the value for the key_name parameter
  to the Model constructor. This allows you to create instances with
  named keys. The 'key_name' field will be ignored when updating an
  instance (although it will still be shown on the form).
  """

  __metaclass__ = ModelFormMetaclass
