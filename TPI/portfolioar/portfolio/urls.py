from django.urls import path
from . import views

app_name = 'portfolio'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('positions/', views.position_list, name='position_list'),
    path('positions/create/', views.position_create, name='position_create'),
    path('positions/<int:position_id>/', views.position_detail, name='position_detail'),
    path('positions/<int:position_id>/delete/', views.position_delete, name='position_delete'),
    path('positions/<int:position_id>/lots/create/', views.lot_create, name='lot_create'),
    path('lots/<int:lot_id>/delete/', views.lot_delete, name='lot_delete'),
    path('positions/<int:position_id>/sales/create/', views.sale_create, name='sale_create'),
    path('api/precio/', views.api_instrument_price, name='api_instrument_price'),
    path('liquidez/', views.cash_list, name='cash_list'),
    path('liquidez/create/', views.cash_create, name='cash_create'),
    path('liquidez/<int:cash_id>/update/', views.cash_update, name='cash_update'),
    path('liquidez/<int:cash_id>/delete/', views.cash_delete, name='cash_delete'),
]
