from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.views import LoginView as AuthLoginView
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from Base_App.models import BookTable, AboutUs, Feedback, ItemList, Items, Cart


@never_cache
def add_to_cart(request):
    """Add item to cart - handles both session and database cart"""
    if request.method == 'POST':
        item_id = request.POST.get('item_id')

        if not item_id:
            return JsonResponse({'error': 'Item ID is required'}, status=400)

        try:
            item = get_object_or_404(Items, id=item_id)
        except:
            return JsonResponse({'error': 'Item not found'}, status=404)

        if request.user.is_authenticated:
            # For authenticated users, use database cart
            cart_item, created = Cart.objects.get_or_create(
                user=request.user,
                item=item,
                defaults={'quantity': 1}
            )

            if not created:
                cart_item.quantity += 1
                cart_item.save()

            return JsonResponse({
                'message': 'Item added to cart',
                'quantity': cart_item.quantity
            })
        else:
            # For anonymous users, use session cart
            cart = request.session.get('cart', {})

            if item_id in cart:
                cart[item_id]['quantity'] += 1
            else:
                cart[item_id] = {
                    'name': item.Item_name,
                    'price': float(item.Price),
                    'quantity': 1
                }

            request.session['cart'] = cart
            request.session.modified = True

            return JsonResponse({
                'message': 'Item added to cart',
                'cart': cart
            })

    return JsonResponse({'error': 'Invalid request method'}, status=405)


def get_cart_items(request):
    """Get cart items for current user"""
    if request.user.is_authenticated:
        cart_items = Cart.objects.filter(
            user=request.user).select_related('item')
        items = []
        total_amount = 0

        for cart_item in cart_items:
            item_total = cart_item.quantity * cart_item.item.Price
            total_amount += item_total
            items.append({
                'id': cart_item.item.id,
                'name': cart_item.item.Item_name,
                'quantity': cart_item.quantity,
                'price': float(cart_item.item.Price),
                'total': float(item_total),
            })

        return JsonResponse({
            'items': items,
            'total_amount': float(total_amount),
            'item_count': len(items)
        })
    else:
        # Return session cart for anonymous users
        cart = request.session.get('cart', {})
        items = []
        total_amount = 0

        for item_id, item_data in cart.items():
            item_total = item_data['quantity'] * item_data['price']
            total_amount += item_total
            items.append({
                'id': item_id,
                'name': item_data['name'],
                'quantity': item_data['quantity'],
                'price': item_data['price'],
                'total': item_total,
            })

        return JsonResponse({
            'items': items,
            'total_amount': total_amount,
            'item_count': len(items)
        })


class LoginView(AuthLoginView):
    """Custom login view with proper error handling"""
    template_name = 'login.html'
    form_class = AuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        # Check if there's a 'next' parameter
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url

        # Check if the user is an admin
        if self.request.user.is_staff:
            return reverse_lazy('admin:index')

        # Default redirect to home
        return reverse_lazy('Home')

    def form_valid(self, form):
        """Handle successful login"""
        user = form.get_user()

        # Transfer session cart to user cart if exists
        if hasattr(self.request, 'session') and 'cart' in self.request.session:
            session_cart = self.request.session['cart']
            for item_id, item_data in session_cart.items():
                try:
                    item = Items.objects.get(id=item_id)
                    cart_item, created = Cart.objects.get_or_create(
                        user=user,
                        item=item,
                        defaults={'quantity': item_data['quantity']}
                    )
                    if not created:
                        cart_item.quantity += item_data['quantity']
                        cart_item.save()
                except Items.DoesNotExist:
                    continue

            # Clear session cart
            del self.request.session['cart']

        messages.success(self.request, f'Welcome back, {user.username}!')
        return super().form_valid(form)

    def form_invalid(self, form):
        """Handle failed login"""
        messages.error(
            self.request, 'Invalid username or password. Please try again.')
        return super().form_invalid(form)


@never_cache
def LogoutView(request):
    """Handle user logout"""
    if request.user.is_authenticated:
        username = request.user.username
        logout(request)
        messages.success(
            request, f'Goodbye, {username}! You have been logged out successfully.')
    return redirect('Home')


def SignupView(request):
    """Handle user registration"""
    if request.user.is_authenticated:
        return redirect('Home')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Log the user in immediately after signup
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)

            if user:
                login(request, user)
                messages.success(
                    request, f'Welcome to FoodLoops, {username}! Your account has been created successfully.')
                return redirect('Home')
        else:
            # Add form errors to messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = UserCreationForm()

    return render(request, 'register.html', {'form': form})


def HomeView(request):
    """Home page view with items and reviews"""
    try:
        items = Items.objects.select_related('Category').all()
        categories = ItemList.objects.all()
        reviews = Feedback.objects.all().order_by('-id')[:5]

        context = {
            'items': items,
            'categories': categories,
            'reviews': reviews
        }

        # Add cart count for authenticated users
        if request.user.is_authenticated:
            cart_count = Cart.objects.filter(user=request.user).count()
            context['cart_count'] = cart_count

        return render(request, 'home.html', context)
    except Exception as e:
        messages.error(request, 'An error occurred while loading the page.')
        return render(request, 'home.html', {'items': [], 'categories': [], 'reviews': []})


def AboutView(request):
    """About page view"""
    try:
        about_data = AboutUs.objects.all()
        return render(request, 'about.html', {'data': about_data})
    except Exception as e:
        messages.error(
            request, 'An error occurred while loading the about page.')
        return render(request, 'about.html', {'data': []})


def MenuView(request):
    """Menu page view"""
    try:
        items = Items.objects.select_related('Category').all()
        categories = ItemList.objects.all()

        context = {
            'items': items,
            'categories': categories
        }

        return render(request, 'menu.html', context)
    except Exception as e:
        messages.error(request, 'An error occurred while loading the menu.')
        return render(request, 'menu.html', {'items': [], 'categories': []})


def BookTableView(request):
    """Book table view with form handling"""
    google_maps_api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '')

    if request.method == 'POST':
        name = request.POST.get('user_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('user_email', '').strip()
        total_person = request.POST.get('total_person', '').strip()
        booking_date = request.POST.get('booking_data', '').strip()

        # Validation
        errors = []

        if not name:
            errors.append('Name is required.')

        if not phone_number or len(phone_number) != 10 or not phone_number.isdigit():
            errors.append('Please enter a valid 10-digit phone number.')

        if not email:
            errors.append('Email is required.')

        if not total_person or total_person == '0':
            errors.append('Please select number of persons.')

        if not booking_date:
            errors.append('Booking date is required.')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'book_table.html', {'google_maps_api_key': google_maps_api_key})

        try:
            # Save booking
            booking = BookTable(
                Name=name,
                Phone_number=int(phone_number),
                Email=email,
                Total_person=int(total_person),
                Booking_date=booking_date
            )
            booking.save()

            # Send confirmation email
            try:
                subject = 'Booking Confirmation - FoodLoops'
                message = f"""Hello {name},

Your table booking has been successfully received!

Booking Details:
- Name: {name}
- Phone: {phone_number}
- Email: {email}
- Number of Persons: {total_person}
- Booking Date: {booking_date}

We will contact you shortly to confirm your reservation.

Thank you for choosing FoodLoops!

Best regards,
FoodLoops Team"""

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                # Email failed, but booking was saved
                messages.warning(
                    request, 'Booking saved but confirmation email could not be sent.')

            messages.success(
                request, 'Booking request submitted successfully! We will contact you shortly.')
            return redirect('book_table')

        except Exception as e:
            messages.error(
                request, 'An error occurred while processing your booking. Please try again.')

    return render(request, 'book_table.html', {'google_maps_api_key': google_maps_api_key})


def FeedbackView(request):
    """Feedback submission view"""
    if request.method == 'POST':
        name = request.POST.get('User_name', '').strip()
        feedback_text = request.POST.get('Description', '').strip()
        rating = request.POST.get('Rating', '').strip()
        image = request.FILES.get('Selfie')

        # Validation
        errors = []

        if not name:
            errors.append('Name is required.')
        elif len(name) < 2:
            errors.append('Name must be at least 2 characters long.')

        if not feedback_text:
            errors.append('Feedback description is required.')
        elif len(feedback_text) < 10:
            errors.append(
                'Feedback description must be at least 10 characters long.')

        if not rating:
            errors.append('Please select a rating.')
        elif rating not in ['1', '2', '3', '4', '5']:
            errors.append('Please select a valid rating.')

        # Validate image if uploaded
        if image:
            # Check file size (5MB limit)
            if image.size > 5 * 1024 * 1024:
                errors.append('Image file size must be less than 5MB.')

            # Check file type
            allowed_types = ['image/jpeg',
                             'image/jpg', 'image/png', 'image/gif']
            if image.content_type not in allowed_types:
                errors.append(
                    'Please upload a valid image file (JPEG, PNG, or GIF).')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'feedback.html')

        try:
            # Save feedback
            feedback = Feedback(
                User_name=name,
                Description=feedback_text,
                Rating=int(rating),
                Image=image
            )
            feedback.save()

            # Send notification email to admin (optional)
            try:
                from django.core.mail import send_mail
                from django.conf import settings

                subject = f'New Feedback Received - Rating: {rating}/5'
                message = f"""New feedback received:

Name: {name}
Rating: {rating}/5
Feedback: {feedback_text}

Please check the admin panel for more details."""

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [settings.DEFAULT_FROM_EMAIL],  # Send to admin
                    fail_silently=True,
                )
            except Exception as e:
                # Email failed, but feedback was saved
                pass

            messages.success(
                request, 'Thank you for your feedback! We appreciate your input.')
            return redirect('feedback')

        except Exception as e:
            messages.error(
                request, 'An error occurred while submitting your feedback. Please try again.')

            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error saving feedback: {str(e)}')

    return render(request, 'feedback.html')
