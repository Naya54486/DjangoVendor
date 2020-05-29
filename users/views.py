from django.shortcuts import renderfrom django.shortcuts import render
from django.shortcuts import render, redirect, get_list_or_404
from . models import Vendor, Customer, Menu, Status, Order, Notification, Auth, Cart, OrderContent
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from . serializers import VendorSerializer, CustomerSerializer, MenuSerializer, StatusSerializer, OrderSerializer, NotificationSerializer, UserSerializer, CartSerializer, OrderContentSerializer
from django.http import HttpResponse, Http404
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from django.core.mail import send_mail
from django.core.mail import EmailMessage
from django.contrib import messages
# Create your views here.


class SetPassword(APIView):
    def get_object(self, pk):
        try:
            return User.objects.get(reference_id = pk)
        except User.DoesNotExist:
            raise Http404
        
    def get(self, request, pk, format=None):
        user = self.get_object(pk)
        message = {"message":f"{user},use a PUT request to set your password"}
        return Response(message, status = status.HTTP_200_OK)

    def put(self, request, pk, format=None):
        user = self.get_object(pk)
        now = timezone.now()
        if now < user.date_expiry :
            user_obj = User.objects.get(email = user)
            new_password = request.data['password']
            user_obj.set_password(new_password)
            user_obj.save()
            message ={"message":"Your password has now been set you can now login"}
            return Response(message, status =  status.HTTP_200_OK)
        message ={"message":"The password reset link has exipred"}
        return Response(message,status = status.HTTP_400_BAD_REQUEST)


class LoginUser(APIView):
    def post(self, request, format = None):
        data = request.data
        email = data['email']
        password = data['password']
        user = authenticate(email = email, password = password)
        if user is None :
            response = {"message" : "Incorrect username or password details"}
            return Response(response, status = status.HTTP_400_BAD_REQUEST)
        user_token = get_token(request)
        response = {
            "message" : "You are logged in welcome back",
            "token" : user_token
            }
        update_last_login(email)
        return Response(response, status =  status.HTTP_200_OK)

def createuser(request, reference_id, user_type):
    data = request.data
    email = data['email']
    default_password = config("DEFAULT_PASSWORD")
    userdata = {'email': email,'password':default_password, 'reference_id':reference_id, 'user_type' : user_type }
    authseuserdatarializer = UserSerializer(data=userdata)
    if authseuserdatarializer.is_valid():
        authseuserdatarializer.save()

@api_view(['POST'])
def get_user_token(request):
    user_obj = User.objects.get(email = request.data['email'])
    if request.method == 'POST':
        token = Token.objects.filter(user=user_obj)
        if token:
            new_key = token[0].generate_key()
            token.update(key=new_key)
            return Response({"token":new_key})
        else:
            token = Token.objects.create(user = user_obj)
            return Response({"token":token.key})

def get_token(request):
    user_obj = User.objects.get(email = request.data['email'])
    if request.method == 'POST':
        token = Token.objects.filter(user=user_obj)
        if token:
            new_key = token[0].generate_key()
            token.update(key=new_key)
            return new_key
        else:
            token = Token.objects.create(user = user_obj)
            return token.key

def update_last_login(email):
    user_obj = User.objects.get(email = email)
    update_data ={"last_login":timezone.now()}
    serializer =UserSerializer(user_obj, data = update_data, partial = True)
    if serializer.is_valid():
        serializer.save()

class SignUp(APIView):
    user_type = 2                       
    def get(self, request, format=None):
        users = Customer.objects.all()
        serializer = CustomerSerializer(users, many=True)
        return Response(serializer.data)

    def post(self, request, format = None):
        user_type = SignUp.user_type
        user_email = request.data['email']
        query_user = User.objects.filter(email = user_email,user_type = user_type)
        if query_user:
            message = {"message" : "user with this email already exists"}
            return Response(message, status = status.HTTP_400_BAD_REQUEST)
        serializer = CustomerSerializer(data=request.data)
        
        subject = "Customer Signup Registration"
        reference_id = id_generator()
        if serializer.is_valid():
            serializer.save()
            createuser(request, reference_id, user_type)
            sendmail(request, reference_id, subject)
            message = {"message":"A password reset link has been sent to your email account. Link expires in 10 mins"}
            return Response(message, status =  status.HTTP_201_CREATED)
        return Response(serializer.errors, status = status.HTTP_400_BAD_REQUEST)


class AllMenu(APIView):
    permission_classes = (IsAuthenticated,) 

    def get(self, request, format=None):
        today = date.today().strftime('%Y-%m-%d')
        weekday = date.today().strftime('%A').lower()
        all_menu = MenuModel.objects.filter(avaliable=True, freq_of_reocurrence__contains = [weekday])
        serializer = MenuSerializer(all_menu, many=True)
        return Response(serializer.data)

class VendorAllMenu(APIView):
    permission_classes = (IsAuthenticated,) 

    def get(self, request, pk, format=None):
        all_vendor_menu = MenuModel.objects.filter(vendor_id = pk, avaliable=True)
        serializer = MenuSerializer(all_vendor_menu, many=True)
        return Response(serializer.data)

class Order(APIView):
    permission_classes = (IsAuthenticated,) 
 
    def get_object(self, pk):
        try:
            return MenuModel.objects.get(pk=pk)
        except MenuModel.DoesNotExist:
            raise Http404
    
    def get_available_object(self, pk):
        menu_record = MenuModel.objects.filter(pk = pk ,avaliable=True)
        return menu_record
        
    def update_balance (self, customer_obj, charge_amt):
        old_balance = customer_obj.amount_outstanding
        new_balance = old_balance + (charge_amt)
        user_data = {"amount_outstanding":new_balance}
        serializer = CustomerSerializer(customer_obj, data=user_data, partial = True)  
        if serializer.is_valid():
            serializer.save()

    def get(self, request, format=None):
        current_user = request.user
        if current_user.user_type != 2:   
            message ={'message':"this resource is for customers"}
            return Response(message, status=status.HTTP_400_BAD_REQUEST)
                
        data = request.data
        menus = data['items_ordered']
        if menus == []:
            message = {"message":"No order(s) entered"}
            return Response(message, status = status.HTTP_400_BAD_REQUEST)

        for menu in menus:
            avaliable_menu=self.get_available_object(menu)
            if not avaliable_menu.exists():
                message = {"message":f"Menu ID {menu} is not avalaible kindly remove !"}
                return Response(message, status = status.HTTP_400_BAD_REQUEST)         
        
        amount_due = sum([self.get_object(menu).price for menu in menus])
        message = {'message':f"total amount due {amount_due}"}
        return Response(message, status = status.HTTP_200_OK)


    def post(self, request, format=None):
        current_user = request.user
        if current_user.user_type != 2:
            message ={'message':"this resource is for customers"}
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        customer_obj = customer_details(current_user)

        data = request.data

        menus = data['items_ordered']
        if menus == []:
            message = {"message":"No order(s) made"}
            return Response(message, status = status.HTTP_400_BAD_REQUEST)

        for menu in menus:
            avaliable_menu=self.get_available_object(menu)
            if not avaliable_menu.exists():
                message = {"message":f"Menu ID {menu} is not avalaible kindly remove !"}
                return Response(message, status = status.HTTP_400_BAD_REQUEST)    
        
        vendor_id = self.get_object(menus[0]).vendor_id

        amount_due = sum([self.get_object(menu).price for menu in menus])
        paid = data['amount_paid']

        if paid < 0 :
            message = {"message":f"amount paid cannot be less than zero. your amount due is {amount_due} naira to complete your order"}
            return Response(message, status = status.HTTP_400_BAD_REQUEST)
        
        balance =  paid - amount_due

        if balance == amount_due :
            payment_status = 1           
        elif balance < 0 :
            payment_status = 2    
        elif balance == 0 :
            payment_status = 3     
        elif balance > 0 :
            payment_status = 4      
        else:
            payment_status = 0          
        
        order_data = {
        "description" : data['description'],
        "items_ordered" : data['items_ordered'],
        "amount_due" : amount_due,
        "amount_paid" : data['amount_paid'],
        "amount_outstanding" : balance,
        "payment_status" : payment_status,
        "vendor" : vendor_id,
        "customer" : customer_obj.id,
        "delivery_date_time" : data['delivery_date_time'],
        "order_status_id" : 1
        }

        serializer  = OrderSerializer(data=order_data)
        if serializer.is_valid():
            serializer.save()
            message = {"message":"Your Order has been Placed successfully"}

            cust_list = [customer_obj.id]
            order = OrderModel.objects.latest('id')
            notify_message = f"A new order with id {order.id} has been placed for {data['description']}"
            notify = Notification(vendor_id,notify_message,1,cust_list)
            notify.push_notification_to_all()

            self.update_balance(customer_obj, balance)

            return Response(message, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class OrdersHistory(APIView):
    permission_classes = (IsAuthenticated,)
    """
    Retrieve, History of all transactions by customer.
    """
    def get(self, request, format=None):

        current_user = request.user
        if current_user.user_type != 2: 
            message ={'message':"this resource is for customers"}
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        customer_obj = customer_details(request.user)
        order = OrderModel.objects.filter(customer = customer_obj.id).order_by('-date_time_created')
        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

class CustomerOrderDetail(APIView):
    permission_classes = (IsAuthenticated,) 
 
    def get_object(self, pk):
        try:
            return OrderModel.objects.get(pk=pk)
        except OrderModel.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):      

        current_user = request.user
        if current_user.user_type != 2: 
            message ={'message':"this resource is for customers"}
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        menu = self.get_object(pk)
        cust_obj  = customer_details(request.user)
        if cust_obj.id != menu.customer_id :
            message = {"message": "The Selected Order does not belong to you"}
            return Response(message, status=status.HTTP_400_BAD_REQUEST)
        serializer = OrderSerializer(menu)
        return Response(serializer.data)

class CancelOrder(APIView):
    cancel_id = 7
    charge_amt = 200
    permission_classes = (IsAuthenticated,) 

    def get_object(self, pk):
        try:
            return OrderModel.objects.get(pk=pk)
        except OrderModel.DoesNotExist:
            raise Http404
    
    def update_balance (self, customer_obj, charge_amt):
        old_balance = customer_obj.amount_outstanding
        new_balance = old_balance -  (charge_amt)
        user_data = {"amount_outstanding":new_balance}
        serializer = CustomerSerializer(customer_obj, data=user_data, partial = True)  
        if serializer.is_valid():
            serializer.save()

    def put(self, request, pk, format=None):         
        
        order = self.get_object(pk)

        cust_obj  = customer_details(request.user)

        if cust_obj.id != order.customer_id :
            message = {"message": "The Selected Order does not belong to you"}
            return Response(message, status=status.HTTP_400_BAD_REQUEST)
        
        if order.order_status_id != 1:
            status_name = OrderStatus.objects.get(pk = order.order_status_id)
            message = {"message": f"This Order cannot be cancelled its now {status_name.name}"}
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        now  = timezone.now()
        if now > order.cancel_expiry :  
            message = {"message": "This order cancellation time is expired "}
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        order_status = {"order_status" : CancelOrder.cancel_id}                          
        cust_list = [order.customer_id]

        serializer = OrderSerializer(order, data=order_status, partial = True)
        
        if serializer.is_valid():
            serializer.save()
            self.update_balance(cust_obj, CancelOrder.charge_amt)

            notify_message = f"the order with ID {pk} has been cancelled by customer"
            notify =Notification(order.vendor_id,notify_message,1,cust_list)
            notify.push_notification_to_all()
            message = {"message":f"the order with ID {pk} has been successfully cancelled"}
            return Response(message, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def customer_details(user_email):
    customer_object = Customer.objects.get(email=user_email)
    return customer_object


class VendorSignUp(APIView):

    def post(self, request, format = None):
        user_type = 1
        subject = "Vendor Signup Registration"
        serializer = VendorSerializer(data=request.data)
        reference_id = id_generator()
        if serializer.is_valid():
            serializer.save()
            createuser(request, reference_id, user_type)
            sendmail(request, reference_id, subject)
            message = {"message":"Account created successfully a password reset link has been sent to your email account. Link expires in 10 mins"}
            return Response(message, status =  status.HTTP_201_CREATED)
        return Response(serializer.errors, status = status.HTTP_400_BAD_REQUEST)


class Menu(APIView):
    permission_classes = (IsAuthenticated,) 
 
    def get_object(self, vid):

        try:
            return MenuModel.objects.get(vendor=vid)
        except MenuModel.DoesNotExist:
            raise Http404

    def get(self, request, format=None):
        current_user = request.user
        vendor_obj = vendor_details(current_user)
        queryset = MenuModel.objects.filter(vendor=vendor_obj.id)
        serializer = MenuSerializer(queryset, many=True)
        # serializer = MenuSerializer(menu)
        return Response(serializer.data)

    def post(self, request, format=None):
        current_user = request.user
        vendor_obj = vendor_details(current_user)
        business_name = vendor_obj.business_name
        cust_list =  list(Customer.objects.all().values_list('id',flat=True))
        data = request.data

        #checking if order is recurring or not
        if data['is_recurring'] == "True":
            menu_data = {
            "name" : data['name'],
            "description" : data['description'],
            "price" : data['price'],
            "quantity" : data['quantity'],
            "is_recurring" : data['is_recurring'],
            "freq_of_reocurrence" : data['freq_of_reocurrence'],
            "vendor" : vendor_obj.id
            }
        else:
            menu_data = {
            "name" : data['name'],
            "description" : data['description'],
            "price" : data['price'],
            "quantity" : data['quantity'],
            "is_recurring" : data['is_recurring'],
            "vendor" : vendor_obj.id
            }     
        serializer  = MenuSerializer(data=menu_data)
        if serializer.is_valid():
            serializer.save()
            notify_message = f"A New menu {data['name']} has been added by {business_name} "
            notify = Notification(vendor_obj.id,notify_message,2,cust_list)
            notify.push_notification_to_all()
            message ={"message":f"{data['name']} has been added successfully to your menu list"}
            return Response(message, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MenuDetail(APIView):
    permission_classes = (IsAuthenticated,) 

    def get_object(self, pk):
        try:
            return MenuModel.objects.get(pk=pk)
        except MenuModel.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        menu = self.get_object(pk)
        current_user = request.user
        vendor_obj = vendor_details(current_user)
        if menu.vendor_id != vendor_obj.id:
            message = {"message":"This Menu does not belong to you, Preview is not Allowed"}
            return Response(message, status = status.HTTP_400_BAD_REQUEST)        
        serializer = MenuSerializer(menu)
        return Response(serializer.data)

    def put(self, request, pk, format=None):
        menu = self.get_object(pk)
        current_user = request.user
        vendor_obj = vendor_details(current_user)
        if menu.vendor_id != vendor_obj.id:
            message = {"message":"This Menu does not belong to you, Update is not Allowed"}
            return Response(message, status = status.HTTP_400_BAD_REQUEST)
        serializer = MenuSerializer(menu, data=request.data, partial = True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        menu = self.get_object(pk)
        current_user = request.user
        vendor_obj = vendor_details(current_user)
        if menu.vendor_id != vendor_obj.id:
            message = {"message":"This Menu does not belong to you, Delete is not Allowed"}
            return Response(message, status = status.HTTP_400_BAD_REQUEST)
        menu.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class VendorOrderDetail(APIView):
    permission_classes = (IsAuthenticated,) 

    def get_object(self, pk):
        try:
            return OrderModel.objects.get(pk=pk)
        except OrderModel.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        order = self.get_object(pk)
        current_user = request.user
        vendor_obj = vendor_details(current_user)
        if order.vendor_id != vendor_obj.id:
            message = {"message":"This Order does not belong to you, Preview is not Allowed"}
            return Response(message, status = status.HTTP_400_BAD_REQUEST)        
        serializer = OrdersSerializer(order)
        return Response(serializer.data)

    def put(self, request, pk, format=None):
        order = self.get_object(pk)
        current_user = request.user
        vendor_obj = vendor_details(current_user)
        if len(request.data) != 1 or 'order_status' not in request.data:
            message = {"message":"you are only allowed to update order status from customer order"}
            return Response(message, status = status.HTTP_400_BAD_REQUEST)
        
        order_status = {"order_status" : request.data["order_status"]}
        if order.vendor_id != vendor_obj.id:
            message = {"message":"This Order does not belong to you, Update is not Allowed"}
            return Response(message, status = status.HTTP_400_BAD_REQUEST)
        serializer = OrdersSerializer(order, data=order_status, partial = True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VendorSales(APIView):
    permission_classes = (IsAuthenticated,) 

    def get(self, request, format=None):
        if 'date_time_created' not in request.data:
            message ={"message":"this request requires date_time_created e.g 2020-05-25"}
            return Response(message, status=status.HTTP_400_BAD_REQUEST)

        current_user = request.user
        vendor_obj = vendor_details(current_user)
        search_date = request.data["date_time_created"]
        queryset = OrderModel.objects.filter(date_time_created__date = search_date, vendor_id = vendor_obj.id)
        serializer = OrdersSerializer(queryset, many=True)
        return Response(serializer.data)

class VendorSendBalances(APIView):
    permission_classes = (IsAuthenticated,) 

    def get(self, request, format=None):
        current_user = request.user
        vendor_obj = vendor_details(current_user)
        qry_orders = OrderModel.objects.filter(vendor_id = vendor_obj.id).exclude(amount_outstanding = 0.00)
        serializer = OrdersSerializer(qry_orders, many=True)
        return Response(serializer.data, status = status.HTTP_200_OK)            

    def post(self, request, format=None):
        current_user = request.user
        vendor_obj = vendor_details(current_user)
        orders = OrderModel.objects.filter(vendor_id = vendor_obj.id).exclude(amount_outstanding = 0.00)
        if orders :
            for order in orders:
                notify_message = f"This is to notify you your balace with us is {order.amount_outstanding} "
                notify = Notification(vendor_obj.id,notify_message,2,[order.customer_id])
                notify.push_notification_to_all()

            message ={"message":"All balances sent successfully"}
            return Response(message, status = status.HTTP_200_OK )
        message ={"message":"No balances to be sent"}
        return Response(message, status = status.HTTP_200_OK )

class OrderHistory(APIView):
    permission_classes = (IsAuthenticated,) 

    def get(self, request, pk, format=None):
        current_user = request.user
        vendor_obj = vendor_details(current_user)
        qry_orders_by_user = OrderModel.objects.filter(vendor_id = vendor_obj.id,customer_id = pk)
        serializer = OrdersSerializer(qry_orders_by_user, many=True)
        return Response(serializer.data, status = status.HTTP_200_OK) 

class OrdersStatus(APIView):
    permission_classes = (IsAuthenticated,) 

    def get(self, request, pk, format=None):
        current_user = request.user
        vendor_obj = vendor_details(current_user)

        if 'order_date' in request.data :
            order_date = request.data['order_date']
            qry_orders_by_user = OrderModel.objects.filter(vendor_id = vendor_obj.id,order_status_id = pk, delivery_date_time__date = order_date)
            serializer = OrdersSerializer(qry_orders_by_user, many=True)
            return Response(serializer.data, status = status.HTTP_200_OK)
        message ={"message":"order_date field is missing"}
        return Response(message, status = status.HTTP_400_BAD_REQUEST)

class OrderStatus(APIView):

    def get(self, request, format=None):
        order_status = OrderStatusModel.objects.all()
        serializer = OrderStatusSerializer(order_status, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        serializer  = OrderStatusSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MessageStatus(APIView):

    def get(self, request, format=None):
        message_status = MessageStatusModel.objects.all()
        serializer = MessageStatusSerializer(message_status, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        serializer  = MessageStatusSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def vendor_details(user_email):
    Vendor_object = Vendor.objects.get(email=user_email)
    return Vendor_object