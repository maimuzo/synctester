# -*- coding: utf-8 -*-
# backend.urls



from werkzeug.routing import (
  Map, Rule, Submount,
  EndpointPrefix, RuleTemplate,
)

def make_rules():
  return [
    EndpointPrefix('backend/', [
      Rule('/', endpoint='index'),
      Rule('/favorites', endpoint='favorite_list'),
      Rule('/favorite/<int:id>', endpoint='favorite_crud'),
#      Rule('/favorite/<int:id>', endpoint='favorite_view'),
#      Rule('/favorite/<int:id>/update', endpoint='favorite_update'),
#      Rule('/favorite/<int:id>/delete', endpoint='favorite_delete'),
      Rule('/androiduser', endpoint='androiduser'),
    ]),
  ]

all_views = {
  'backend/index': 'backend.views.index',
  'backend/favorite_list': 'backend.views.favorite_list',
  'backend/favorite_crud': ('backend.favorite_handler.FavoriteHandler', (), {}),
#  'backend/favorite_view': ('backend.favorite_handler.FavoriteHandler', (), {}),
#  'backend/favorite_update': ('backend.favorite_handler.FavoriteHandler', (), {}),
#  'backend/favorite_delete': ('backend.favorite_handler.FavoriteHandler', (), {}),
  'backend/androiduser': ('backend.androiduser_handler.AndroiduserHandler', (), {}),
}
