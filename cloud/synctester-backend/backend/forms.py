from kay.utils import forms
from kay.i18n import gettext as _

class AndroidUserForm(forms.Form):
    tel = forms.TextField(_("tel"), required=True)



class CommentForm(forms.Form):
    user_id = forms.IntegerField(min_value=0, max_value=999999)
    comment = forms.TextField(_("comment"), required=True)
