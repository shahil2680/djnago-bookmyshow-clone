import threading
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

class EmailThread(threading.Thread):
    def __init__(self, subject, html_content, recipient_list, from_email=None):
        self.subject = subject
        self.recipient_list = recipient_list
        self.html_content = html_content
        self.from_email = from_email or 'no-reply@bookmyshow-clone.com'
        threading.Thread.__init__(self)

    def run(self):
        try:
            text_content = strip_tags(self.html_content)
            msg = EmailMultiAlternatives(
                subject=self.subject,
                body=text_content,
                from_email=self.from_email,
                to=self.recipient_list
            )
            msg.attach_alternative(self.html_content, "text/html")
            msg.send()
            logger.info(f"Successfully sent ticket confirmation email to {self.recipient_list}")
        except Exception as e:
            # We log the failure but do not crash the booking thread
            logger.error(f"Failed to send email to {self.recipient_list}. Error: {str(e)}")

def send_booking_email_task(booking_obj):
    """
    Spawns a background thread to render the template and send the email
    """
    context = {
        'user': booking_obj.user,
        'movie': booking_obj.movie,
        'theater': booking_obj.theater,
        'seat': booking_obj.seat,
        'booking': booking_obj,
    }
    
    html_content = render_to_string('emails/ticket.html', context)
    
    # Spawn thread to send email without blocking the HTTP response
    EmailThread(
        subject=f"Tickets Confirmed! {booking_obj.movie.name}",
        html_content=html_content,
        recipient_list=[booking_obj.user.email]
    ).start()
