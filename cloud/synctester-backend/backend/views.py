# -*- coding: utf-8 -*-
# backend.views

"""
import logging

from google.appengine.api import users
from google.appengine.api import memcache
from werkzeug import (
  unescape, redirect, Response,
)

from kay.i18n import gettext as _
from kay.auth.decorators import login_required

"""

from kay.utils import render_to_response, get_by_key_name_or_404
from models import *
from forms import AndroidUserForm
from kay.utils import (
  render_to_response, reverse,
  get_by_key_name_or_404, get_by_id_or_404,
  to_utc, to_local_timezone, url_for, raise_on_dev
)
from werkzeug.exceptions import (
  NotFound, MethodNotAllowed, BadRequest
)

# Create your views here.

def index(request):
    return render_to_response('backend/index.html', {'message': 'Hello'})

"""
    params 
        tel:Androidの番号
        devid:Android端末番号
        simserial:SIMのシリアルナンバー
"""
def get_android_user(request):
#    form = AndroidUserForm()
#    if not form.validate(request.values):
#        raise Exception("Runtime error. not found user's tel number.")
#    requestTel = form["tel"]
    requestTel = request.args.get('tel')
    requestDevID = request.args.get('devid')
    requestSimSerial = request.args.get('simserial')
    # user = AndroidUser.get(Key("AU" + requestTel))
    # user = get_by_key_name_or_404(model_class=AndroidUser, key_name="AU" + requestTel)
    user = get_by_key_name_or_404(AndroidUser, "AU" + requestTel)
    if user.dev_id == requestDevID and user.sim_serial == requestSimSerial:
        return user
    else:
        NotFound('the user was modified.')
    


def favorite_list(request):
    user = get_android_user(request)
    entities = user.favorite_set
    return render_to_response('backend/favorite_list.xml', {'entities': entities}, mimetype="text/xml")


#def comment_view(request, user_id):
#    user = get_or_add_android_user(request)
#    comment = user.comment_set.filter("user_id = ", user_id).get()
#    if None == comment:
#        raise NotFound("not found user_id:" + str(user_id))
#    return render_to_response('backend/comment_view.xml', {'comment': comment}, mimetype="text/xml")
#    
#
#def comment_update(request, user_id):
#    user = get_or_add_android_user(request)
#    comment = request.values("comment")
#    entity = user.comment_set.filter("user_id = ", user_id).get()
#    if entity:
#        # 更新
#        entity.comment = comment
#    else:
#        # 追加
#        entity = Comment(key_name = "AU" + user.tel + "_" + user_id,
#                          android_user = user,
#                          user_id = user_id,
#                          comment = comment,)
#    entity.put()
#    return render_to_response('backend/comment_view.xml', {'comment': comment}, mimetype="text/xml")
#    
#    
#def comment_delete(request, user_id):
#    user = get_or_add_android_user(request)
#    comment = user.comment_set.filter("user_id = ", user_id).get()
#    if comment:
#        comment.delete()
#        return render_to_response('backend/result.xml', {'state': "OK", 'message': 'OK'}, mimetype="text/xml")
#    else:
#        NotFound("not found user_id:" + str(user_id))