import random
import string

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404, redirect, render
from django.template.base import kwarg_re
from django.views.generic import DetailView, ListView, View
from requests.api import post
from stripe.api_resources import coupon

from core.forms import PaymentForm, RequestRefundForm

from .forms import AddCouponForm, CheckoutForm
from .models import Address, Coupon, Item, Order, OrderItem, Payment, Refund,UserProfile

stripe.api_key = settings.STRIPE_KEY


def create_ref_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=20))


def home(request):
    item_list = Item.objects.all()
    context = {}
    return render(request, "home.html", context)


class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        context = {'order': order}
        try:
            userprofile = UserProfile.objects.get(user=self.request.user)
            if userprofile.one_click_purchasing:
                cards = stripe.Customer.list_sources(userprofile.stripe_customer_id,object='card',limit=3)
                cards_list = cards['data']
                if len(cards_list) >0:
                    context.update({'card':cards_list[0]})
        except ObjectDoesNotExist:
            pass
        return render(self.request, 'payment.html', context)

    def post(self, *args, **kwargs):
        print(' in patment view POST')
        form = PaymentForm(self.request.POST)
        print(self.request.POST)
        order = Order.objects.get(user=self.request.user, ordered=False)

        if form.is_valid():
            print('FORM VALID')
            stripeToken = form.cleaned_data.get('stripeToken');
            save_card_info = form.cleaned_data.get('save_card_info');
            use_default_card = form.cleaned_data.get('use_default_card');
            amount = int(order.get_total() * 100)
            print('stripeToken = ',  stripeToken)
            print('save_card_info = ',  save_card_info)
            print('use_default_card = ',  use_default_card)

            userprofile = UserProfile.objects.get(user=self.request.user)

            if save_card_info:
                if not userprofile.stripe_customer_id:
                    customer = stripe.Customer.create(source=stripeToken,email=userprofile.user.email,)
                    userprofile.stripe_customer_id = customer['id']
                    userprofile.one_click_purchasing = True
                else:
                    stripe.Customer.create_source(userprofile.stripe_customer_id,source=stripeToken)
            
        try:
            if use_default_card:
                charge = stripe.Charge.create(amount=amount,currency="usd",customer=userprofile.stripe_customer_id)
            else:
                charge = stripe.Charge.create(amount=amount,currency="usd",source=stripeToken)

            payment = Payment()
            payment.stripe_charge_id = charge['id']
            payment.user = self.request.user
            payment.amount = order.get_total()
            payment.save()

            order_items = order.items.all()
            order_items.update(ordered=True)
            for item in order_items:
                item.save()

            order.ordered = True
            order.ref_code = create_ref_code()

            # for order_item in order.items.all():

            order.payment = payment
            order.save()
            messages.success(self.request, 'order was successful')

            return redirect('/')

        except stripe.error.CardError as e:
            messages.error(self.request,'CardError')

        except stripe.error.RateLimitError as e:
            messages.error(self.request,'RateLimitError')
        except stripe.error.InvalidRequestError as e:
            messages.error(self.request,'InvalidRequestError')
        except stripe.error.AuthenticationError as e:
            messages.error(self.request,'AuthenticationError')
        except stripe.error.APIConnectionError as e:
            messages.error(self.request,'APIConnectionError')
        except stripe.error.StripeError as e:
            messages.error(self.request,'StripeError')
        except Exception as e:
            messages.error(self.request,e.error)

        return redirect('/')


class AddCoupon(View):
    def post(self, *args, **kwargs):

        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
        except ObjectDoesNotExist:
            print('no active order')
            return redirect('checkout')

        couponform = AddCouponForm(self.request.POST or None)
        if couponform.is_valid():
            print('couponform is valid')
            code = couponform.cleaned_data.get('code')

            try:
                coupon = Coupon.objects.get(code=code)
            except ObjectDoesNotExist:
                print('invalid coupon code')
                return redirect('checkout')
            order.coupon = coupon
            order.save()
            return redirect('checkout')


class RemoveCoupon(View):
    def get(self, *args, **kwargs):
        form = CheckoutForm()
        couponform = AddCouponForm()
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            order.coupon.delete()
            # coupon.delete()
            order.save()
        except ObjectDoesNotExist:
            print('no active order')
            return redirect('checkout')
        context = {'form': form, 'order': order, 'couponform': couponform}
        return render(self.request, "checkout.html", context)


def remove_coupon(request):
    order = Order.objects.get(user=request.user, ordered=False)
    order.coupon = None
    order.save()
    return redirect('checkout')


class CheckOut(View):
    def get(self, *args, **kwargs):
        form = CheckoutForm()
        couponform = AddCouponForm()
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
        except ObjectDoesNotExist:
            print('no active order')
            return redirect('checkout')
        context = {'form': form, 'order': order, 'couponform': couponform}
        return render(self.request, "checkout.html", context)

    def post(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
        except ObjectDoesNotExist:
            print('no active order')
            return redirect('order-summary')

        form = CheckoutForm(self.request.POST or None)
        print(self.request.POST)
        if form.is_valid():
            print(form.cleaned_data)
            shipping_address1 = form.cleaned_data.get('shipping_address1')
            shipping_address2 = form.cleaned_data.get('shipping_address2')
            shipping_country = form.cleaned_data.get('shipping_country')
            shipping_zip = form.cleaned_data.get('shipping_zip')
            save_as_default_shipping = form.cleaned_data.get('save_as_default_shipping')
            use_default_shipping = form.cleaned_data.get('use_default_shipping')

            billing_address1 = form.cleaned_data.get('billing_address1')
            billing_address2 = form.cleaned_data.get('billing_address2')
            billing_country = form.cleaned_data.get('billing_country')
            billing_zip = form.cleaned_data.get('billing_zip')
            save_as_default_billing = form.cleaned_data.get('save_as_default_billing')
            payment_option = form.cleaned_data.get('payment_option')
            use_default_billing = form.cleaned_data.get('use_default_billing')



            if save_as_default_shipping and order.shipping_address is not None:
                prev_default_shipping_add = order.shipping_address
                prev_default_shipping_add.default = False
                prev_default_shipping_add.save()

            if save_as_default_billing and order.billing_address is not None:
                prev_default_billing_add = order.billing_address
                prev_default_billing_add.default = False
                prev_default_billing_add.save()
            

            if use_default_shipping :
                order.shipping_address = order.get_user_default_shipping_address()
            else:
                shipping_address = Address(user=self.request.user, street_address=shipping_address1,
                                                apartment_address=shipping_address2, country=shipping_country, zip_code=shipping_zip,address_type='S',default=save_as_default_shipping)
                shipping_address.save()
                order.shipping_address = shipping_address
            
            if use_default_billing :
                order.billing_address = order.get_user_default_billing_address()
            else:
                billing_address = Address(user=self.request.user, street_address=billing_address1,
                                                apartment_address=billing_address2, country=billing_country, zip_code=billing_zip,address_type='B',default=save_as_default_billing)
                billing_address.save()
                order.billing_address = billing_address
            
            order.save()

            if payment_option == 'S':
                return redirect('payment', payment_option='stripe')
            elif payment_option == 'P':
                return redirect('payment', payment_option='paypal')

        print('Checkout failed,invalid form')
        return redirect('checkout')


def products(request):
    context = {}
    return render(request, "product.html", context)


class ItemListView(ListView):
    model = Item
    paginate_by = 1
    template_name = "home.html"


class ItemDetailView(DetailView):
    model = Item
    template_name = "product.html"


class OrderSummary(LoginRequiredMixin, View):

    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
        except ObjectDoesNotExist:
            # messages.error('You dont have an active order')
            return redirect('/')
        context = {'object': order}
        return render(self.request, 'order_summary.html', context)


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    open_order, open_order_created = Order.objects.get_or_create(
        user=request.user, ordered=False)
    item_in_order, item_in_order_created = OrderItem.objects.get_or_create(
        user=request.user, ordered=False, item=item)
    if item_in_order_created:
        open_order.items.add(item_in_order)
        messages.success(request, 'Item added to cart',extra_tags='alert')
    else:
        item_in_order.quantity += 1
        messages.success(request, 'Item quantity updated',extra_tags='alert')
    open_order.save()
    item_in_order.save()
    return redirect(item)


def add_one_item_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    open_order, open_order_created = Order.objects.get_or_create(
        user=request.user, ordered=False)
    item_in_order, item_in_order_created = OrderItem.objects.get_or_create(
        user=request.user, ordered=False, item=item)
    if item_in_order_created:
        open_order.items.add(item_in_order)
        messages.success(request, 'Item added to cart')
    else:
        item_in_order.quantity += 1
        messages.success(request, 'Item quantity updated')
    open_order.save()
    item_in_order.save()
    return redirect('order-summary')


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    qs = Order.objects.filter(user=request.user, ordered=False)
    if qs.exists():
        open_order = qs[0]
        qs1 = OrderItem.objects.filter(
            user=request.user, ordered=False, item=item)
        if qs1.exists():
            item_in_order = qs1[0]
            item_in_order.quantity = item_in_order.quantity - 1
            item_in_order.save()
            messages.info(request, 'Item quantity updated')
            if item_in_order.quantity <= 0:
                item_in_order.delete()
                messages.warning(request, 'Item removed from cart')
        else:
            messages.warning(request, 'item does not exist in cart')
    else:
        messages.warning(request, 'You dont have an active order')
    return redirect(item)


def remove_one_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    qs = Order.objects.filter(user=request.user, ordered=False)
    if qs.exists():
        open_order = qs[0]
        qs1 = OrderItem.objects.filter(
            user=request.user, ordered=False, item=item)
        if qs1.exists():
            item_in_order = qs1[0]
            item_in_order.quantity = item_in_order.quantity - 1
            item_in_order.save()
            messages.info(request, 'Item quantity updated')
            if item_in_order.quantity <= 0:
                item_in_order.delete()
                messages.warning(request, 'Item removed from cart')
        else:
            messages.warning(request, 'item does not exist in cart')
    else:
        messages.warning(request, 'You dont have an active order')
    return redirect('order-summary')


def remove_whole_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    qs = Order.objects.filter(user=request.user, ordered=False)
    if qs.exists():
        open_order = qs[0]
        qs1 = OrderItem.objects.filter(
            user=request.user, ordered=False, item=item)
        if qs1.exists():
            item_in_order = qs1[0]
            # item_in_order.quantity = item_in_order.quantity - 1
            # item_in_order.save()
            # messages.info(request,'Item quantity updated')
            # if item_in_order.quantity<=0:
            item_in_order.delete()
            messages.warning(request, 'Item removed from cart')
        else:
            messages.warning(request, 'item does not exist in cart')
    else:
        messages.warning(request, 'You dont have an active order')
    return redirect('order-summary')


class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RequestRefundForm()
        context = {'form': form}
        return render(self.request, "request_refund.html", context)

    def post(self, *args, **kwargs):
        form = RequestRefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            reason = form.cleaned_data.get('reason')
            email = form.cleaned_data.get('email')
        try:
            order = Order.objects.get(ref_code=ref_code)
            order.refund_requested = True
            order.save()
            refund = Refund()
            refund.reason = reason
            refund.email = email
            refund.order = order
            refund.save()
            print('refund request received')
            return redirect('/')
        except ObjectDoesNotExist:
            print('order doesnot exists')
            return redirect('/')
