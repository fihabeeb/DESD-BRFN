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
    products = Product.objects.filter(
        availability='available',
        is_active=True,
        )

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

    recommended_products = []
    user_purchase_history = []
    if request.user.is_authenticated:
        try:
            from ml.recommendation.service_enhanced import EnhancedRecommendationService
            
            # Get user's purchase history
            from orders.models import OrderItem, OrderPayment
            
            # Fetch user's purchase history ordered by time
            user_orders = OrderPayment.objects.filter(
                user=request.user,
                payment_status='paid'
            ).order_by('created_at')
            
            # Extract product IDs from order items
            order_items = OrderItem.objects.filter(
                producer_order__payment__in=user_orders
            ).select_related('product').order_by('producer_order__payment__created_at')
            
            user_purchase_history = []  # List of (product_id, timestamp) tuples

            for item in order_items:
                # Get the timestamp from the payment
                timestamp = item.producer_order.payment.created_at
                
                # Repeat product ID based on quantity, each with the same timestamp
                for _ in range(item.quantity):
                    user_purchase_history.append((item.product.id, timestamp))

            # Sort by timestamp to ensure chronological order
            user_purchase_history.sort(key=lambda x: x[1])
            
            # Get recommendations if user has purchase history
            if user_purchase_history:
                recommendation_service = EnhancedRecommendationService()
                recommended_products = recommendation_service.get_recommendations(
                    user_id=request.user.id,
                    purchase_history_with_timestamps=user_purchase_history,
                    top_k=6  # Get top 6 recommendations
                )
                
                # Log for debugging (optional)
                print(f"Generated {len(recommended_products)} recommendations for user {request.user.id}")

        except Exception as e:
            print(f"Recommendation error for user {request.user.id}: {e}")
            recommended_products = []



    # products = products.order_by(category_id=category_id)
    context = {
        'products': products,
        'categories': categories,
        'current_categories': category_id,
        'search_query': search_query,
        'recommended_products': recommended_products,
        'user_purchase_history': user_purchase_history[:10],  # Last 10 purchases for display
        'has_recommendations': bool(recommended_products),
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
        'is_deleted': not product.is_active,
    }
    

    return render(request, 'products/product_detail.html', context)
