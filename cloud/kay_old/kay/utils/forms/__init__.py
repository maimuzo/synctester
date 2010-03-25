# -*- coding: utf-8 -*-
"""
    kay.utils.forms
    ~~~~~~~~~~~~~~~~

    This module implements a sophisticated form validation and rendering
    system that is based on diva with concepts from django newforms and
    wtforms incorporated.

    It can validate nested structures and works in both ways.  It can also
    handle intelligent backredirects (via :mod:`zine.utils.http`) and supports
    basic CSRF protection.

    For usage informations see :class:`Form`

    :copyright: (c) 2009 by the Zine Team, see AUTHORS for more details.
    :copyright: (c) 2009 by Takashi Matsuo <tmatsuo@candit.jp>
    :license: BSD, see LICENSE for more details.
    This file is originally derived from Zine project.
"""
import re
from datetime import datetime
from unicodedata import normalize
from itertools import chain
from threading import Lock
try:
  from hashlib import sha1
except ImportError:
  from sha import new as sha1

from werkzeug import escape, cached_property, MultiDict
from google.appengine.ext import db

from kay.utils import get_request, url_for
from kay.i18n import _, ngettext, lazy_gettext, parse_datetime, \
     format_system_datetime
#from zine.utils.http import get_redirect_target, _redirect, redirect_to
from kay.utils.crypto import gen_random_identifier
from kay.utils.validators import ValidationError
from kay.utils.datastructures import OrderedDict, missing

CSRF_TOKEN_SEED = "csrf_token_seed"

_last_position_hint = -1
_position_hint_lock = Lock()

class HtmlProxy(object):
  def __getattr__(self, name):
    from kay.conf import settings
    if settings.FORMS_USE_XHTML:
      from werkzeug import xhtml
      return getattr(xhtml, name)
    else:
      from werkzeug import html
      return getattr(html, name)

html = HtmlProxy()

def fill_dict(_dict, **kwargs):
  """A helper to fill the dict passed with the items passed as keyword
  arguments if they are not yet in the dict.  If the dict passed was
  `None` a new dict is created and returned.

  This can be used to prepopulate initial dicts in overriden constructors:

      class MyForm(forms.Form):
          foo = forms.TextField()
          bar = forms.TextField()

          def __init__(self, initial=None):
              forms.Form.__init__(self, forms.fill_dict(initial,
                  foo="nothing",
                  bar="nothing"
              ))
  """
  if _dict is None:
    return kwargs
  for key, value in kwargs.iteritems():
    if key not in _dict:
      _dict[key] = value
  return _dict


def set_fields(obj, data, *fields):
  """Set all the fields on obj with data if changed."""
  for field in fields:
    value = data[field]
    if getattr(obj, field) != value:
      setattr(obj, field, value)


def _next_position_hint():
  """Return the next position hint."""
  global _last_position_hint
  _position_hint_lock.acquire()
  try:
    _last_position_hint += 1
    return _last_position_hint
  finally:
    _position_hint_lock.release()


def _decode(data):
  """Decodes the flat dictionary d into a nested structure.

  >>> _decode({'foo': 'bar'})
  {'foo': 'bar'}
  >>> _decode({'foo.0': 'bar', 'foo.1': 'baz'})
  {'foo': ['bar', 'baz']}
  >>> data = _decode({'foo.bar': '1', 'foo.baz': '2'})
  >>> data == {'foo': {'bar': '1', 'baz': '2'}}
  True

  More complex mappings work too:

  >>> _decode({'foo.bar.0': 'baz', 'foo.bar.1': 'buzz'})
  {'foo': {'bar': ['baz', 'buzz']}}
  >>> _decode({'foo.0.bar': '23', 'foo.1.baz': '42'})
  {'foo': [{'bar': '23'}, {'baz': '42'}]}
  >>> _decode({'foo.0.0': '23', 'foo.0.1': '42'})
  {'foo': [['23', '42']]}
  >>> _decode({'foo': ['23', '42']})
  {'foo': ['23', '42']}

  Missing items in lists are ignored for convenience reasons:

  >>> _decode({'foo.42': 'a', 'foo.82': 'b'})
  {'foo': ['a', 'b']}

  This can be used for help client side DOM processing (inserting and
  deleting rows in dynamic forms).

  It also supports werkzeug's multi dicts:

  >>> _decode(MultiDict({"foo": ['1', '2']}))
  {'foo': ['1', '2']}
  >>> _decode(MultiDict({"foo.0": '1', "foo.1": '2'}))
  {'foo': ['1', '2']}

  Those two submission ways can also be used combined:

  >>> _decode(MultiDict({"foo": ['1'], "foo.0": '2', "foo.1": '3'}))
  {'foo': ['1', '2', '3']}

  This function will never raise exceptions except for argument errors
  but the recovery behavior for invalid form data is undefined.
  """
  list_marker = object()
  value_marker = object()
  if isinstance(data, MultiDict):
    listiter = data.iterlists()
  else:
    listiter = ((k, [v]) for k, v in data.iteritems())

  def _split_key(name):
    result = name.split('.')
    for idx, part in enumerate(result):
      if part.isdigit():
        result[idx] = int(part)
    return result

  def _enter_container(container, key):
    if key not in container:
      return container.setdefault(key, {list_marker: False})
    return container[key]

  def _convert(container):
    if value_marker in container:
      force_list = False
      values = container.pop(value_marker)
      if container.pop(list_marker):
        force_list = True
        values.extend(_convert(x[1]) for x in
                      sorted(container.items()))
      if not force_list and len(values) == 1:
        values = values[0]
      return values
    elif container.pop(list_marker):
      return [_convert(x[1]) for x in sorted(container.items())]
    return dict((k, _convert(v)) for k, v in container.iteritems())

  result = {list_marker: False}
  for key, values in listiter:
    parts = _split_key(key)
    if not parts:
      continue
    container = result
    for part in parts:
      last_container = container
      container = _enter_container(container, part)
      last_container[list_marker] = isinstance(part, (int, long))
    container[value_marker] = values[:]

  return _convert(result)


def _bind(obj, form, memo):
  """Helper for the field binding.  This is inspired by the way `deepcopy`
  is implemented.
  """
  if memo is None:
    memo = {}
  obj_id = id(obj)
  if obj_id in memo:
    return memo[obj_id]
  rv = obj._bind(form, memo)
  memo[obj_id] = rv
  return rv


def _force_dict(value):
  """If the value is not a dict, raise an exception."""
  if value is None or not isinstance(value, dict):
    return {}
  return value


def _force_list(value):
  """If the value is not a list, make it one."""
  if value is None:
    return []
  try:
    if isinstance(value, basestring):
      raise TypeError()
    return list(value)
  except TypeError:
    return [value]


def _make_widget(field, name, value, errors):
  """Shortcut for widget creation."""
  return field.widget(field, name, value, errors)


def _make_name(parent, child):
  """Joins a name."""
  if parent is None:
    result = child
  else:
    result = '%s.%s' % (parent, child)

  # try to return a ascii only bytestring if possible
  try:
    return str(result)
  except UnicodeError:
    return unicode(result)


def _to_string(value):
  """Convert a value to unicode, None means empty string."""
  if value is None:
    return u''
  return unicode(value)


def _to_list(value):
  """Similar to `_force_list` but always succeeds and never drops data."""
  if value is None:
    return []
  if isinstance(value, basestring):
    return [value]
  try:
    return list(value)
  except TypeError:
    return [value]


def _value_matches_choice(value, choice):
  """Checks if a given value matches a choice."""
  # this algorithm is also implemented in `MultiChoiceField.convert`
  # for better scaling with multiple items.  If it's changed here, it
  # must be changed for the multi choice field too.
  return choice == value or _to_string(choice) == _to_string(value)


def _iter_choices(choices):
  """Iterate over choices."""
  if choices is not None:
    for choice in choices:
      if not isinstance(choice, tuple):
        choice = (choice, choice)
      yield choice


def _is_choice_selected(field, value, choice):
  """Checks if a choice is selected.  If the field is a multi select
  field it's checked if the choice is in the passed iterable of values,
  otherwise it's checked if the value matches the choice.
  """
  if field.multiple_choices:
    for value in value:
      if _value_matches_choice(value, choice):
        return True
    return False
  return _value_matches_choice(value, choice)


class _Renderable(object):
  """Mixin for renderable HTML objects."""

  def render(self):
    return u''

  def __call__(self, *args, **kwargs):
    return self.render(*args, **kwargs)


class Widget(_Renderable):
  """Baseclass for all widgets.  All widgets share a common interface
  that can be used from within templates.

  Take this form as an example:

  >>> class LoginForm(Form):
  ...     username = TextField(required=True)
  ...     password = TextField(widget=PasswordInput)
  ...     flags = MultiChoiceField(choices=[1, 2, 3])
  ...
  >>> form = LoginForm()
  >>> form.validate({'username': '', 'password': '',
  ...                'flags': [1, 3]})
  False
  >>> widget = form.as_widget()

  You can get the subwidgets by using the normal indexing operators:

  >>> username = widget['username']
  >>> password = widget['password']

  To render a widget you can usually invoke the `render()` method.  All
  keyword parameters are used as HTML attribute in the resulting tag.
  You can also call the widget itself (``username()`` instead of
  ``username.render()``) which does the same if there are no errors for
  the field but adds the default error list after the widget if there
  are errors.

  Widgets have some public attributes:

  `errors`

      gives the list of errors:

      >>> username.errors
      [u'This field is required.']

      This error list is printable:

      >>> print username.errors()
      <ul class="errors"><li>This field is required.</li></ul>

      Like any other sequence that yields list items it provides
      `as_ul` and `as_ol` methods:

      >>> print username.errors.as_ul()
      <ul><li>This field is required.</li></ul>

      Keep in mind that ``widget.errors()`` is equivalent to
      ``widget.errors.as_ul(class_='errors', hide_empty=True)``.

  `value`

      returns the value of the widget as primitive.  For basic
      widgets this is always a string, for widgets with subwidgets or
      widgets with multiple values a dict or a list:

      >>> username.value
      u''
      >>> widget['flags'].value
      [u'1', u'3']

  `name` gives you the name of the field for form submissions:

      >>> username.name
      'username'

      Please keep in mind that the name is not always that obvious.  Zine
      supports nested form fields so it's a good idea to always use the
      name attribute.

  `id`

      gives you the default domain for the widget.  This is either none
      if there is no idea for the field or `f_` + the field name with
      underscores instead of dots:

      >>> username.id
      'f_username'

  `all_errors`

      like `errors` but also contains the errors of child
      widgets.
  """

  disable_dt = False
  needs_multipart_form = False

  def __init__(self, field, name, value, all_errors):
    self._field = field
    self._value = value
    self._all_errors = all_errors
    self.name = name

  def hidden(self):
    """Return one or multiple hidden fields for the current value.  This
    also handles subwidgets.  This is useful for transparent form data
    passing.
    """
    fields = []

    def _add_field(name, value):
      fields.append(html.input(type='hidden', name=name, value=value))

    def _to_hidden(value, name):
      if isinstance(value, list):
        for idx, value in enumerate(value):
          _to_hidden(value, _make_name(name, idx))
      elif isinstance(value, dict):
        for key, value in value.iteritems():
          _to_hidden(value, _make_name(name, key))
      else:
        _add_field(name, value)

    _to_hidden(self.value, self.name)
    return u'\n'.join(fields)

  @property
  def localname(self):
    """The local name of the field."""
    return self.name.rsplit('.', 1)[-1]

  @property
  def id(self):
    """The proposed id for this widget."""
    if self.name is not None:
      return 'f_' + self.name.replace('.', '__')

  @property
  def value(self):
    """The primitive value for this widget."""
    return self._field.to_primitive(self._value)

  @property
  def label(self):
    """The label for the widget."""
    if self._field.label is not None:
      return Label(unicode(self._field.label), self.id)

  @property
  def help_text(self):
    """The help text of the widget."""
    if self._field.help_text is not None:
      return unicode(self._field.help_text)

  @property
  def errors(self):
    """The direct errors of this widget."""
    if self.name in self._all_errors:
      return self._all_errors[self.name]
    return ErrorList()

  @property
  def all_errors(self):
    """The current errors and the errors of all child widgets."""
    items = sorted(self._all_errors.items())
    if self.name is None:
      return ErrorList(chain(*(item[1] for item in items)))
    result = ErrorList()
    for key, value in items:
      if key == self.name or key.startswith(self.name + '.'):
        result.extend(value)
    return result

  def as_dd(self, **attrs):
    """Return a dt/dd item."""
    rv = []
    if not self.disable_dt:
      label = self.label
      if label:
        rv.append(html.dt(label()))
    rv.append(html.dd(self(**attrs)))
    if self.help_text:
      rv.append(html.dd(self.help_text, class_='explanation'))
    return u''.join(rv)

  def _attr_setdefault(self, attrs):
    """Add an ID to the attrs if there is none."""
    if 'id' not in attrs and self.id is not None:
      attrs['id'] = self.id

  def __call__(self, **attrs):
    """The default display is the form + error list as ul if needed."""
    return self.render(**attrs) + self.errors()


class Label(_Renderable):
  """Holds a label."""

  def __init__(self, text, linked_to=None):
    self.text = text
    self.linked_to = linked_to

  def render(self, **attrs):
    attrs.setdefault('for', self.linked_to)
    return html.label(escape(self.text), **attrs)


class InternalWidget(Widget):
  """Special widgets are widgets that can't be used on arbitrary
  form fields but belong to others.
  """

  def __init__(self, parent):
    self._parent = parent

  value = name = None
  errors = all_errors = property(lambda x: ErrorList())


class Input(Widget):
  """A widget that is a HTML input field."""
  hide_value = False
  type = None

  def render(self, **attrs):
    self._attr_setdefault(attrs)
    value = self.value
    if self.hide_value:
      value = u''
    return html.input(name=self.name, value=value, type=self.type,
                      **attrs)


class FileInput(Input):
  """A widget for uploading files."""
  type = 'file'
  needs_multipart_form = True


class MultipleFieldMixin(object):
  def __call__(self, **attrs):
    """form + all_errors list as ul if needed."""
    return self.render(**attrs) + self.all_errors()


class TextInput(Input):
  """A widget that holds text."""
  type = 'text'


class MultipleTextInput(MultipleFieldMixin, TextInput):
  pass


class PasswordInput(TextInput):
  """A widget that holds a password."""
  type = 'password'
  hide_value = True


class HiddenInput(Input):
  """A hidden input field for text."""
  type = 'hidden'
  disable_dt = True 


class Textarea(Widget):
  """Displays a textarea."""

  def _attr_setdefault(self, attrs):
    Widget._attr_setdefault(self, attrs)
    attrs.setdefault('rows', 8)
    attrs.setdefault('cols', 40)

  def render(self, **attrs):
    self._attr_setdefault(attrs)
    return html.textarea(self.value, name=self.name, **attrs)


class MultipleTextarea(MultipleFieldMixin, Textarea):
  pass


class Checkbox(Widget):
  """A simple checkbox."""

  @property
  def checked(self):
    return self.value != u'False'

  def with_help_text(self, **attrs):
    """Render the checkbox with help text."""
    data = self(**attrs)
    if self.help_text:
      data += u' ' + html.label(self.help_text, class_='explanation',
                                for_=self.id)
    return data

  def as_dd(self, **attrs):
    """Return a dt/dd item."""
    rv = []
    label = self.label
    if label:
      rv.append(html.dt(label()))
    rv.append(html.dd(self.with_help_text()))
    return u''.join(rv)

  def as_li(self, **attrs):
    """Return a li item."""
    rv = [self.render(**attrs)]
    if self.label:
      rv.append(u' ' + self.label())
    if self.help_text:
      rv.append(html.div(self.help_text, class_='explanation'))
    rv.append(self.errors())
    return html.li(u''.join(rv))

  def render(self, **attrs):
    self._attr_setdefault(attrs)
    return html.input(name=self.name, type='checkbox',
                      checked=self.checked, **attrs)


class SelectBox(Widget):
  """A select box."""

  def _attr_setdefault(self, attrs):
    Widget._attr_setdefault(self, attrs)
    attrs.setdefault('multiple', self._field.multiple_choices)

  def render(self, **attrs):
    self._attr_setdefault(attrs)
    items = []
    for choice in self._field.choices:
      if isinstance(choice, tuple):
        key, value = choice
      else:
        key = value = choice
      selected = _is_choice_selected(self._field, self.value, key)
      items.append(html.option(unicode(value), value=unicode(key),
                               selected=selected))
    return html.select(name=self.name, *items, **attrs)


class _InputGroupMember(InternalWidget):
  """A widget that is a single radio button."""

  # override the label descriptor
  label = None
  inline_label = True

  def __init__(self, parent, value, label):
    InternalWidget.__init__(self, parent)
    self.value = unicode(value)
    self.label = Label(label, self.id)

  @property
  def name(self):
    return self._parent.name

  @property
  def id(self):
    return 'f_%s_%s' % (self._parent.name, self.value)

  @property
  def checked(self):
    return _is_choice_selected(self._parent._field, self._parent.value,
                               self.value)

  def render(self, **attrs):
    self._attr_setdefault(attrs)
    return html.input(type=self.type, name=self.name, value=self.value,
                      checked=self.checked, **attrs)


class RadioButton(_InputGroupMember):
  """A radio button in an input group."""
  type = 'radio'


class GroupCheckbox(_InputGroupMember):
  """A checkbox in an input group."""
  type = 'checkbox'


class _InputGroup(Widget):

  def __init__(self, field, name, value, all_errors):
    Widget.__init__(self, field, name, value, all_errors)
    self.choices = []
    self._subwidgets = {}
    for value, label in _iter_choices(self._field.choices):
      widget = self.subwidget(self, value, label)
      self.choices.append(widget)
      self._subwidgets[value] = widget

  def __getitem__(self, value):
    """Return a subwidget."""
    return self._subwidgets[value]

  def _as_list(self, list_type, attrs):
    if attrs.pop('hide_empty', False) and not self.choices:
      return u''
    self._attr_setdefault(attrs)
    empty_msg = attrs.pop('empty_msg', None)
    class_ = attrs.pop('class_', attrs.pop('class', None))
    if class_ is None:
      class_ = 'choicegroup'
    attrs['class'] = class_
    choices = [u'<li>%s %s</li>' % (
        choice(),
        choice.label()
    ) for choice in self.choices]
    if not choices:
      if empty_msg is None:
        empty_msg = _('No choices.')
      choices.append(u'<li>%s</li>' % _(empty_msg))
    return list_type(*choices, **attrs)

  def as_ul(self, **attrs):
    """Render the radio buttons widget as <ul>"""
    return self._as_list(html.ul, attrs)

  def as_ol(self, **attrs):
    """Render the radio buttons widget as <ol>"""
    return self._as_list(html.ol, attrs)

  def as_table(self, **attrs):
    """Render the radio buttons widget as <table>"""
    self._attr_setdefault(attrs)
    return list_type(*[u'<tr><td>%s</td><td>%s</td></tr>' % (
        choice,
        choice.label
    ) for choice in self.choices], **attrs)

  def render(self, **attrs):
    return self.as_ul(**attrs)


class RadioButtonGroup(_InputGroup):
  """A group of radio buttons."""
  subwidget = RadioButton


class CheckboxGroup(_InputGroup):
  """A group of checkboxes."""
  subwidget = GroupCheckbox


class MappingWidget(Widget):
  """Special widget for dict-like fields."""

  def __init__(self, field, name, value, all_errors):
    Widget.__init__(self, field, name, _force_dict(value), all_errors)
    self._subwidgets = {}

  def __getitem__(self, name):
    subwidget = self._subwidgets.get(name)
    if subwidget is None:
      # this could raise a KeyError we pass through
      subwidget = _make_widget(self._field.fields[name],
                               _make_name(self.name, name),
                               self._value.get(name),
                               self._all_errors)
      self._subwidgets[name] = subwidget
    return subwidget

  def as_dl(self, **attrs):
    return html.dl(*[x.as_dd() for x in self], **attrs)

  def __call__(self, *args, **kwargs):
    return self.as_dl(*args, **kwargs)

  def __iter__(self):
    for key in self._field.fields:
      yield self[key]


class FormWidget(MappingWidget):
  """A widget for forms."""

  def get_hidden_fields(self):
    """This method is called by the `hidden_fields` property to return
    a list of (key, value) pairs for the special hidden fields.
    """
    fields = []
    if self._field.form.request is not None:
      if self._field.form.csrf_protected:
        fields.append(('_csrf_token', self.csrf_token))
#             if self._field.form.redirect_tracking:
#                 target = self.redirect_target
#                 if target is not None:
#                     fields.append(('_redirect_target', target))
    return fields

  @property
  def hidden_fields(self):
    """The hidden fields as string."""
    return u''.join(html.input(type='hidden', name=name, value=value)
                    for name, value in self.get_hidden_fields())

  @property
  def csrf_token(self):
    """Forward the CSRF check token for templates."""
    return self._field.form.csrf_token

#     @property
#     def redirect_target(self):
#         """The redirect target for this form."""
#         return self._field.form.redirect_target

  def default_actions(self, **attrs):
    """Returns a default action div with a submit button."""
    label = attrs.pop('label', None)
    if label is None:
      label = _('Submit')
    attrs.setdefault('class', 'actions')
    return html.div(html.input(type='submit', value=label), **attrs)

  def render(self, action='', method='post', **attrs):
    self._attr_setdefault(attrs)
    with_errors = attrs.pop('with_errors', False)

    # support jinja's caller
    caller = attrs.pop('caller', None)
    if caller is not None:
      body = caller()
    else:
      body = self.as_dl() + self.default_actions()

    hidden = self.hidden_fields
    if hidden:
      # if there are hidden fields we put an invisible div around
      # it.  the HTML standard doesn't allow input fields as direct
      # childs of a <form> tag...
      body = '<div style="display: none">%s</div>%s' % (hidden, body)

    if with_errors:
      body = self.errors() + body
    if self.is_multipart:
      attrs['enctype'] = 'multipart/form-data'
    return html.form(body, action=action, method=method, **attrs)

  @property
  def is_multipart(self):
    for widget in self:
      if widget.needs_multipart_form:
        return True
    return False

  def __call__(self, *args, **attrs):
    attrs.setdefault('with_errors', True)
    return self.render(*args, **attrs)


class ListWidget(Widget):
  """Special widget for list-like fields."""

  def __init__(self, field, name, value, all_errors):
    Widget.__init__(self, field, name, _force_list(value), all_errors)
    self._subwidgets = {}

  def as_ul(self, **attrs):
    return self._as_list(html.ul, attrs)

  def as_ol(self, **attrs):
    return self._as_list(html.ol, attrs)

  def _as_list(self, factory, attrs):
    if attrs.pop('hide_empty', False) and not self:
      return u''
    items = []
    for index in xrange(len(self) + attrs.pop('extra_rows', 1)):
      items.append(html.li(self[index]()))
    # add an invisible item for the validator
    if not items:
      items.append(html.li(style='display: none'))
    return factory(*items, **attrs)

  def __getitem__(self, index):
    if not isinstance(index, (int, long)):
      raise TypeError('list widget indices must be integers')
    subwidget = self._subwidgets.get(index)
    if subwidget is None:
      try:
        value = self._value[index]
      except IndexError:
        # return an widget without value if we try
        # to access a field not in the list
        value = None
      subwidget = _make_widget(self._field.field,
                               _make_name(self.name, index), value,
                               self._all_errors)
      self._subwidgets[index] = subwidget
    return subwidget

  def __iter__(self):
    for index in xrange(len(self)):
      yield self[index]

  def __len__(self):
    return len(self._value)

  def __call__(self, *args, **kwargs):
    return self.as_ul(*args, **kwargs)


class ErrorList(_Renderable, list):
  """The class that is used to display the errors."""

  def render(self, **attrs):
    return self.as_ul(**attrs)

  def as_ul(self, **attrs):
    return self._as_list(html.ul, attrs)

  def as_ol(self, **attrs):
    return self._as_list(html.ol, attrs)

  def _as_list(self, factory, attrs):
    if attrs.pop('hide_empty', False) and not self:
      return u''
    return factory(*(html.li(item) for item in self), **attrs)

  def __call__(self, **attrs):
    attrs.setdefault('class', attrs.pop('class_', 'errors'))
    attrs.setdefault('hide_empty', True)
    return self.render(**attrs)


class MultipleValidationErrors(ValidationError):
  """A validation error subclass for multiple errors raised by
  subfields.  This is used by the mapping and list fields.
  """

  def __init__(self, errors):
    ValidationError.__init__(self, '%d error%s' % (
        len(errors), len(errors) != 1 and 's' or ''
    ))
    self.errors = errors

  def __unicode__(self):
    return ', '.join(map(unicode, self.errors.itervalues()))

  def unpack(self, key=None):
    rv = {}
    for name, error in self.errors.iteritems():
      rv.update(error.unpack(_make_name(key, name)))
    return rv


class FieldMeta(type):

  def __new__(cls, name, bases, d):
    messages = {}
    for base in reversed(bases):
      if hasattr(base, 'messages'):
        messages.update(base.messages)
    if 'messages' in d:
      messages.update(d['messages'])
    d['messages'] = messages
    return type.__new__(cls, name, bases, d)


class Field(object):
  """Abstract field base class."""

  __metaclass__ = FieldMeta
  messages = dict(required=lazy_gettext('This field is required.'))
  form = None
  widget = TextInput

  # these attributes are used by the widgets to get an idea what
  # choices to display.  Not every field will also validate them.
  multiple_choices = False
  choices = ()

  # fields that have this attribute set get special treatment on
  # validation.  It means that even though a value was not in the
  # submitted data it's validated against a default value.
  validate_on_omission = False
  creation_counter = 0

  def __init__(self, label=None, help_text=None, validators=None,
               widget=None, messages=None, default=missing):
    self._position_hint = _next_position_hint()
    self.label = label
    self.help_text = help_text
    if validators is None:
      validators = []
    self.validators = validators
    self.custom_converter = None
    if widget is not None:
      self.widget = widget
    if messages:
      self.messages = self.messages.copy()
      self.messages.update(messages)
    self._default = default
    assert not issubclass(self.widget, InternalWidget), \
        'can\'t use internal widgets as widgets for fields'
    self.creation_counter = Field.creation_counter
    Field.creation_counter += 1

  def __call__(self, value):
    value = self.convert(value)
    self.apply_validators(value)
    return value

  def __copy__(self):
    return _bind(self, None, None)

  def apply_validators(self, value):
    """Applies all validators on the value."""
    if self.should_validate(value):
      for validate in self.validators:
        validate(self.form, value)

  def should_validate(self, value):
    """Per default validate if the value is not None.  This method is
    called before the custom validators are applied to not perform
    validation if the field is empty and not required.

    For example a validator like `is_valid_ip` is never called if the
    value is an empty string and the field hasn't raised a validation
    error when checking if the field is required.
    """
    return value is not None

  def convert(self, value):
    """This can be overridden by subclasses and performs the value
    conversion.
    """
    return unicode(value)

  def to_primitive(self, value):
    """Convert a value into a primitve (string or a list/dict of lists,
    dicts or strings).

    This method must never fail!
    """
    return _to_string(value)

  def get_default(self):
    if callable(self._default):
      return self._default()
    return self._default

  def _bind(self, form, memo):
    """Method that binds a field to a form. If `form` is None, a copy of
    the field is returned."""
    if form is not None and self.bound:
      raise TypeError('%r already bound' % type(obj).__name__)
    rv = object.__new__(self.__class__)
    rv.__dict__.update(self.__dict__)
    rv.validators = self.validators[:]
    rv.messages = self.messages.copy()
    if form is not None:
      rv.form = form
    return rv

  @property
  def bound(self):
    """True if the form is bound."""
    return 'form' in self.__dict__

  def __repr__(self):
    rv = object.__repr__(self)
    if self.bound:
      rv = rv[:-1] + ' [bound]>'
    return rv


class Mapping(Field):
  """Apply a set of fields to a dictionary of values.

  >>> field = Mapping(name=TextField(), age=IntegerField())
  >>> field({'name': u'John Doe', 'age': u'42'})
  {'age': 42, 'name': u'John Doe'}

  Although it's possible to reassign the widget after field construction
  it's not recommended because the `MappingWidget` is the only builtin
  widget that is able to handle mapping structures.
  """

  widget = MappingWidget

  def __init__(self, *args, **fields):
    Field.__init__(self)
    if len(args) == 1:
      if fields:
        raise TypeError('keyword arguments and dict given')
      self.fields = OrderedDict(args[0])
    else:
      if args:
        raise TypeError('no positional arguments allowed if keyword '
                        'arguments provided.')
      self.fields = OrderedDict(fields)
    self.fields.sort(key=lambda i: i[1]._position_hint)

  def convert(self, value):
    value = _force_dict(value)
    errors = {}
    result = {}
    for name, field in self.fields.iteritems():
      try:
        result[name] = field(value.get(name))
      except ValidationError, e:
        errors[name] = e
    if errors:
      raise MultipleValidationErrors(errors)
    return result

  def to_primitive(self, value):
    value = _force_dict(value)
    result = {}
    for key, field in self.fields.iteritems():
      result[key] = field.to_primitive(value.get(key))
    return result

  def _bind(self, form, memo):
    rv = Field._bind(self, form, memo)
    rv.fields = OrderedDict()
    for key, field in self.fields.iteritems():
      rv.fields[key] = _bind(field, form, memo)
    return rv


class FormMapping(Mapping):
  """Like a mapping but does csrf protection and stuff."""

  widget = FormWidget

  def convert(self, value):
    if self.form is None:
      raise TypeError('form mapping without form passed is unable '
                      'to convert data')
    if self.form.csrf_protected and self.form.request is not None:
      token = self.form.request.values.get('_csrf_token')
      if token != self.form.csrf_token:
        raise ValidationError(_(u'Invalid security token submitted.'))
    return Mapping.convert(self, value)


class FormAsField(Mapping):
  """If a form is converted into a field the returned field object is an
  instance of this class.  The behavior is mostly equivalent to a normal
  :class:`Mapping` field with the difference that it as an attribute called
  :attr:`form_class` that points to the form class it was created from.
  """

  def __init__(self):
    raise TypeError('can\'t create %r instances' %
                    self.__class__.__name__)


class Multiple(Field):
  """Apply a single field to a sequence of values.

  >>> field = Multiple(IntegerField())
  >>> field([u'1', u'2', u'3'])
  [1, 2, 3]

  Recommended widgets:

  -   `ListWidget` -- the default one and useful if multiple complex
      fields are in use.
  -   `CheckboxGroup` -- useful in combination with choices
  -   `SelectBoxWidget` -- useful in combination with choices
  """

  widget = ListWidget
  messages = dict(too_small=None, too_big=None)
  validate_on_omission = True

  def __init__(self, field, label=None, help_text=None, min_size=None,
               max_size=None, validators=None, widget=None, messages=None,
               default=missing, required=False):
    Field.__init__(self, label, help_text, validators, widget, messages,
                   default)
    self.field = field
    self.min_size = min_size
    self.max_size = max_size
    if required and self.min_size is None:
      self.min_size = 1

  @property
  def multiple_choices(self):
    return self.max_size is None or self.max_size > 1

  def convert(self, value):
    value = _force_list(value)
    if self.min_size is not None and len(value) < self.min_size:
      message = self.messages['too_small']
      if message is None:
        message = ngettext(u'Please provide at least %d item.',
                           u'Please provide at least %d items.',
                           self.min_size) % self.min_size
      raise ValidationError(message)
    if self.max_size is not None and len(value) > self.max_size:
      message = self.messages['too_big']
      if message is None:
        message = ngettext(u'Please provide no more than %d item.',
                           u'Please provide no more than %d items.',
                           self.max_size) % self.max_size
      raise ValidationError(message)
    result = []
    errors = {}
    for idx, item in enumerate(value):
      try:
        result.append(self.field(item))
      except ValidationError, e:
        errors[idx] = e
    if errors:
      raise MultipleValidationErrors(errors)
    return result

  def to_primitive(self, value):
    return map(self.field.to_primitive, _force_list(value))

  def _bind(self, form, memo):
    rv = Field._bind(self, form, memo)
    rv.field = _bind(self.field, form, memo)
    return rv


class CommaSeparated(Multiple):
  """Works like the multiple field but for comma separated values:

  >>> field = CommaSeparated(IntegerField())
  >>> field(u'1, 2, 3')
  [1, 2, 3]

  The default widget is a `MultipleTextInput` but `MultipleTextarea`
  would be a possible choices as well.
  """

  widget = MultipleTextInput

  def __init__(self, field, label=None, help_text=None, min_size=None,
               max_size=None, sep=u',', validators=None, widget=None,
               messages=None, default=missing, required=False):
    Multiple.__init__(self, field, label, help_text, min_size,
                      max_size, validators, widget, messages,
                      default, required)
    self.sep = sep

  def convert(self, value):
    if isinstance(value, basestring):
      value = filter(None, [x.strip() for x in value.split(self.sep)])
    return Multiple.convert(self, value)

  def to_primitive(self, value):
    if value is None:
      return u''
    if isinstance(value, basestring):
      return value
    return (self.sep + u' ').join(map(self.field.to_primitive, value))


class LineSeparated(CommaSeparated):
  r"""Works like `CommaSeparated` but uses multiple lines:

  >>> field = LineSeparated(IntegerField())
  >>> field(u'1\n2\n3')
  [1, 2, 3]

  The default widget is a `MultipleTextarea` and taht is pretty much
  the only thing that makes sense for this widget.
  """
  widget = MultipleTextarea

  def convert(self, value):
    if isinstance(value, basestring):
      value = filter(None, [x.strip() for x in value.splitlines()])
    return Multiple.convert(self, value)

  def to_primitive(self, value):
    if value is None:
      return u''
    if isinstance(value, basestring):
      return value
    return u'\n'.join(map(self.field.to_primitive, value))


class TextField(Field):
  """Field for strings.

  >>> field = TextField(required=True, min_length=6)
  >>> field('foo bar')
  u'foo bar'
  >>> field('')
  Traceback (most recent call last):
    ...
  ValidationError: This field is required.
  """

  messages = dict(too_short=None, too_long=None)

  def __init__(self, label=None, help_text=None, required=False,
               min_length=None, max_length=None, validators=None,
               widget=None, messages=None, default=missing):
    Field.__init__(self, label, help_text, validators, widget, messages,
                   default)
    self.required = required
    self.min_length = min_length
    self.max_length = max_length

  def convert(self, value):
    value = _to_string(value)
    if self.required and not value:
      raise ValidationError(self.messages['required'])
    if self.min_length is not None and len(value) < self.min_length:
      message = self.messages['too_short']
      if message is None:
        message = ngettext(u'Please enter at least %d character.',
                           u'Please enter at least %d characters.',
                           self.min_length) % self.min_length
      raise ValidationError(message)
    if self.max_length is not None and len(value) > self.max_length:
      message = self.messages['too_long']
      if message is None:
        message = ngettext(u'Please enter no more than %d character.',
                           u'Please enter no more than %d characters.',
                           self.max_length) % self.max_length
      raise ValidationError(message)
    return value

  def should_validate(self, value):
    """Validate if the string is not empty."""
    return bool(value)


class KeyField(TextField):
 def convert(self, value):
   value = super(KeyField, self).convert(value)
   try:
     return db.Key(value)
   except Exception, e:
     raise ValidationError(e)


class RegexField(TextField):
  messages = dict(invalid=lazy_gettext(u"The value is invalid."))
  def __init__(self, regex, *args, **kwargs):
    super(RegexField, self).__init__(*args, **kwargs)
    if isinstance(regex, basestring):
      regex = re.compile(regex)
    self.regex = regex

  def convert(self, value):
    value = super(RegexField, self).convert(value)
    if value == u"":
      return value
    if not self.regex.search(value):
      raise ValidationError(self.messages["invalid"])
    return value

email_re = re.compile(
  r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"
  r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"'
  r')@(?:[A-Z0-9]+(?:-*[A-Z0-9]+)*\.)+[A-Z]{2,6}$', re.IGNORECASE)

class EmailField(RegexField):
  messages = {
    'invalid': lazy_gettext(u'Enter a valid e-mail address.'),
  }

  def __init__(self, *args, **kwargs):
    RegexField.__init__(self, email_re, *args, **kwargs)


class DateTimeField(Field):
  """Field for datetime objects.

  >>> field = DateTimeField()
  >>> field('1970-01-12 00:00')
  datetime.datetime(1970, 1, 12, 0, 0)

  >>> field('foo')
  Traceback (most recent call last):
    ...
  ValidationError: Please enter a valid date.
  """

  messages = dict(invalid_date=lazy_gettext('Please enter a valid date.'))

  def __init__(self, label=None, help_text=None, required=False,
               rebase=True, validators=None, widget=None, messages=None,
               default=missing):
    Field.__init__(self, label, help_text, validators, widget, messages,
                   default)
    self.required = required
    self.rebase = rebase

  def convert(self, value):
    if isinstance(value, datetime):
      return value
    value = _to_string(value)
    if not value:
      if self.required:
        raise ValidationError(self.messages['required'])
      return None
    try:
      return parse_datetime(value, rebase=self.rebase)
    except ValueError:
      raise ValidationError(self.messages['invalid_date'])

  def to_primitive(self, value):
    if isinstance(value, datetime):
      value = format_system_datetime(value, rebase=self.rebase)
    return value


class ModelField(Field):
  """A field that queries for a model.

  The first argument is the name of the model. If the key is not given
  (None) the primary key is assumed. You can specify query parameter
  on init or anytime you want via set_query() method. It gives you
  query based option rendering and validation.

  Here is an example for setting query after init:

  >>> class FormWithModelField(Form):
  ...    model_field = forms.ModelField(model=TestModel, reuired=True)

  >>> form = FormWithModelField()
  ... query = TestModel.all().filter('user =', user.key())
  ... form.model_field.set_query(query)

  If the Model class has ``__unicode__()`` method, the return value of
  this method will be used for rendering the text in an option tag. If
  there's no ``__unicode__()`` method, ``Model.__repr__()`` will be
  used for this purpose. You can override this behavior by passing an
  attribute name used for the option tag's value with ``option_name``
  keyword argument on initialization of this field.

  """
  messages = dict(not_found=lazy_gettext(
      u'The selected entity does not exist, or is not allowed to select.'))
  widget = SelectBox

  def __init__(self, model=None, key=None, label=None, help_text=None,
               required=False, message=None, validators=None, widget=None,
               messages=None, default=missing, on_not_found=None,
               query=None, option_name=None):
    Field.__init__(self, label, help_text, validators, widget, messages,
                   default)
    self.model = model
    self.key = key
    self.required = required
    self.message = message
    self.on_not_found = on_not_found
    self.query = query
    self.option_name = option_name
    self.__choices = None

  def convert(self, value):
    import copy
    if isinstance(value, self.model):
      return value
    if not value:
      if self.required:
        raise ValidationError(self.messages['required'])
      return None
    value = self._coerce_value(value)
    self._prepare_query()
    tmp_query = copy.copy(self.query)
    if self.key is None:
      query = tmp_query.filter("__key__ =", db.Key(value))
    else:
      query = tmp_query.filter("%s =" % self.key, value)
    rv = query.get()

    if rv is None:
      if self.on_not_found is not None:
        self.on_not_found(value)
      raise ValidationError(self.messages['not_found'] %
                            {'value': value})
    return rv

  def _coerce_value(self, value):
    return value

  def to_primitive(self, value):
    if value is None:
      return u''
    elif isinstance(value, self.model):
      if self.key is None:
        return value.key()
      else:
        value = getattr(value, self.key)
    return unicode(value)

  def _get_option_name(self, entry):
    if self.option_name is not None:
      return getattr(entry, self.option_name)
    try:
      return entry.__unicode__()
    except AttributeError:
      return entry.__repr__()

  def _prepare_query(self):
    if self.query is None:
      self.query = self.model.all()

  def _create_choices(self):
    self._prepare_query()
    self.__choices = [("", u"----")] + \
        [(e.key(), escape(self._get_option_name(e)))
         for e in self.query.fetch(1000)]

  def _get_choices(self):
    if self.__choices is None:
      self._create_choices()
    return self.__choices

  def _set_choices(self, choices):
    self.__choices = choices
  choices_doc = """You can set choices directly via this attribute."""
  choices = property(_get_choices, _set_choices, None, choices_doc)

  def set_query(self, query):
    """You can set query directly with this method."""
    self.query = query
    self._create_choices()


class HiddenModelField(ModelField):
  """A hidden field that points to a model identified by primary key.
  Can be used to pass models through a form.
  """
  widget = HiddenInput

  # these messages should never show up unless ...
  #   ... the user tempered with the form data
  #   ... or the object went away in the meantime.
  messages = dict(
      invalid=lazy_gettext('Invalid value.'),
      not_found=lazy_gettext('Key does not exist.')
  )

  def __init__(self, model, key=None, required=False, message=None,
               validators=None, widget=None, messages=None,
               default=missing):
    ModelField.__init__(self, model, key, None, None, required,
                        message, validators, widget, messages,
                        default)

  def _coerce_value(self, value):
    try:
      return int(value)
    except (TypeError, ValueError):
      raise ValidationError(self.messages['invalid'])


class ChoiceField(Field):
  """A field that lets a user select one out of many choices.

  A choice field accepts some choices that are valid values for it.
  Values are compared after converting to unicode which means that
  ``1 == "1"``:

  >>> field = ChoiceField(choices=[1, 2, 3])
  >>> field('1')
  1
  >>> field('42')
  Traceback (most recent call last):
    ...
  ValidationError: Please enter a valid choice.

  Two values `a` and `b` are considered equal if either ``a == b`` or
  ``primitive(a) == primitive(b)`` where `primitive` is the primitive
  of the value.  Primitives are created with the following algorithm:

      1.  if the object is `None` the primitive is the empty string
      2.  otherwise the primitive is the string value of the object

  A choice field also accepts lists of tuples as argument where the
  first item is used for comparing and the second for displaying
  (which is used by the `SelectBoxWidget`):

  >>> field = ChoiceField(choices=[(0, 'inactive'), (1, 'active')])
  >>> field('0')
  0

  Because all fields are bound to the form before validation it's
  possible to assign the choices later:

  >>> class MyForm(Form):
  ...     status = ChoiceField()
  ...
  >>> form = MyForm()
  >>> form.status.choices = [(0, 'inactive', 1, 'active')]
  >>> form.validate({'status': '0'})
  True
  >>> form.data
  {'status': 0}

  If a choice field is set to "not required" and a `SelectBox` is used
  as widget you have to provide an empty choice or the field cannot be
  left blank.

  >>> field = ChoiceField(required=False, choices=[('', _('Nothing')),
  ...                                              ('1', _('Something'))])
  """

  widget = SelectBox
  messages = dict(
      invalid_choice=lazy_gettext('Please enter a valid choice.')
  )

  def __init__(self, label=None, help_text=None, required=False,
               choices=None, validators=None, widget=None, messages=None,
               default=missing):
    Field.__init__(self, label, help_text, validators, widget, messages,
                   default)
    self.required = required
    self.choices = choices

  def convert(self, value):
    if not value and not self.required:
      return
    for choice in self.choices:
      if isinstance(choice, tuple):
        choice = choice[0]
      if _value_matches_choice(value, choice):
        return choice
    raise ValidationError(self.messages['invalid_choice'])

  def _bind(self, form, memo):
    rv = Field._bind(self, form, memo)
    if self.choices is not None:
      rv.choices = list(self.choices)
    return rv


class MultiChoiceField(ChoiceField):
  """A field that lets a user select multiple choices."""

  multiple_choices = True
  messages = dict(too_small=None, too_big=None)
  validate_on_omission = True

  def __init__(self, label=None, help_text=None, choices=None,
               min_size=None, max_size=None, validators=None,
               widget=None, messages=None, default=missing):
    ChoiceField.__init__(self, label, help_text, min_size > 0, choices,
                         validators, widget, messages, default)
    self.min_size = min_size
    self.max_size = max_size

  def convert(self, value):
    result = []
    known_choices = {}
    for choice in self.choices:
      if isinstance(choice, tuple):
        choice = choice[0]
      known_choices[choice] = choice
      known_choices.setdefault(_to_string(choice), choice)

    x = _to_list(value)
    for value in _to_list(value):
      for version in value, _to_string(value):
        if version in known_choices:
          result.append(known_choices[version])
          break
      else:
        raise ValidationError(_(u'“%s” is not a valid choice') %
                              value)

    if self.min_size is not None and len(result) < self.min_size:
      message = self.messages['too_small']
      if message is None:
        message = ngettext(u'Please provide at least %d item.',
                           u'Please provide at least %d items.',
                           self.min_size) % self.min_size
      raise ValidationError(message)
    if self.max_size is not None and len(result) > self.max_size:
      message = self.messages['too_big']
      if message is None:
        message = ngettext(u'Please provide no more than %d item.',
                           u'Please provide no more than %d items.',
                           self.max_size) % self.max_size
      raise ValidationError(message)

    return result

  def to_primitive(self, value):
    return map(unicode, _force_list(value))



class NumberField(Field):
  """Field for numbers.

  >>> field = IntegerField(min_value=0, max_value=99)
  >>> field('13')
  13

  >>> field('thirteen')
  Traceback (most recent call last):
    ...
  ValidationError: Please enter a whole number.

  >>> field('193')
  Traceback (most recent call last):
    ...
  ValidationError: Ensure this value is less than or equal to 99.
  """

  messages = dict(
      too_small=None,
      too_big=None,
      value_error=lazy_gettext('Please enter a number.')
  )

  def __init__(self, label=None, help_text=None, required=False,
               min_value=None, max_value=None, validators=None,
               widget=None, messages=None, default=missing):
    Field.__init__(self, label, help_text, validators, widget, messages,
                   default)
    self.required = required
    self.min_value = min_value
    self.max_value = max_value

  def convert(self, value):
    value = _to_string(value)
    if not value:
      if self.required:
        raise ValidationError(self.messages['required'])
      return None
    try:
      value = self._convert(value)
    except ValueError:
      raise ValidationError(self.messages['value_error'])

    if self.min_value is not None and value < self.min_value:
      message = self.messages['too_small']
      if message is None:
        message = _(u'Ensure this value is greater than or '
                    u'equal to %s.') % self.min_value
      raise ValidationError(message)
    if self.max_value is not None and value > self.max_value:
      message = self.messages['too_big']
      if message is None:
        message = _(u'Ensure this value is less than or '
                    u'equal to %s.') % self.max_value
      raise ValidationError(message)

    return value

  def _convert(self, value):
    try:
      return int(value)
    except ValueError:
      return float(value)


class IntegerField(NumberField):
  """Field for integers.

  >>> field = IntegerField(min_value=0, max_value=99)
  >>> field('13')
  13

  >>> field('thirteen')
  Traceback (most recent call last):
    ...
  ValidationError: Please enter a whole number.

  >>> field('193')
  Traceback (most recent call last):
    ...
  ValidationError: Ensure this value is less than or equal to 99.
  """
  messages = dict(
      too_small=None,
      too_big=None,
      value_error=lazy_gettext('Please enter a whole number.')
  )
  def _convert(self, value):
    return int(value)


class FloatField(NumberField):
  """Field for floats.

  >>> field = IntegerField(min_value=0, max_value=99)
  >>> field('13.4')
  13.4

  >>> field('thirteen')
  Traceback (most recent call last):
    ...
  ValidationError: Please enter a float number.

  >>> field('193.2')
  Traceback (most recent call last):
    ...
  ValidationError: Ensure this value is less than or equal to 99.
  """
  messages = dict(
      too_small=None,
      too_big=None,
      value_error=lazy_gettext('Please enter a float number.')
  )
  def _convert(self, value):
    return float(value)


class FileField(Field):
  """
  Field for file upload.
  """
  widget = FileInput
  def __init__(self, label=None, help_text=None, required=False,
               validators=None, widget=None, messages=None, default=missing):
    Field.__init__(self, label, help_text, validators, widget, messages,
                   default)
    self.required = required

  def convert(self, value):
    if not value:
      if self.required:
        raise ValidationError(_("Please select a file to upload."))
      else:
        return None
    ret = value.read()
    if self.required and len(ret) == 0:
      raise ValidationError(_("File must not empty."))
    return ret

  def to_primitive(self, value):
    # always return None
    return None

class BooleanField(Field):
  """Field for boolean values.

  >>> field = BooleanField()
  >>> field('1')
  True

  >>> field = BooleanField()
  >>> field('')
  False
  """

  widget = Checkbox
  validate_on_omission = True
  choices = [
    (u'True', lazy_gettext(u'True')),
    (u'False', lazy_gettext(u'False'))
  ]

  def __init__(self, label=None, help_text=None, required=False,
               validators=None, widget=None, messages=None, default=missing):
    Field.__init__(self, label, help_text, validators, widget, messages,
                   default)
    self.required = required

  def convert(self, value):
    if self.required and isinstance(value, basestring) and value == u"":
      raise ValidationError(_("Please select True or False."))
    return value != u'False' and bool(value)

  def to_primitive(self, value):
    if self.convert(value):
      return u'True'
    return u'False'


class FormMeta(type):
  """Meta class for forms.  Handles form inheritance and registers
  validator functions.
  """

  def __new__(cls, name, bases, d):
    fields = {}
    validator_functions = {}
    root_validator_functions = []

    for base in reversed(bases):
      if hasattr(base, "_root_field"):
        # base._root_field is always a FormMapping field
        fields.update(base._root_field.fields)
        root_validator_functions.extend(base._root_field.validators)

    if d.has_key("_base_fields"):
      for key, value in d["_base_fields"].iteritems():
        if isinstance(value, Field):
          fields[key] = value
          d[key] = FieldDescriptor(key)

    for key, value in d.iteritems():
      if key.startswith('validate_') and callable(value):
        validator_functions[key[9:]] = value
      elif isinstance(value, Field):
        fields[key] = value
        d[key] = FieldDescriptor(key)

    for field_name, func in validator_functions.iteritems():
      if field_name in fields:
        fields[field_name].validators.append(func)

    d['_root_field'] = root = FormMapping(**fields)
    context_validate = d.get('context_validate')
    root.validators.extend(root_validator_functions)
    if context_validate is not None:
      root.validators.append(context_validate)

    return type.__new__(cls, name, bases, d)

  def as_field(cls):
    """Returns a field object for this form.  The field object returned
    is independent of the form and can be modified in the same manner as
    a bound field.
    """
    field = object.__new__(FormAsField)
    field.__dict__.update(cls._root_field.__dict__)
    field.form_class = cls
    field.validators = cls._root_field.validators[:]
    field.fields = cls._root_field.fields.copy()
    return field

  @property
  def validators(cls):
    return cls._root_field.validators

  @property
  def fields(cls):
    return cls._root_field.fields


class FieldDescriptor(object):

  def __init__(self, name):
    self.name = name

  def __get__(self, obj, type=None):
    try:
      return (obj or type).fields[self.name]
    except KeyError:
      raise AttributeError(self.name)

  def __set__(self, obj, value):
    obj.fields[self.name] = value

  def __delete__(self, obj):
    if self.name not in obj.fields:
      raise AttributeError('%r has no attribute %r' %
                           (type(obj).__name__, self.name))
    del obj.fields[self.name]


class Form(object):
  """Form base class.

  >>> class PersonForm(Form):
  ...     name = TextField(required=True)
  ...     age = IntegerField()

  >>> form = PersonForm()
  >>> form.validate({'name': 'johnny', 'age': '42'})
  True
  >>> form.data['name']
  u'johnny'
  >>> form.data['age']
  42

  Let's cause a simple validation error:

  >>> form = PersonForm()
  >>> form.validate({'name': '', 'age': 'fourty-two'})
  False
  >>> print form.errors['age'][0]
  Please enter a whole number.
  >>> print form.errors['name'][0]
  This field is required.

  You can also add custom validation routines for fields by adding methods
  that start with the prefix ``validate_`` and the field name that take the
  value as argument. For example:

  >>> class PersonForm(Form):
  ...     name = TextField(required=True)
  ...     age = IntegerField()
  ...
  ...     def validate_name(self, value):
  ...         if not value.isalpha():
  ...             raise ValidationError(u'The value must only contain letters')

  >>> form = PersonForm()
  >>> form.validate({'name': 'mr.t', 'age': '42'})
  False
  >>> form.errors
  {'name': [u'The value must only contain letters']}

  You can also validate multiple fields in the context of other fields.
  That validation is performed after all other validations.  Just add a
  method called ``context_validate`` that is passed the dict of all fields:

  >>> class RegisterForm(Form):
  ...     username = TextField(required=True)
  ...     password = TextField(required=True)
  ...     password_again = TextField(required=True)
  ...
  ...     def context_validate(self, data):
  ...         if data['password'] != data['password_again']:
  ...             raise ValidationError(u'The two passwords must be the same')

  >>> form = RegisterForm()
  >>> form.validate({'username': 'admin', 'password': 'blah',
  ...                'password_again': 'blag'})
  ...
  False
  >>> form.errors
  {None: [u'The two passwords must be the same']}

  Forms can be used as fields for other forms.  To create a form field of
  a form you can call the `as_field` class method::

  >>> field = RegisterForm.as_field()

  This field can be used like any other field class.  What's important about
  forms as fields is that validators don't get an instance of `RegisterForm`
  passed as `form` / `self` but the form where it's used in if the field is
  used from a form.

  Form fields are bound to the form on form instanciation.  This makes it
  possible to modify a particular instance of the form.  For example you
  can create an instance of it and drop some fiels by using
  ``del form.fields['name']`` or reassign choices of choice fields.  It's
  however not easily possible to add new fields to an instance because newly
  added fields wouldn't be bound.  The fields that are stored directly on
  the form can also be accessed with their name like a regular attribute.

  Example usage:

  >>> class StatusForm(Form):
  ...     status = ChoiceField()
  ...
  >>> StatusForm.status.bound
  False
  >>> form = StatusForm()
  >>> form.status.bound
  True
  >>> form.status.choices = [u'happy', u'unhappy']
  >>> form.validate({'status': u'happy'})
  True
  >>> form['status']
  u'happy'

  Fields support default values.  These however are not as useful as you
  might think.  These defaults are just annotations for external handling.
  The form validation system does not respect those values.

  They are for example used in the configuration system.

  Example:

  >>> field = TextField(default=u'foo')
  """
  __metaclass__ = FormMeta

  csrf_protected = True
  csrf_key = None
#    redirect_tracking = True

  def __init__(self, initial=None):
    self.request = get_request()
    if initial is None:
      initial = {}
    self.initial = initial
#        self.invalid_redirect_targets = set()

    self._root_field = _bind(self.__class__._root_field, self, {})
    self.reset()
    for name, field in self._root_field.fields.iteritems():
      if field.label is None:
        field.label = name.capitalize().replace("_", " ")

  def __getitem__(self, key):
    return self.data[key]

  def __contains__(self, key):
    return key in self.data

  def as_widget(self):
    """Return the form as widget."""
    # if there is submitted data, use that for the widget
    if self.raw_data is not None:
      data = self.raw_data
    # otherwise go with the data from the source (eg: database)
    else:
      data = self.data
    return _make_widget(self._root_field, None, data, self.errors)

#     def add_invalid_redirect_target(self, *args, **kwargs):
#         """Add an invalid target. Invalid targets are URLs we don't want to
#         visit again. For example if a post is deleted from the post edit page
#         it's a bad idea to redirect back to the edit page because in that
#         situation the edit page would return a page not found.

#         This function accepts the same parameters as `url_for`.
#         """
#         self.invalid_redirect_targets.add(url_for(*args, **kwargs))

#     @property
#     def redirect_target(self):
#         """The back-redirect target for this form."""
#         return get_redirect_target(self.invalid_redirect_targets,
#                                    self.request)

#     def redirect(self, *args, **kwargs):
#         """Redirects to the url rule given or back to the URL where we are
#         comming from if `redirect_tracking` is enabled.
#         """
#         target = None
#         if self.redirect_tracking:
#             target = self.redirect_target
#         if target is None:
#             return redirect_to(*args, **kwargs)
#         return _redirect(target)

  @property
  def csrf_token(self):
    """The unique CSRF security token for this form."""
    if self.request is None:
      raise AttributeError('no csrf token because form not bound '
                           'to request')
    if self.csrf_key is not None:
      csrf_key = self.csrf_key
    else:
      csrf_key = self.request.path
    if hasattr(self.request, 'user'):
      user_id = self.request.user.key()
    else:
      user_id = -1
    if hasattr(self.request, 'session') and not self.request.session.new:
      try:
        session_key = self.request.session.sid
      except Exception:
        # SecureSession
        if CSRF_TOKEN_SEED in self.request.session:
          session_key = self.request.session.get(CSRF_TOKEN_SEED)
        else:
          import uuid
          session_key = str(uuid.uuid4())
          self.request.session[CSRF_TOKEN_SEED] = session_key
    else:
      session_key = -1
    from kay.conf import settings
    key = settings.SECRET_KEY
    return sha1(('%s|%s|%s|%s' % (csrf_key, session_key, user_id, key))
                 .encode('utf-8')).hexdigest()

  @property
  def is_valid(self):
    """True if the form is valid."""
    return not self.errors

  @property
  def has_changed(self):
    """True if the form has changed."""
    return self._root_field.to_primitive(self.initial) != \
           self._root_field.to_primitive(self.data)

  @property
  def fields(self):
    return self._root_field.fields

  @property
  def validators(self):
    return self._root_field.validators

  def reset(self):
    """Resets the form."""
    self.data = self.initial.copy()
    self.errors = {}
    self.raw_data = None

  def append_errors(self, message, field_name=None):
    if not isinstance(message, (list, tuple)):
      messages = [unicode(message)]
    else:
      messages = map(unicode, message)
    error_list = ErrorList(messages)
    error_list.extend(self.errors.get(field_name, []))
    self.errors.update({field_name: error_list})

  def validate(self, data, files=None):
    """Validate the form against the data passed."""
    self.raw_data = _decode(data)
    if files is not None:
      self.raw_data.update(_decode(files))

    # for each field in the root that requires validation on value
    # omission we add `None` into the raw data dict.  Because the
    # implicit switch between initial data and user submitted data
    # only happens on the "root level" for obvious reasons we only
    # have to hook the data in here.
    for name, field in self._root_field.fields.iteritems():
      if field.validate_on_omission and name not in self.raw_data:
        self.raw_data.setdefault(name)

    d = self.data.copy()
    d.update(self.raw_data)
    errors = {}
    try:
      data = self._root_field(d)
    except ValidationError, e:
      errors = e.unpack()
    self.errors = errors
    if errors:
      return False

    self.data.update(data)
    return True
