from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import Product, ProductCategory
from django.db.models import Q
from django.contrib.postgres.search import TrigramSimilarity
from mainApp.utils import haversine_miles, BRISTOL_LAT, BRISTOL_LON


@login_required
def add_product(request):
    '''
    Allow producer to list new products
    TC-003
    '''

    if request.method == 'POST':
        product = Product(
            name=request.POST['name'],
            description=request.POST['description'],
            price=request.POST['price'],
            unit=request.POST['unit'],
            stock_quantity=request.POST['stock_quantity'],
            category_id=request.POST['category'],
            is_organic=request.POST.get('is_organic', False),
            availability=request.POST['availability'],

            producer = request.user.producer
        )

        if 'image' in request.FILES:
            product.image = request.FILES['image']

        product.save()
        return request('product_list')
    
    categories = ProductCategory.objects.filter(is_active=True)
    context = {
        'categories': categories,
        'availability_choices': Product.AVAILABILITY_CHOICES
    }
    return render(request, 'products/add_product.html', context)


def product_list(request):
    '''
    Display products for customers to browse
    '''
    products = Product.objects.filter(availability='available')

    search_query = request.GET.get('q', '')
    if search_query:
        # Check if search query contains "organic"
        search_lower = search_query.lower()
        is_organic_search = 'organic' in search_lower
        
        # Build the base search
        products = products.annotate(
            similarity=TrigramSimilarity('name', search_query)
        )
        
        # Create filter conditions
        search_filter = Q(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query) |
            Q(similarity__gt=0.125)
        )
        
        # If searching for organic, add organic filter
        if is_organic_search:
            search_filter &= Q(is_organic=True)
            
            # Also remove "organic" from the search term for better matching
            clean_query = search_lower.replace('organic', '').strip()
            if clean_query:
                # Add search for the remaining terms
                search_filter |= Q(
                    Q(name__icontains=clean_query) |
                    Q(description__icontains=clean_query) |
                    Q(category__name__icontains=clean_query)
                )
        
        products = products.filter(search_filter).order_by('-similarity')

            # TODO:
            ## add producer name when available

    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
    categories = ProductCategory.objects.filter(is_active=True)

    # products = products.order_by(category_id=category_id)
    context = {
        'products': products,
        'categories': categories,
        'current_categories': category_id,
        'search_query': search_query,
    }

    return render(request, 'products/product_list.html', context)

def product_detail(request, product_id):
    '''
    Show detailed product
    '''
    product = Product.objects.get(id=product_id)

    if request.user.is_authenticated:
        user_lat, user_long = request.user.get_default_address_coordinates()
    else:
        user_lat, user_long = BRISTOL_LAT,BRISTOL_LON


    food_miles = product.get_food_miles(user_lat, user_long)

    context = {
        'product': product,
        'food_miles': food_miles,
        'user_is_authenticated': request.user.is_authenticated,
        'user_has_coordinates': bool(user_lat and user_long),
    }
    

    return render(request, 'products/product_detail.html', context)
