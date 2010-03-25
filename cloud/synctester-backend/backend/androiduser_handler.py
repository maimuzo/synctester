# -*- coding: utf-8 -*-

from kay.handlers import BaseHandler
from backend.models import *

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

class AndroiduserHandler(BaseHandler):
        
    # Android端末が登録済みかどうかを確認
    def get(self):
        tel = self.request.args.get("tel")
        devId = self.request.args.get("devid")
        simSerial = self.request.args.get("simserial")
        if tel is None or devId is None or simSerial is None:
            req_param = "tel:" + str(tel) + "/devId:" + str(devId) + "/simSerial:" + str(simSerial)
            raise BadRequest("param error.")
        query = AndroidUser.all()
        query.filter("tel =", tel)
        query.filter("devId =", devId)
        query.filter("simSerial =", simSerial)
        android = query.get()
        # まずは電話番号で検索
        android = AndroidUser.get_by_key_name("AU" + tel)
        if android is None:
            # 未登録
            req_param = "tel:" + str(tel) + "/devId:" + str(devId) + "/simSerial:" + str(simSerial)
            raise NotFound("not found Android user. " + req_param)
        else:
            if devId == android.dev_id and simSerial == android.sim_serial:
                # 最終アクセス日時更新
                android.put()
                return render_to_response('backend/result.xml', {'state': "OK", 'message': 'The user was Registed.'}, mimetype="text/xml")
            else:
                return render_to_response('backend/result.xml', {'state': "CHANGED", 'message': 'The user was Registed. but detail was changed.'}, mimetype="text/xml") 
        
    # Android端末を登録
    def post(self):
        tel = self.request.values.get("tel")
        devId = self.request.values.get("devid")
        simSerial = self.request.values.get("simserial")
        if tel is None or devId is None or simSerial is None:
            req_param = "tel:" + str(tel) + "/devId:" + str(devId) + "/simSerial:" + str(simSerial)
            raise NotFound("param error." + req_param)
        android = AndroidUser(key_name='AU'+tel, tel=tel, dev_id=devId, sim_serial=simSerial)
        android.put()
        return render_to_response('backend/result.xml', {'state': "OK", 'message': 'The user was Registed.'}, mimetype="text/xml")
        
        
androiduser_handler = AndroiduserHandler()
    