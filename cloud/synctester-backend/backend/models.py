# -*- coding: utf-8 -*-
# backend.models

from google.appengine.ext import db
from re import MULTILINE

# Create your models here.

class AndroidUser(db.Model):
    # key_name format: "AU" + tel
    tel = db.PhoneNumberProperty(required=True)
    dev_id = db.StringProperty(required=True)
    sim_serial = db.StringProperty(required=True)
    installed_at = db.DateTimeProperty(auto_now_add=True)
    last_access_at = db.DateTimeProperty(auto_now=True)

class Favorite(db.Model):
    # key_name format: "AU" + tel + id
    # parent: instance of AndroidUser
    id = db.IntegerProperty(required=True)
    url = db.StringProperty()
    title = db.StringProperty()
    android_user = db.ReferenceProperty(required=True)
    created_at = db.DateTimeProperty(auto_now_add=True)
    updated_at = db.DateTimeProperty(auto_now=True)
    client_updated_at = db.DateTimeProperty(required=True)
