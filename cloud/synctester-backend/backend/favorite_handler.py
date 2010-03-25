# -*- coding: utf-8 -*-

from kay.handlers import BaseHandler
from backend.models import *
from datetime import datetime
import logging
"""

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

"""
from kay.utils import (
  render_to_response, reverse,
  get_by_key_name_or_404, get_by_id_or_404,
  to_utc, to_local_timezone, url_for, raise_on_dev
)
"""
from werkzeug.exceptions import (
  NotFound, MethodNotAllowed, BadRequest
)

from views import get_android_user

class FavoriteHandler(BaseHandler):
    def loggingRequestValue(self, values):
        request = "request.values: "
        for k, v in values.iteritems():
            request += k + ':[' + v + '] / '
        logging.debug(request)

    def loggingAndroidUser(self, android):
        if android is None:
            logging.debug("AndroidUser is not authanticated.")
        else:
            result = "Authanticated AndroidUser: tel:[" + android.tel + "] / devId:[" + android.dev_id + "] / sim_serial:[" + android.sim_serial + "]"
            logging.debug(result)

    def prepare(self):
        self.loggingRequestValue(self.request.values)
        self.android_user = get_android_user(self.request)
        self.loggingAndroidUser(self.android_user)
        
    def get(self, id):
        logging.debug("enter get().")
        entity = self.android_user.favorite_set.filter("id = ", id).get()
        if entity is None:
            raise NotFound("not found id:" + str(id))
        return render_to_response('backend/favorite_view.xml', {'favorite': entity}, mimetype="text/xml")
        

    def post(self, id):
        logging.debug("enter post().")
        if 'delete' == self.request.values.get("_method"):
            return delete(self, id)
        
        url = self.request.values.get("url")
        title = self.request.values.get("title")
        client_updated_at = datetime.strptime(self.request.values.get("updated_at"), "%Y/%m/%d %H:%M:%S")
        entity = self.android_user.favorite_set.filter("id = ", id).get()
        if entity is None:
            # 追加
            entity = Favorite(key_name = "AU" + self.android_user.tel + "_" + str(id),
                              parent = self.android_user,
                              android_user = self.android_user,
                              id = id,
                              url = url,
                              client_updated_at = client_updated_at)
        else:
            # 更新
            entity.url = url
            entity.title = title
            entity.client_updated_at
        entity.put()
        return render_to_response('backend/favorite_view.xml', {'state': "OK", 'message': 'OK', 'favorite': entity}, mimetype="text/xml")
        
        
    def delete(self, id):
        logging.debug("enter delete().")
        entity = self.android_user.favorite_set.filter("id = ", id).get()
        if entity is None:
            # 見つからなかったidをクライアントに戻す
            entity = Favorite(key_name = "AU" + self.android_user.tel + "_" + str(id),
                              parent = self.android_user,
                              android_user = self.android_user,
                              id = id,
                              client_updated_at = datetime.today())
            # 見つからなかった場合、クライアント側のデータは不要なので消す→正規フォーマットで返す
            return render_to_response('backend/favorite_view.xml', {'state': "Not found", 'message': 'not found id:'+ str(id), 'favorite': entity}, mimetype="text/xml")
        else:
            entity.delete()
            return render_to_response('backend/favorite_view.xml', {'state': "OK", 'message': 'OK', 'favorite': entity}, mimetype="text/xml")
        
favorite_handler = FavoriteHandler()
    