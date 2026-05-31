from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('career/', views.career, name='career'),
    path('api/db/', views.get_db, name='get_db'),
    path('api/db/update/', views.update_db, name='update_db'),
    path('api/db/merge/', views.merge_db, name='merge_db'),
    path('api/db/export/', views.export_db, name='export_db'),
    path('api/db/contribute/', views.contribute, name='contribute'),
    path('api/db/status/', views.sheets_status, name='sheets_status'),
    path('api/consult/save/', views.save_consult, name='save_consult'),
    path('api/consult/class/', views.get_class_students, name='get_class_students'),
]
