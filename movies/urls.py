from django.urls import path
from . import views
urlpatterns=[
    path('',views.movie_list,name='movie_list'),
    path('<int:movie_id>/theaters',views.theater_list,name='theater_list'),
    path('theater/<int:theater_id>/seats/book/',views.book_seats,name='book_seats'),
    path('checkout/<int:payment_id>/', views.checkout, name='checkout'),
    path('booking/success/<int:payment_id>/', views.booking_success, name='booking_success'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
    path('analytics/', views.admin_dashboard, name='admin_dashboard'),
]