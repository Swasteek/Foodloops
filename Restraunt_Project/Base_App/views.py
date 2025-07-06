from django.shortcuts import render
from django.http import JsonResponse

# Create your views here.


def HomeView(request):
    return render(request, 'home.html')


def AboutView(request):
    return render(request, 'about.html')


def MenuView(request):
    return render(request, 'menu.html')


def BookTableView(request):
    return render(request, 'book_table.html')


def FeedbackView(request):
    return render(request, 'feedback.html')


def get_cart_items(request):
    # Placeholder for cart functionality
    # You can implement actual cart logic here later
    return JsonResponse({'items': []})
