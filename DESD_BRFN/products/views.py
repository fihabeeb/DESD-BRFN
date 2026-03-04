from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import Product, ProductCategory

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
    category_id = request.GET.get('category')
    products = Product.objects.filter(availability__in=['available', 'in_season'])

    if category_id:
        products = products.filter(category_id=category_id)

    categories = ProductCategory.objects.filter(is_active=True)

    context = {
        'products': products,
        'categories': categories,
        'current_categories': category_id,
    }

    return render(request, 'products/product_list.html', context)

def product_detail(request, product_id):
    '''
    Show detailed product
    '''
    product = Product.objects.get(id=product_id)
    return render(request, 'products/product_detail.html', {
        'product': product
    })
