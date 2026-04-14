import uuid
from django.db import models
from django.contrib.auth.models import User 
from django.core.validators import RegexValidator
from django.utils import timezone

class Genre(models.Model):
    name = models.CharField(max_length=50, unique=True, db_index=True)

    def __str__(self):
        return self.name

class Language(models.Model):
    name = models.CharField(max_length=50, unique=True, db_index=True)

    def __str__(self):
        return self.name

class Movie(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    image = models.ImageField(upload_to="movies/")
    rating = models.DecimalField(max_digits=3, decimal_places=1)
    cast = models.TextField()
    description = models.TextField(blank=True, null=True)
    
    genres = models.ManyToManyField(Genre, related_name='movies', blank=True)
    languages = models.ManyToManyField(Language, related_name='movies', blank=True)
    
    # Task 3: Secure YouTube Embed
    trailer_url = models.URLField(
        blank=True, 
        null=True, 
        validators=[
            RegexValidator(
                regex=r'^(https?://)?(www\.)?(youtube\.com/embed/|youtu\.be/).+$',
                message="Only secure YouTube embed links are allowed."
            )
        ]
    )

    def __str__(self):
        return self.name

class Theater(models.Model):
    name = models.CharField(max_length=255)
    movie = models.ForeignKey(Movie,on_delete=models.CASCADE,related_name='theaters')
    time= models.DateTimeField()

    def __str__(self):
        return f'{self.name} - {self.movie.name} at {self.time}'

class Seat(models.Model):
    theater = models.ForeignKey(Theater,on_delete=models.CASCADE,related_name='seats')
    seat_number = models.CharField(max_length=10)
    is_booked=models.BooleanField(default=False)

    def __str__(self):
        return f'{self.seat_number} in {self.theater.name}'

class Booking(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    seat=models.OneToOneField(Seat,on_delete=models.CASCADE)
    movie=models.ForeignKey(Movie,on_delete=models.CASCADE)
    theater=models.ForeignKey(Theater,on_delete=models.CASCADE)
    booked_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f'Booking by{self.user.username} for {self.seat.seat_number} at {self.theater.name}'

# Task 5: Concurrency-Safe Seat Reservations
class SeatLock(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    seat = models.OneToOneField(Seat, on_delete=models.CASCADE, related_name='lock')
    expires_at = models.DateTimeField()

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"Lock for {self.seat.seat_number} by {self.user.username}"

# Task 4: Payment Gateway Integration
class Payment(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed')
    ]
    idempotency_key = models.CharField(max_length=255, unique=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stripe_charge_id = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional relation to booking if successful
    booking = models.OneToOneField(Booking, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Payment {self.idempotency_key} - {self.status}"