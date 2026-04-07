# recommendation/management/commands/generate_synthetic_orders.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
from decimal import Decimal

from mainApp.models import CustomerProfile
from products.models import Product
from orders.models import OrderPayment, OrderProducer, OrderItem


class Command(BaseCommand):
    help = "Generate synthetic order data for AI recommendations"

    def handle(self, *args, **kwargs):
        customers = CustomerProfile.objects.all()
        products = list(Product.objects.filter(availability='available'))

        if not customers.exists() or not products:
            self.stdout.write(self.style.ERROR("No customers or products found"))
            return

        for customer in customers:
            user = customer.user

            favourite_products = random.sample(products, min(5, len(products)))

            num_orders = random.randint(10, 30)

            for _ in range(num_orders):
                days_ago = random.randint(0, 90)
                created_at = timezone.now() - timedelta(days=days_ago)

                order = OrderPayment.objects.create(
                    customer=customer,
                    user=user,
                    payment_status='paid',
                    total_amount=Decimal("0.00"),
                    created_at=created_at
                )

                order_total = Decimal("0.00")

                producer_map = {}

                num_items = random.randint(1, 5)

                for _ in range(num_items):
                    if random.random() < 0.7:
                        product = random.choice(favourite_products)
                    else:
                        product = random.choice(products)

                    producer = product.producer

                    if not producer:
                        continue

                    if producer.id not in producer_map:
                        producer_map[producer.id] = OrderProducer.objects.create(
                            payment=order,
                            producer=producer,
                            producer_subtotal=Decimal("0.00"),
                            order_status='confirmed',
                        )

                    producer_order = producer_map[producer.id]

                    quantity = random.randint(1, 3)
                    price = product.price

                    item = OrderItem.objects.create(
                        producer_order=producer_order,
                        product=product,
                        product_name=product.name,
                        product_price=price,
                        quantity=quantity,
                        unit=product.unit
                    )

                    line_total = price * quantity
                    order_total += line_total
                    producer_order.producer_subtotal += line_total

                for po in producer_map.values():
                    po.save()

                order.total_amount = order_total
                order.save()

        self.stdout.write(self.style.SUCCESS("Synthetic orders generated successfully"))