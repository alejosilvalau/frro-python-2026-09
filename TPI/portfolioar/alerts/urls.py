from django.urls import path
from . import views

app_name = 'alerts'

urlpatterns = [
    path('', views.alert_list, name='alert_list'),
    path('create/', views.alert_create, name='alert_create'),
    path('<int:alert_id>/', views.alert_detail, name='alert_detail'),
    path('<int:alert_id>/update/', views.alert_update, name='alert_update'),
    path('<int:alert_id>/delete/', views.alert_delete, name='alert_delete'),
    path('<int:alert_id>/add-condition/', views.alert_add_condition, name='alert_add_condition'),
    path('<int:alert_id>/remove-condition/<int:condition_id>/', views.alert_remove_condition, name='alert_remove_condition'),
    path('indicators/', views.indicator_list, name='indicator_list'),
    path('conditions/', views.condition_list, name='condition_list'),
]
