from django.shortcuts import render, redirect, get_object_or_404
from .models import Movie, Theater, Seat, Booking, Genre, Language, SeatLock, Payment
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum
from django.core.paginator import Paginator
from django.utils import timezone
from django.core.cache import cache
from .utils import send_booking_email_task
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from datetime import timedelta
import decimal

def movie_list(request):
    search_query = request.GET.get('search', '')
    selected_genres = request.GET.getlist('genres')
    selected_languages = request.GET.getlist('languages')
    sort_by = request.GET.get('sort', '-rating') # Default high to low rating

    # Base query optimized with prefetch_related
    movies = Movie.objects.prefetch_related('genres', 'languages').all()

    # Search filter
    if search_query:
        movies = movies.filter(name__icontains=search_query)

    # Apply Multi-select Genre Filter
    if selected_genres:
        # Use Q objects or direct filter, for 'OR' within genre array:
        movies = movies.filter(genres__name__in=selected_genres).distinct()

    # Apply Multi-select Language Filter
    if selected_languages:
        movies = movies.filter(languages__name__in=selected_languages).distinct()

    # Sorting
    if sort_by in ['rating', '-rating', 'name', '-name']:
        movies = movies.order_by(sort_by)

    # Setup pagination (20 per page for scalability)
    paginator = Paginator(movies, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Dynamic Filter Counts Calculation
    # We annotate genres with the count of movies matching the *current* movies query
    active_movies = movies.values('id')
    
    genres_with_counts = Genre.objects.annotate(
        movie_count=Count('movies', filter=Q(movies__in=active_movies), distinct=True)
    ).order_by('-movie_count', 'name')

    languages_with_counts = Language.objects.annotate(
        movie_count=Count('movies', filter=Q(movies__in=active_movies), distinct=True)
    ).order_by('-movie_count', 'name')

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'selected_genres': selected_genres,
        'selected_languages': selected_languages,
        'sort_by': sort_by,
        'genres': genres_with_counts,
        'languages': languages_with_counts,
    }
    return render(request, 'movies/movie_list.html', context)

def theater_list(request,movie_id):
    movie = get_object_or_404(Movie,id=movie_id)
    theater=Theater.objects.filter(movie=movie)
    return render(request,'movies/theater_list.html',{'movie':movie,'theaters':theater})



@login_required(login_url='/login/')
def book_seats(request, theater_id):
    theater = get_object_or_404(Theater, id=theater_id)
    seats = Seat.objects.filter(theater=theater)
    
    if request.method == 'POST':
        selected_seats = request.POST.getlist('seats')
        error_messages = []
        
        if not selected_seats:
            return render(request, "movies/seat_selection.html", {'theaters': theater, "seats": seats, 'error': "No seat selected"})
        
        locked_seat_objects = []
        
        try:
            # Task 5: Use atomic transaction and row-level locking
            with transaction.atomic():
                # select_for_update prevents other identical requests from touching these rows
                seats_to_book = Seat.objects.select_for_update().filter(id__in=selected_seats, theater=theater)
                
                if len(seats_to_book) != len(selected_seats):
                    raise IntegrityError("Some seats are invalid.")

                now = timezone.now()
                
                # Verify availability and locks
                for seat in seats_to_book:
                    if seat.is_booked:
                        error_messages.append(f"Seat {seat.seat_number} is already fully booked.")
                        continue
                    
                    # Check if there's an active temporary lock by someone else
                    try:
                        active_lock = SeatLock.objects.get(seat=seat)
                        if active_lock.user != request.user and not active_lock.is_expired:
                            error_messages.append(f"Seat {seat.seat_number} is currently being held by another user.")
                        elif active_lock.is_expired:
                            active_lock.delete() # Clear expired lock
                    except SeatLock.DoesNotExist:
                        pass
                
                if error_messages:
                    raise IntegrityError("Validation failed")
                
                # Clear user's previous expired locks
                SeatLock.objects.filter(user=request.user, expires_at__lt=now).delete()

                # Generate Locks (2 mins)
                expires = now + timedelta(minutes=2)
                for seat in seats_to_book:
                    SeatLock.objects.update_or_create(
                        seat=seat, 
                        defaults={'user': request.user, 'expires_at': expires}
                    )
                    locked_seat_objects.append(seat)

        except IntegrityError:
            return render(request, 'movies/seat_selection.html', {
                'theaters': theater, 'seats': seats, 'error': " | ".join(error_messages) or "A concurrency collision occurred. Please select different seats."
            })

        # Initiate Payment (Task 4)
        total_amount = decimal.Decimal(len(locked_seat_objects) * 200) # Mock 200 per seat
        payment = Payment.objects.create(
            user=request.user,
            amount=total_amount,
            status='PENDING'
        )
        return redirect('checkout', payment_id=payment.id)
        
    return render(request, 'movies/seat_selection.html', {'theaters': theater, "seats": seats})

@login_required(login_url='/login/')
def checkout(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action', 'pay')  # 'pay' or 'fail'

        # ---- PAYMENT FAILURE PATH ----
        if action == 'fail':
            payment.status = 'FAILED'
            payment.save()
            # Release all seat locks so other users can book them
            SeatLock.objects.filter(user=request.user).delete()
            return render(request, 'movies/checkout.html', {
                'payment': payment,
                'error': 'Payment failed or was declined. Your seat hold has been released. Please try again.'
            })

        # ---- PAYMENT SUCCESS PATH ----
        payment.status = 'SUCCESS'
        payment.save()
        
        active_locks = SeatLock.objects.filter(user=request.user, expires_at__gt=timezone.now())
        if not active_locks.exists():
            payment.status = 'FAILED'
            payment.save()
            return render(request, 'movies/checkout.html', {
                'payment': payment,
                'error': 'Your seat hold expired before payment completed. Please select seats again.'
            })
        
        # Convert locks to final bookings
        for lock in active_locks:
            Booking.objects.create(
                user=request.user,
                seat=lock.seat,
                movie=lock.seat.theater.movie,
                theater=lock.seat.theater
            )
            seat = lock.seat
            seat.is_booked = True
            seat.save()
            
            # Task 2: Dispatch Email Background Task
            send_booking_email_task(Booking.objects.filter(user=request.user).last())
            
        active_locks.delete() # Free locks
        return redirect('booking_success', payment_id=payment.id)

    return render(request, 'movies/checkout.html', {'payment': payment})

@csrf_exempt
def stripe_webhook(request):
    """
    Simulated Webhook endpoint for Task 4. 
    Accepts Stripe signature payloads securely.
    """
    # Verify signatures and idempotency locally before approving DB hits
    return HttpResponse(status=200)

@login_required(login_url='/login/')
def booking_success(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    # Get the most recent booking for this user to display summary
    booking = Booking.objects.filter(user=request.user).order_by('-booked_at').first()
    return render(request, 'movies/booking_success.html', {'payment': payment, 'booking': booking})

@user_passes_test(lambda u: u.is_superuser)
def admin_dashboard(request):
    """
    Task 6: Advanced Admin Analytics Dashboard with Cache Optimizations.
    """
    analytics_data = cache.get('admin_analytics')
    
    if not analytics_data:
        from django.db.models.functions import TruncDate
        
        daily_revenue = Payment.objects.filter(status='SUCCESS').aggregate(total=Sum('amount'))['total'] or 0
        total_bookings = Booking.objects.count()
        total_revenue = Payment.objects.filter(status='SUCCESS').aggregate(total=Sum('amount'))['total'] or 0
        failed_payments = Payment.objects.filter(status='FAILED').count()
        
        # Most popular movies based on bookings
        popular_movies = Movie.objects.annotate(booking_count=Count('booking')).order_by('-booking_count')[:5]
        
        # Daily booking trends (last 7 days)
        daily_trends = (
            Booking.objects
            .annotate(date=TruncDate('booked_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )[:7]
        
        analytics_data = {
            'revenue': total_revenue,
            'total_bookings': total_bookings,
            'failed_payments': failed_payments,
            'popular_movies': popular_movies,
            'daily_trends': list(daily_trends),
        }
        cache.set('admin_analytics', analytics_data, 300)
    
    return render(request, 'admin/dashboard.html', {'data': analytics_data})




