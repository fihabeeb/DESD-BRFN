from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth import get_user_model
from mainApp.models import ProducerProfile
from django.contrib.auth import authenticate, login

from django.core.paginator import Paginator
from products.models import Product, ProductCategory
from products.forms import ProductForm
from mainApp.models import RegularUser
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import timezone
from producers.forms import ProducerRegistrationForm
from django.db.models import Q
from mainApp.decorators import producer_required

# Create your views here.

User = get_user_model()

# TODO: function below to remove after testing
# def login_view(request):
#     if request.method == 'POST':
#         username = request.POST['username']
#         password = request.POST['password']
#         user = authenticate(request, username=username, password=password)
#         if user:
#             login(request, user)
#             return redirect('home')
#         else:
#             return render(request, 'producer_login.html', {'error': 'Invalid credentials'})
#     return render(request, 'producer_login.html')


# def register_view(request):
#     if request.method == 'POST':
#         username = request.POST['username']
#         email = request.POST['email']
#         password1 = request.POST['password1']
#         password2 = request.POST['password2']
#         if password1 != password2:
#             return render(request, 'producer_register.html', {'error': 'Passwords do not match'})
#         if User.objects.filter(username=username).exists():
#             return render(request, 'producer_register.html', {'error': 'Username already taken'})
#         user = User.objects.create_user(username=username, email=email, password=password1)
#         user.role = 'producer'
#         user.save()
#         ProducerProfile.objects.create(user=user)
#         return redirect('producer_login')
#     return render(request, 'producer_register.html')

def register_view(request):
    """
    Producer registration view using the form
    """
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('mainApp:home')

    if request.method == 'POST':
        form = ProducerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Optional: Auto-login after registration
            # login(request, user)

            messages.success(request, f"Welcome {user.username}! Your producer account has been created successfully.")
            messages.info(request, 'Please log in to access your producer dashboard.')
            return redirect('mainApp:producers:login')
        else:
            # Form errors will be displayed in the template
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProducerRegistrationForm()

    context = {
        'form': form,
        'title': 'Producer Registration'
    }
    return render(request, 'producers/register.html', context)

@login_required
@producer_required
def myproduct_view(request):
    """
    Display products for the logged-in producer

    All the q functions dont work btw
    """
    producer_profile = request.user.producer_profile

    # Base queryset - filter products by this producer
    products = Product.objects.filter(producer=producer_profile)

    # Apply filters from request.GET
    # Filter by availability (TC-003, TC-016)
    availability = request.GET.get('availability')
    if availability:
        products = products.filter(availability=availability)

    # Filter by organic (TC-014)
    if request.GET.get('organic') == 'true':
        products = products.filter(is_organic=True)

    # Low stock filter (TC-023)
    if request.GET.get('low_stock') == 'true':
        products = products.filter(stock_quantity__lt=10, stock_quantity__gt=0)

    # Out of stock filter
    if request.GET.get('out_of_stock') == 'true':
        products = products.filter(stock_quantity=0)

    # In season filter (TC-016)
    if request.GET.get('in_season') == 'true':
        current_month = timezone.now().month
        products = products.filter(
            Q(season_start__lte=current_month, season_end__gte=current_month) |
            Q(availability='in_season')
        )

    # Search by name or description (TC-005)
    search = request.GET.get('search')
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search)
        )

    # Sorting
    sort = request.GET.get('sort', '-created_at')  # Default: newest first
    valid_sort_fields = [
        'name', '-name',
        'price', '-price',
        'stock_quantity', '-stock_quantity',
        'created_at', '-created_at',
        'availability', '-availability'
    ]
    if sort in valid_sort_fields:
        products = products.order_by(sort)

    # Pagination
    paginator = Paginator(products, 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Prepare context
    context = {
        'page_obj': page_obj,
        'products': page_obj,  # For backward compatibility
        'producer': producer_profile,
        'availability_choices': Product.AVAILABILITY_CHOICES,
        'current_filters': request.GET.dict(),
        'sort': sort,
        'search': search,
    }

    return render(request, 'producers/myproduct.html', context)

@login_required
@producer_required
def addproduct_view(request):
    """
    View for producers to add new products (TC-003)
    """
    producer_profile = request.user.producer_profile

    if request.method == 'POST':
        """
        username = request.POST['username']
        email = request.POST['email']
        password1 = request.POST['password1']
        password2 = request.POST['password2']
        if password1 != password2:
            return render(request, 'producer_register.html', {'error': 'Passwords do not match'})
        if User.objects.filter(email=email).exists():
            return render(request, 'producer_register.html', {'error': 'Username already taken'})
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.role = 'producer'
        user.save()
        ProducerProfile.objects.create(user=user)
        return redirect('producer_login')
    return render(request, 'producer_register.html')
        """
        form = ProductForm(request.POST, request.FILES, producer=producer_profile)

        if form.is_valid():
            product = form.save()

            # Success message
            messages.success(request, f'Product "{product.name}" has been successfully listed!')

            # Check for low stock warning (TC-023)
            if product.is_low_stock:
                messages.warning(request, f'Note: "{product.name}" has low stock. Consider adding more inventory.')

            # Redirect to product list or product detail
            return redirect('mainApp:producers:myproduct')  # or 'producer_product_detail' with product.id
        else:
            # Form errors will be displayed in template
            messages.error(request, 'Please correct the errors below.')
    else:
        # Pre-populate with defaults if needed
        initial_data = {
            'availability': 'available',
            'stock_quantity': 0,
        }
        form = ProductForm(producer=producer_profile, initial=initial_data)

    # Get categories for reference
    categories = ProductCategory.objects.filter(is_active=True)

    context = {
        'form': form,
        'categories': categories,
        'producer': producer_profile,
        'is_edit': False,
        'month_choices': Product.MONTH_CHOICES,
        'availability_choices': Product.AVAILABILITY_CHOICES,
    }

    return render(request, 'producers/addproduct.html', context)

@login_required
@producer_required
def product_edit_view(request, product_id):
    producer_profile = request.user.producer_profile

    # Get the product and verify ownership
    product = get_object_or_404(
        Product,
        id=product_id,
        producer=producer_profile  # This ensures the product belongs to this producer
    )

    if request.method == 'POST':
        # Pass the existing product instance to the form
        form = ProductForm(
            request.POST,
            request.FILES,  # For image uploads
            instance=product,  # This tells Django to update existing product
            producer=producer_profile
        )

        if form.is_valid():
            updated_product = form.save()

            # Check if stock changed and is now low (TC-023)
            if updated_product.is_low_stock:
                messages.warning(
                    request,
                    f'"{updated_product.name}" has low stock ({updated_product.stock_quantity} remaining).'
                )

            messages.success(request, f'"{updated_product.name}" has been updated successfully!')
            return redirect('mainApp:producers:myproduct')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # GET request - populate form with existing product data
        form = ProductForm(
            instance=product,
            producer=producer_profile
        )

    context = {
        'form': form,
        'product': product,  # Pass the product for template use
        'producer': producer_profile,
        'is_edit': True,  # Flag for template to adjust UI
        'month_choices': Product.MONTH_CHOICES,
        'availability_choices': Product.AVAILABILITY_CHOICES,
    }

    return render(request, 'producers/addproduct.html', context)  # Reuse the same template
