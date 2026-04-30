from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from mainApp.models import ProducerProfile
from django.contrib.auth import authenticate, login

from django.core.paginator import Paginator
from products.models import Product, ProductCategory
from products.forms import ProductForm
from mainApp.models import RegularUser
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import timezone, timedelta
from producers.forms import ProducerRegistrationForm, ProducerPersonalInfoForm, RestaurantRegistrationForm
from django.db.models import Q, Sum
from mainApp.decorators import producer_required
from orders.models import OrderPayment, OrderItem, OrderProducer
from products.models import Product

from django.contrib.auth import logout, update_session_auth_hash
from mainApp.models import Address

from mainApp.utils import geocode_postcode, haversine_miles
import logging



# Create your views here.
logger = logging.getLogger(__name__)
User = get_user_model()

def register_view(request):
    """
    Producer registration view using the form
    """
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('mainApp:home')

    if request.method == 'POST':
        try:
            form = ProducerRegistrationForm(request.POST)
            if form.is_valid():
                user = form.save()

                # login(request,user)

                messages.success(request, f"Welcome {user.username}! Your producer account has been created successfully.")
                messages.info(request, 'Please log in to access your producer dashboard.')
                return redirect('mainApp:producers:login')
            else:
                messages.error(request, 'Please correct the errors below.')

        except Exception as e:
            print (e)
            messages.error(request, 'db error')

    else:
        form = ProducerRegistrationForm()

    context = {
        'form': form,
        'title': 'Producer Registration'
    }
    return render(request, 'producers/register.html', context)


def register_restaurant_view(request):
    """TC-018: Registration view for restaurant / business accounts."""
    if request.user.is_authenticated:
        return redirect('mainApp:home')

    if request.method == 'POST':
        form = RestaurantRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                messages.success(request, f"Welcome {user.username}! Your restaurant account has been created.")
                messages.info(request, 'Please log in to access your dashboard.')
                return redirect('mainApp:customers:login')
            except Exception as e:
                logger.error(f"Restaurant registration error: {e}")
                messages.error(request, 'An error occurred. Please try again.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RestaurantRegistrationForm()

    return render(request, 'producers/register_restaurant.html', {
        'form': form,
        'title': 'Restaurant Registration'
    })


# =================
# product managment
# =================

@login_required
@producer_required
def myproduct_view(request):
    """
    Display products for the logged-in producer

    All the q functions dont work btw
    """
    producer_profile = request.user.producer_profile

    # Base queryset - filter products by this producer
    products = Product.objects.filter(
        producer=producer_profile,
        is_active=True,
        )

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

    return render(request, 'producers/management/myproduct.html', context)

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

    return render(request, 'producers/management/addproduct.html', context)

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

    return render(request, 'producers/management/addproduct.html', context)  # Reuse the same template

@login_required
@producer_required
def delete_product(request, product_id):
    if request.method == 'POST':

        product = get_object_or_404(Product, id=product_id)

        if product.producer != request.user.producer_profile:
            messages.error(request, "Permission denied.")
            return redirect('mainApp:producers:myproduct')

        product_name = product.name
        product.delete()
        messages.success(request, f'"{product_name}" deleted.')
        return redirect('mainApp:producers:myproduct')

    # return redirect('mainApp:producers:myproduct')
    return redirect('mainApp:producers:edit_product', product_id=product_id)


# =================
# order management
# =================

@login_required
@producer_required
def incoming_orders_view(request):
    """
    Display all orders that contain items assigned to this producer.
    Only shows this producer's items within each order.
    """
    producer_profile = request.user.producer_profile
    
    if not producer_profile:
        logger.warning(f"Producer profile missing for user {request.user.id}")
        return redirect('mainApp:home')
    
    # Get status filter from request
    status_filter = request.GET.get('status', '')
    
    # Get all OrderProducer records for this producer
    producer_orders = OrderProducer.objects.filter(
        producer=producer_profile
    ).exclude(
        order_status='pending'
    ).select_related('payment', 'payment__user').order_by('-created_at')

    revenue= 0
    for producer_order in producer_orders:
        if producer_order.order_status=="delivered":
            revenue += producer_order.producer_payout

    #calculate statistics
    stats = {
        'total': producer_orders.count(),
        'confirmed': producer_orders.filter(order_status='confirmed').count(),
        'preparing': producer_orders.filter(order_status='preparing').count(),
        'ready': producer_orders.filter(order_status='ready').count(),
        'delivered': producer_orders.filter(order_status='delivered').count(),
        'cancelled': producer_orders.filter(order_status='cancelled').count(),
        # 'total_revenue': sum(
        #     data['producer_subtotal'] for data in orders_data 
        #     if data['order'].order_status == 'delivered'
        # ),
        'total_revenue': revenue
    }
    
    # Apply status filter if provided
    if status_filter:
        producer_orders = producer_orders.filter(order_status=status_filter)
    
    # Build orders data with items and subtotals
    orders_data = []
    for producer_order in producer_orders:
        # Get items for this producer order
        order_items = OrderItem.objects.filter(
            producer_order=producer_order
        ).select_related('product')
        
        # Calculate subtotal for this producer's items
        producer_subtotal = sum(item.line_total for item in order_items)
        
        orders_data.append({
            'order': producer_order,
            'items': order_items,
            'producer_subtotal': producer_subtotal,
            'order_payment': producer_order.payment,  # Access the main payment
            'customer_name': producer_order.payment.user.get_full_name() or producer_order.payment.user.username,
            'customer_email': producer_order.payment.user.email,
            'delivery_date': producer_order.delivered_by,
            'customer_note': producer_order.customer_note,
        })
    
    # Pagination
    paginator = Paginator(orders_data, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    available_status_choices = [
        choice for choice in OrderProducer.ORDER_STATUS_CHOICES 
        if choice[0] != 'pending'
    ]
    
    context = {
        'page_obj': page_obj,
        'producer': producer_profile,
        'status_choices': available_status_choices,
        'current_status': status_filter,
        'stats': stats,
    }
    
    return render(request, 'producers/orders/incoming_orders.html', context)

@login_required
@producer_required
def update_order_status(request, order_id):
    """
    Update the status of a producer's order (e.g., confirmed, preparing, ready)
    """
    producer_profile = request.user.producer_profile
    
    # Get the producer order (ensure it belongs to this producer)
    producer_order = get_object_or_404(
        OrderProducer, 
        id=order_id, 
        producer=producer_profile
    )
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        
        if new_status in dict(OrderProducer.ORDER_STATUS_CHOICES):
            producer_order.order_status = new_status
            producer_order.save()
            
            # Log the status change
            logger.info(f"Producer {producer_profile.id} updated order {order_id} to {new_status}")
            
            # You could add notification here
            # send_order_status_notification(producer_order)
    
    return redirect('mainApp:producers:incoming_orders')


@login_required
@producer_required
def order_detail(request, order_id):
    """
    View detailed information for a specific producer order
    not in use
    """
    producer_profile = request.user.producer_profile
    print(producer_profile)

    producer_order = get_object_or_404(
        OrderProducer, 
        id=order_id, 
        producer=producer_profile
    )
    print(producer_order)
    
    # Get all items for this order
    order_items = OrderItem.objects.filter(
        producer_order=producer_order
    ).select_related('product')
    
    # Calculate subtotal
    producer_subtotal = sum(item.line_total for item in order_items)
    
    context = {
        'producer_order': producer_order,
        'order_payment': producer_order.payment,
        'items': order_items,
        'producer_subtotal': producer_subtotal,
        'status_choices': OrderProducer.ORDER_STATUS_CHOICES,
    }
    
    return render(request, 'producers/orders/details/order_details.html', context)


# =================
# quality scan (adv_ai/task2)
# =================

@login_required
@producer_required
def quality_scan_view(request):
    """
    AI quality scan page. GET renders the upload/camera UI.
    POST accepts an image, runs the Keras model, and returns a JSON score breakdown.
    """
    if request.method == 'POST':
        image = request.FILES.get('image')
        if not image:
            return JsonResponse({'success': False, 'error': 'No image provided.'}, status=400)

        try:
            from ml.predictor import predict
            from interactions.utils import log_interaction
            from interactions.models import UserInteraction
            prediction = predict(image)
            log_interaction(request, UserInteraction.QUALITY_SCAN, metadata={
                'overall_score': prediction.get('overall_score'),
                'grade': prediction.get('grade'),
                'breakdown': prediction.get('breakdown'),
                'labels': prediction.get('labels'),
            })
            return JsonResponse({'success': True, **prediction})

        except FileNotFoundError as e:
            return JsonResponse({'success': False, 'error': f'Model file missing: {e}'}, status=500)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Prediction failed: {e}'}, status=500)

    return render(request, 'producers/quality_scan.html')


# =================
# account management
# =================

@login_required
@producer_required
def personal_info_view(request):
    """Producer personal information management"""
    user = request.user

    # ====== DELETE ACCOUNT HANDLER ============
    if request.method == "POST" and "delete_account" in request.POST:
        user.delete()
        logout(request)
        messages.success(request, "Your account has been deleted successfully. We're sorry to see you go!")
        return redirect("mainApp:home")
    
    # GET OR CREATE PRODUCER PROFILE
    try:
        profile = ProducerProfile.objects.get(user=user)
    except ProducerProfile.DoesNotExist:
        # this should never happen
        print('profile does not exist')
        logger.info(f"Creating missing profile for user {user.username}")
        profile = ProducerProfile.objects.create(user=user)
        messages.info(request, "Producer profile was created. Please complete your farm details.")
    
    # GET ADDRESSES
    all_addresses = user.addresses.all().order_by('-is_default', '-created_at')
    
    # default address for producer is always farm type.
    default_address = all_addresses.filter(is_default=True).first()
    if not default_address:
        # Try to get any address
        default_address = all_addresses.first()
    
    # Get other addresses
    other_addresses = all_addresses.exclude(id=default_address.id)
    
    # PROCESS FORM
    if request.method == "POST":
        form = ProducerPersonalInfoForm(request.POST, user=user)
        
        if form.is_valid():
            try:
                user = form.save()
                
                # Handle session after password change
                if form.cleaned_data.get('password1'):
                    update_session_auth_hash(request, user)
                    messages.success(request, "Password updated successfully!")
                
                messages.success(request, "Your information has been updated successfully!")
                return redirect("mainApp:producers:personal_info")
                
            except Exception as e:
                logger.error(f"Error updating producer info: {e}", exc_info=True)
                messages.error(request, "An error occurred while updating your information. Please try again.")
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, error)
                    else:
                        field_label = field.replace('_', ' ').title()
                        messages.error(request, f"{field_label}: {error}")
    
    else:
        # GET request - populate initial data for form
        initial_data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": user.phone_number,
            "business_name": profile.business_name if profile else '',
        }
        
        form = ProducerPersonalInfoForm(user=user, initial=initial_data)
    
    context = {
        'form': form,
        'user': user,
        'profile': profile,
        # 'all_addresses': all_addresses,
        'default_address': default_address,
        'other_addresses': other_addresses,
    }
    
    return render(request, "profile/manage/personal_info.html", context)



@login_required
def producer_profile_view(request):
    """
    Producer dashboard: order history + stats
    """
    producer_profile = request.user.producer_profile
    # fetch latest order made by the user (NOT INCOMING ORDERS)
    latest_order = OrderPayment.objects.filter(
        user=request.user,
        payment_status='paid'
    ).order_by('-created_at').first()
    
    # stats card------------
    orderThisMonth = producer_profile.total_order_this_month
    total_orders_count = producer_profile.total_active_orders
    unique_customer = producer_profile.unique_customer_reached
    active_products = producer_profile.products_active_and_available

    stats_card = {
        'ordersThisMonth': orderThisMonth,
        'unfinishedOrders': total_orders_count,
        'uniqueCustomers': unique_customer,
        'activeProducts': active_products,
    }

    # build data for latest order made by the user.
    order_data = None
    if latest_order:
        # Build comprehensive order data
        order_data = {
            'order': latest_order,
            'total_amount': latest_order.total_amount,
            'created_at': latest_order.created_at,
            'payment_status': latest_order.payment_status,
            'shipping_address': latest_order.shipping_address,
            'global_notes': latest_order.global_delivery_notes,
            'producers': []
        }
        
        # Get all producer orders for this payment
        producer_orders = latest_order.producer_orders.select_related(
            'producer'
        ).prefetch_related(
            'order_items__product'
        ).all()

        for producer_order in producer_orders:
            producer_data = {
                'producer': producer_order.producer,
                'business_name': producer_order.producer.business_name if producer_order.producer else 'Unknown',
                'status': producer_order.get_order_status_display(),  
                'subtotal': producer_order.producer_subtotal,
                'delivery_date': producer_order.delivered_by,
                'customer_note': producer_order.customer_note,
                'items': []
            }
            
            # Get items for this producer order
            for item in producer_order.order_items.all():
                producer_data['items'].append({
                    'id': item.id,
                    'product_id': item.product.id if item.product else None,
                    'name': item.product_name,
                    'quantity': item.quantity,
                    'price': item.product_price,
                    'line_total': item.line_total,
                    'unit': item.unit
                })
            
            order_data['producers'].append(producer_data)
    
    context = {
        'stats': stats_card,
        'latest_order': latest_order,
        'order_data': order_data,
        'user_role': 'producer'
    }

    return render(request, "profile/profile_page.html", context)


# =============================================================================
# TC-019 — Surplus / Last-Minute Deals
# =============================================================================

@login_required
@producer_required
def mark_surplus(request, product_id):
    """Mark a product as a surplus deal or update an existing one."""
    from products.models import SurplusDeal, Product
    from django.utils import timezone as tz

    producer_profile = request.user.producer_profile
    product = get_object_or_404(Product, id=product_id, producer=producer_profile)

    existing = getattr(product, 'surplus_deal', None)

    if request.method == 'POST':
        discount = request.POST.get('discount_percent')
        hours = request.POST.get('expires_hours', 48)
        note = request.POST.get('note', '')
        best_before = request.POST.get('best_before_date') or None

        try:
            discount = int(discount)
            hours = int(hours)
            if discount < 10:
                messages.error(request, 'Discount must be at least 10%.')
                return redirect('mainApp:producers:mark_surplus', product_id=product_id)
            if hours < 1:
                messages.error(request, 'Expiry must be at least 1 hour.')
                return redirect('mainApp:producers:mark_surplus', product_id=product_id)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid discount or expiry value.')
            return redirect('mainApp:producers:mark_surplus', product_id=product_id)

        expires_at = tz.now() + timedelta(hours=hours)

        if existing:
            existing.discount_percent = discount
            existing.original_price = product.price
            existing.note = note
            existing.best_before_date = best_before
            existing.expires_at = expires_at
            existing.is_active = True
            existing.save()
            messages.success(request, f'"{product.name}" surplus deal updated.')
        else:
            SurplusDeal.objects.create(
                product=product,
                producer=producer_profile,
                discount_percent=discount,
                original_price=product.price,
                note=note,
                best_before_date=best_before,
                expires_at=expires_at,
                is_active=True,
            )
            messages.success(request, f'"{product.name}" marked as surplus deal.')

        return redirect('mainApp:producers:myproduct')

    context = {
        'product': product,
        'existing': existing,
    }
    return render(request, 'producers/surplus/mark_surplus.html', context)


@login_required
@producer_required
def remove_surplus(request, product_id):
    """Remove surplus deal status from a product."""
    from products.models import SurplusDeal, Product

    producer_profile = request.user.producer_profile
    product = get_object_or_404(Product, id=product_id, producer=producer_profile)
    deal = getattr(product, 'surplus_deal', None)
    if deal:
        deal.is_active = False
        deal.save(update_fields=['is_active'])
        messages.success(request, f'Surplus deal removed from "{product.name}".')
    return redirect('mainApp:producers:myproduct')


# =============================================================================
# TC-020 — Recipes & Farm Stories
# =============================================================================

@login_required
@producer_required
def content_dashboard(request):
    """Producer content management: recipes and farm stories."""
    from producers.models import Recipe, FarmStory

    producer_profile = request.user.producer_profile
    recipes = Recipe.objects.filter(producer=producer_profile).order_by('-created_at')
    stories = FarmStory.objects.filter(producer=producer_profile).order_by('-created_at')

    context = {
        'recipes': recipes,
        'stories': stories,
        'producer': producer_profile,
    }
    return render(request, 'producers/content/dashboard.html', context)


@login_required
@producer_required
def add_recipe(request):
    """Create a new recipe."""
    from producers.models import Recipe
    from products.models import Product

    producer_profile = request.user.producer_profile

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '')
        ingredients = request.POST.get('ingredients', '')
        instructions = request.POST.get('instructions', '')
        seasonal_tags = request.POST.get('seasonal_tags', '')
        linked_product_ids = request.POST.getlist('linked_products')
        image = request.FILES.get('image')

        if not title or not ingredients or not instructions:
            messages.error(request, 'Title, ingredients, and instructions are required.')
        else:
            recipe = Recipe.objects.create(
                producer=producer_profile,
                title=title,
                description=description,
                ingredients=ingredients,
                instructions=instructions,
                seasonal_tags=seasonal_tags,
                image=image,
            )
            if linked_product_ids:
                products = Product.objects.filter(
                    id__in=linked_product_ids, producer=producer_profile
                )
                recipe.linked_products.set(products)
            messages.success(request, f'Recipe "{title}" submitted for review.')
            return redirect('mainApp:producers:content')

    producer_products = Product.objects.filter(producer=producer_profile, is_active=True)
    return render(request, 'producers/content/add_recipe.html', {
        'producer': producer_profile,
        'producer_products': producer_products,
    })


@login_required
@producer_required
def edit_recipe(request, recipe_id):
    """Edit an existing recipe."""
    from producers.models import Recipe
    from products.models import Product

    producer_profile = request.user.producer_profile
    recipe = get_object_or_404(Recipe, id=recipe_id, producer=producer_profile)

    if request.method == 'POST':
        recipe.title = request.POST.get('title', recipe.title).strip()
        recipe.description = request.POST.get('description', recipe.description)
        recipe.ingredients = request.POST.get('ingredients', recipe.ingredients)
        recipe.instructions = request.POST.get('instructions', recipe.instructions)
        recipe.seasonal_tags = request.POST.get('seasonal_tags', recipe.seasonal_tags)
        if request.FILES.get('image'):
            recipe.image = request.FILES['image']
        recipe.moderation_status = 'pending'  # Re-submit for review on edit
        recipe.save()

        linked_product_ids = request.POST.getlist('linked_products')
        if linked_product_ids:
            products = Product.objects.filter(id__in=linked_product_ids, producer=producer_profile)
            recipe.linked_products.set(products)
        else:
            recipe.linked_products.clear()

        messages.success(request, f'Recipe "{recipe.title}" updated and submitted for review.')
        return redirect('mainApp:producers:content')

    producer_products = Product.objects.filter(producer=producer_profile, is_active=True)
    return render(request, 'producers/content/add_recipe.html', {
        'producer': producer_profile,
        'producer_products': producer_products,
        'recipe': recipe,
        'is_edit': True,
    })


@login_required
@producer_required
def delete_recipe(request, recipe_id):
    """Delete a recipe."""
    from producers.models import Recipe

    producer_profile = request.user.producer_profile
    recipe = get_object_or_404(Recipe, id=recipe_id, producer=producer_profile)
    if request.method == 'POST':
        name = recipe.title
        recipe.delete()
        messages.success(request, f'Recipe "{name}" deleted.')
    return redirect('mainApp:producers:content')


@login_required
@producer_required
def add_farm_story(request):
    """Create a new farm story."""
    from producers.models import FarmStory, FarmStoryImage

    producer_profile = request.user.producer_profile

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '')

        if not title or not body:
            messages.error(request, 'Title and body are required.')
        else:
            story = FarmStory.objects.create(
                producer=producer_profile,
                title=title,
                body=body,
            )
            for image in request.FILES.getlist('images'):
                FarmStoryImage.objects.create(story=story, image=image)
            messages.success(request, f'Farm story "{title}" submitted for review.')
            return redirect('mainApp:producers:content')

    return render(request, 'producers/content/add_farm_story.html', {
        'producer': producer_profile,
    })


@login_required
@producer_required
def delete_farm_story(request, story_id):
    """Delete a farm story."""
    from producers.models import FarmStory

    producer_profile = request.user.producer_profile
    story = get_object_or_404(FarmStory, id=story_id, producer=producer_profile)
    if request.method == 'POST':
        name = story.title
        story.delete()
        messages.success(request, f'Farm story "{name}" deleted.')
    return redirect('mainApp:producers:content')
