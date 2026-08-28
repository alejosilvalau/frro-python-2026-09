from django.urls import path
from . import views

app_name = 'portfolio'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('positions/', views.position_list, name='position_list'),
    path('positions/create/', views.position_create, name='position_create'),
    path('positions/<int:position_id>/', views.position_detail, name='position_detail'),
    path('positions/<int:position_id>/update/', views.position_update, name='position_update'),
    path('positions/<int:position_id>/delete/', views.position_delete, name='position_delete'),
    path('positions/<int:position_id>/orders/create/', views.order_create, name='order_create'),
    path('orders/<int:order_id>/delete/', views.order_delete, name='order_delete'),
    path('api/precio/', views.api_instrument_price, name='api_instrument_price'),
]
