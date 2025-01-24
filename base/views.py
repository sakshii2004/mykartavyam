from urllib.parse import urlencode
from django.utils import timezone
import tempfile
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import login, logout
from .forms import CategoryForm, ComplaintForm, UserProfileForm, BadgeForm
from .models import AutocloseDuration, Category, Complaint, CustomUser, Badge, ModeratorApproval, OTP
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .decorators import unauthenticated_user, allowed_users, admin_only
from django.contrib.auth.models import Group
from .utils import post_to_social_media, update_user_badge, reverseGeoLoc, convert_rgba_to_rgb
from datetime import timedelta
from .machine_learning import sensitive_content, detect_hoarding, predict_pothole, predict_garbage, predict_fallen_tree, detect_stagnant_water, detect_and_blur_faces
from .text_checker import contains_offensive_language
from .twitter import post_to_twitter
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from django.utils.timezone import now
from django.core.paginator import Paginator
from random import randint
import json
import re
from django.core.cache import cache
from django.db.models.functions import TruncMonth
from django.db.models import Count  
import folium
from folium.plugins import HeatMap
from mimetypes import guess_type, guess_extension
import os
import http.client
from dotenv import load_dotenv
load_dotenv()


def add_watermark(image_path, reference_id):
    with Image.open(image_path) as img:
        if img.mode == 'RGBA':
            img = img.convert('RGB')

        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype("static/fonts/cour.ttf", size=20)
        text = f"MyKartavyam\nRef: {reference_id}"

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]        
        x = (img.width - text_width) // 2
        y = (img.height - text_height) // 2

        border_offset = 2
        offsets = [
            (x - border_offset, y - border_offset),
            (x + border_offset, y - border_offset),
            (x - border_offset, y + border_offset),
            (x + border_offset, y + border_offset),
            (x, y - border_offset),
            (x, y + border_offset),
            (x - border_offset, y),
            (x + border_offset, y),
        ]
        for offset in offsets:
            draw.text(offset, text, font=font, fill="black")

        draw.text((x, y), text, font=font, fill="white")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            img.save(temp_file.name, format="JPEG")
            return temp_file.name


@login_required(login_url='/login')
def createComplaint(request):
    if request.user.disabled == 'TRUE':
        return redirect('disabled_user_message')    

    if request.method == 'POST':
        form = ComplaintForm(request.POST, request.FILES)
        complaint = form.save(commit=False)
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        complaint.latitude = request.POST.get('latitude')
        complaint.longitude = request.POST.get('longitude')
        complaint.citizen = request.user
        if any(contains_offensive_language(field) for field in [complaint.title, complaint.description]):
            return redirect('restricted_text')
        
        image = request.FILES.get('image')
        if image:
            mime_type, _ = guess_type(image.name)
            if mime_type not in ['image/jpeg', 'image/png', 'image/jpg']:
                return redirect('invalid_file_format')
            
            if image.size > 3 * 1024 * 1024: 
                return redirect('file_too_large')
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=guess_extension(mime_type)) as temp_file:
                temp_file.write(image.read())
                temp_file.flush()
                image_path = temp_file.name

            if mime_type == 'image/png':
                try:
                    image_path = convert_rgba_to_rgb(image_path)
                except Exception as e:
                    print("An error occurred while converting from rgba to rgb.", e)

            try:
                blurred_image_path = detect_and_blur_faces(image_path)
            except Exception as e:
                print("An error occurred while detecting and blurring faces.", e)

            try:
                if sensitive_content(blurred_image_path) == 'Sensitive':
                    return redirect('restricted_content')
            except Exception as e:
                print("An error occurred while evaluating for restricted content.", e)
            
            try:             
                if complaint.category.name == "ILLEGAL HOARDING":
                    complaint.status = 'OPEN' if detect_hoarding(blurred_image_path) == 'Hoarding Detected' else 'AWAITING_APPROVAL'
                elif complaint.category.name == "POTHOLE":
                    complaint.status = 'OPEN' if predict_pothole(blurred_image_path) else 'AWAITING_APPROVAL'
                elif complaint.category.name == "GARBAGE DUMP":
                    complaint.status = 'OPEN' if predict_garbage(blurred_image_path) == 'dirty' else 'AWAITING_APPROVAL'
                elif complaint.category.name == "FALLEN BRANCHES AND TREES":
                    complaint.status = 'OPEN' if predict_fallen_tree(blurred_image_path) == 'fallen_tree' else 'AWAITING_APPROVAL'
                elif complaint.category.name == "STAGNANT DRAIN / WATER":
                    complaint.status = 'OPEN' if detect_stagnant_water(blurred_image_path) == 'Stagnant Water detected' else 'AWAITING_APPROVAL'
            except Exception as e:
                print("An error occurred while AI mod evaluated the image.", e)
                
        complaint.save()
        complaint.reference_id = f"{complaint.category.abbreviation}{complaint.id}"
        complaint.save()

        try:
            watermarked_image_path = add_watermark(blurred_image_path, complaint.reference_id)
        except Exception as e:
            print("An error occurred while watermarking the image.", e)
            return redirect('error')

        ext = ".png" if mime_type == 'image/png' else ".jpg"
        with open(watermarked_image_path, 'rb') as watermarked_image_file:
            complaint.image.save(f"{complaint.id}.{ext}", watermarked_image_file)

        complaint.save()
        update_user_badge(request.user)
        if complaint.status == 'OPEN':
            post_to_social_media(complaint)
            ModeratorApproval.objects.create(
                user=request.user,
                complaint_id=complaint.id,
                reference_id=complaint.reference_id,
                title=complaint.title,
                moderator=None,
                action='APPROVED_BY_AI'
            )
        
        if os.path.exists(image_path):
            os.remove(image_path)
        if os.path.exists(blurred_image_path):
            os.remove(blurred_image_path)
        if os.path.exists(watermarked_image_path):
            os.remove(watermarked_image_path)

        return redirect('home')

    return render(request, 'base/create_complaint.html', {'form': ComplaintForm()})

OTP_RATE_LIMIT_KEY = "otp_rate_limit_{phone_number}"  # unique cache key pattern
OTP_RATE_LIMIT_WINDOW = 60  # time window in seconds
OTP_MAX_REQUESTS = 3  # max OTP requests allowed within the time window

def is_rate_limited(phone_number):
    cache_key = OTP_RATE_LIMIT_KEY.format(phone_number=phone_number)
    request_count = cache.get(cache_key, 0)

    if request_count >= OTP_MAX_REQUESTS:
        return True

    cache.set(cache_key, request_count + 1, OTP_RATE_LIMIT_WINDOW)
    return False

def send_otp(phone_number, otp):
    print(f"Sending OTP {otp} to {phone_number}")
    return True

'''def send_otp(phone_number, otp):
    """
    Sends an OTP using the MSG91 API.

    Args:
    - phone_number (str): The recipient's phone number.
    - otp (str): The OTP to send.

    Returns:
    - str: The API response as a string.
    """
    # Replace with your actual MSG91 credentials and configurations
    msg91_auth_key = os.getenv("MSG91_AUTH_KEY")  # MSG91 Auth Key
    template_id = os.getenv("TEMPLATE_ID")    # Template ID
    sender_id = "KRTVYM"                        # Sender ID
    route = "4"                                 # Route for transactional SMS
    
    # Build the payload with the correct structure for MSG91's API
    payload = {
        "template_id": template_id,
        "sender": sender_id,
        "route": route,
        "recipients": [
            {
                "mobiles": phone_number,
                "var": otp
            }
        ]
    }

    # Convert the payload to JSON
    payload_json = json.dumps(payload)

    # Set up headers for the HTTP request
    headers = {
        'authkey': msg91_auth_key,
        'accept': "application/json",
        'content-type': "application/json"
    }

    try:
        # Establish connection to MSG91's API endpoint
        conn = http.client.HTTPSConnection("api.msg91.com")
        conn.request("POST", "/api/v5/flow", payload_json, headers)

        # Read and decode the API response
        res = conn.getresponse()
        data = res.read()
        conn.close()

        # Log or return the response for debugging
        response = data.decode("utf-8")
        print(f"MSG91 Response: {response}")
        return response
    except Exception as e:
        # Log any exceptions for debugging
        print(f"Error sending OTP: {str(e)}")
        return None'''
    

@unauthenticated_user
def login_view(request):
    try:
        if request.method == 'POST':
            # Handle JSON or form-encoded POST requests
            if request.headers.get('Content-Type') == 'application/json':
                try:
                    body = json.loads(request.body)
                except json.JSONDecodeError:
                    return JsonResponse({'error': 'Invalid JSON format'}, status=400)
                
                phone_number = body.get('phone_number').strip()
                otp = body.get('otp')
            else:
                phone_number = request.POST.get('phone_number').strip()
                otp = request.POST.get('otp')

            if not phone_number:
                return JsonResponse({'error': 'Phone number is required'}, status=400)
            
            if not re.match(r'^\d{10}$', phone_number):
                return JsonResponse({'error': 'Invalid phone number. It must be 10 digits.'}, status=400)
            
            if is_rate_limited(phone_number):
                return JsonResponse({'error': f'OTP request limit reached. Try again after {OTP_RATE_LIMIT_WINDOW} seconds.'}, status=429)

            try:
                user_exists = CustomUser.objects.filter(phone_number=phone_number).exists()
                if not user_exists:
                    return JsonResponse({'error': 'This number is not linked to a MyKartavyam account. Please register.'}, status=400)
            except Exception as e:
                return JsonResponse({'error': f'Error checking user existence: {str(e)}'}, status=500)

            if otp:
                # verify OTP
                try:
                    otp_entry = OTP.objects.get(phone_number=phone_number, otp=otp)
                    if otp_entry.is_expired():
                        return JsonResponse({'error': 'OTP expired'}, status=400)

                    # directly retrieve the user and log them in
                    try:
                        user = CustomUser.objects.get(phone_number=phone_number)
                        if not user.is_active:
                            return JsonResponse({'error': 'User account is inactive'}, status=403)

                        # Log the user in
                        login(request, user)
                        otp_entry.delete()
                        return JsonResponse({'message': 'Login successful'}, status=200)
                    except CustomUser.DoesNotExist:
                        return JsonResponse({'error': 'User does not exist'}, status=404)
                except OTP.DoesNotExist:
                    return JsonResponse({'error': 'Entered OTP is invalid.'}, status=400)

            # generate and send OTP
            otp = randint(100000, 999999)
            OTP.objects.update_or_create(
                phone_number=phone_number,
                defaults={'otp': otp, 'created_at': now()}
            )
            formatted_phone_number = f"91{phone_number}"
            response = send_otp(str(formatted_phone_number), str(otp))
            '''if response and "success" in response.lower():
                return JsonResponse({'message': f'OTP sent to {phone_number}'}, status=200)
            else:
                return JsonResponse({'error': 'Failed to send OTP. Please try again later.'}, status=500)'''
            return JsonResponse({'message': 'OTP sent to ' + phone_number}, status=200)

        return render(request, 'base/login.html')  # render login page for GET requests
    
    except Exception as e:
        # log the error for debugging
        print(f"Error in login_view: {str(e)}")
        return JsonResponse({'error': 'An unexpected error occurred: ' + str(e)}, status=500)

@unauthenticated_user
def register_view(request):
    try:
        if request.method == 'POST':
            if request.headers.get('Content-Type') == 'application/json':
                try:
                    body = json.loads(request.body)
                except json.JSONDecodeError:
                    return JsonResponse({'error': 'Invalid JSON format'}, status=400)

                phone_number = body.get('phone_number').strip()
                name = body.get('name').strip().title()
                email = body.get('email').strip()
                otp = body.get('otp')
            else:
                phone_number = request.POST.get('phone_number').strip()
                name = request.POST.get('name').strip()
                email = request.POST.get('email').strip()
                otp = request.POST.get('otp')

            if not phone_number:
                return JsonResponse({'error': 'Phone number is required.'}, status=400)
            if not name:
                return JsonResponse({'error': 'Name is required.'}, status=400)

            if not email:
                return JsonResponse({'error': 'Email is required.'}, status=400)

            # Field format validation
            if not re.match(r'^\d{10}$', phone_number):
                return JsonResponse({'error': 'Invalid phone number. It must be 10 digits.'}, status=400)
            if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
                return JsonResponse({'error': 'Invalid email address.'}, status=400)
            if not re.match(r'^[A-Za-z\s]+$', name):
                return JsonResponse({'error': 'Invalid name. It should not contain numbers or special characters.'}, status=400)
            
            if is_rate_limited(phone_number):
                return JsonResponse({'error': f'OTP request limit reached. Try again after {OTP_RATE_LIMIT_WINDOW} seconds.'}, status=429)

            # send error if account already exists.
            if CustomUser.objects.filter(phone_number=phone_number).exists():
                return JsonResponse({'error': 'This number is already linked to a MyKartavyam account. Please log in.'}, status=400)

            if otp:
                # Verify OTP
                try:
                    otp_entry = OTP.objects.get(phone_number=phone_number, otp=otp)
                    if otp_entry.is_expired():
                        return JsonResponse({'error': 'OTP expired'}, status=400)

                    # Create user and log them in
                    user, created = CustomUser.objects.get_or_create(
                        phone_number=phone_number,
                        defaults={'name': name, 'email': email}
                    )
                    otp_entry.delete()
                    login(request, user)  # Log the user in
                    return JsonResponse({'message': 'Registration successful and logged in'}, status=200)
                except OTP.DoesNotExist:
                    return JsonResponse({'error': 'Invalid OTP'}, status=400)

            # Generate and send OTP
            otp = randint(100000, 999999)
            OTP.objects.update_or_create(
                phone_number=phone_number,
                defaults={'otp': otp, 'created_at': now()}
            )
            formatted_phone_number = f"91{phone_number}"
            response = send_otp(str(formatted_phone_number), str(otp))
            '''if response and "success" in response.lower():
                return JsonResponse({'message': f'OTP sent to {phone_number}'}, status=200)
            else:
                return JsonResponse({'error': 'Failed to send OTP. Please try again later.'}, status=500)'''
            return JsonResponse({'message': 'OTP sent to '+phone_number}, status=200)

        return render(request, 'base/register.html')  # Render the registration page for GET requests
    except Exception as e:
        # Log the error for debugging
        print(f"Error in register_view: {str(e)}")
        return JsonResponse({'error': 'An unexpected error occurred: ' + str(e)}, status=500)


def logout_user(request):
    logout(request)
    return redirect('login') 

def impact(request):
    current_date = now()
    start_date = current_date - timedelta(days=365)

    total_complaints_count = Complaint.objects.count()

    unique_cities_count = Complaint.objects.values('district').distinct().count()

    unique_states_count = Complaint.objects.values('state').distinct().count()

    complaints_by_month = (
        Complaint.objects.filter(created__gte=start_date)
        .annotate(month=TruncMonth('created'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    complaints_by_category = (
    Complaint.objects.values('category__name')
    .annotate(count=Count('id'))
    .order_by('-count')  
    )

    complaints_by_state = (
        Complaint.objects.values('state')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # data for heatmap (latitude and longitude)
    lat_lon_data = Complaint.objects.filter(latitude__isnull=False, longitude__isnull=False).values_list('latitude', 'longitude')

    resolved_issues_count = Complaint.objects.filter(status='RESOLVED').count()

    auto_closed_issues_count = Complaint.objects.filter(status='AUTO_CLOSED').count()
    reopened_issues_count = Complaint.objects.filter(status='REOPENED').count()

    if auto_closed_issues_count > 0:
        reopened_percentage = (reopened_issues_count / auto_closed_issues_count) * 100
    else:
        reopened_percentage = 0  

    # generate Folium HeatMap
    map_center = [20.5937, 78.9629]  # Center on India
    folium_map = folium.Map(location=map_center, zoom_start=5)
    HeatMap(lat_lon_data, radius=10, blur=15).add_to(folium_map)
    heatmap_html = folium_map._repr_html_()

    # calculate the most popular category for each state
    popular_category_by_state = (
        Complaint.objects.values('state', 'category__name')
        .annotate(count=Count('id'))
        .order_by('state', '-count')
    )

    # prepare a dictionary to store the most popular category for each state
    state_popular_categories = {}
    for item in popular_category_by_state:
        state = item['state']
        category = item['category__name']
        count = item['count']

        # only store the first category for each state (since it's sorted by '-count')
        if state not in state_popular_categories:
            state_popular_categories[state] = {'category': category, 'count': count}

    status_counts = (
        Complaint.objects.values('status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    donut_data = {
        'statuses': [item['status'] for item in status_counts],
        'counts': [item['count'] for item in status_counts],
    }

    graph_data = {
        'months': [item['month'].strftime('%b %Y') for item in complaints_by_month],
        'counts': [item['count'] for item in complaints_by_month],
    }

    category_data = {
        'categories': [item['category__name'] for item in complaints_by_category],
        'counts': [item['count'] for item in complaints_by_category],
    }

    state_data = {
        'states': [item['state'] for item in complaints_by_state],
        'counts': [item['count'] for item in complaints_by_state],
    }

    context = {'graph_data': json.dumps(graph_data), 
               'category_data': json.dumps(category_data), 
               'state_data': json.dumps(state_data), 
               'heatmap_html': heatmap_html,
               'resolved_issues_count': resolved_issues_count,
               'reopened_percentage': reopened_percentage,
               'state_popular_categories': state_popular_categories,
               'total_complaints_count': total_complaints_count,
               'unique_cities_count': unique_cities_count,
               'unique_states_count': unique_states_count,
               'donut_data': json.dumps(donut_data),
        }
    return render(request, 'base/impact.html', context)  


def home(request):
    q = request.GET.get('q')
    c = request.GET.get('c')
    d = request.GET.get('d')
    s = request.GET.get('s')
    r = request.GET.get('r')
    status = request.GET.get('status')
    categories = Category.objects.all()

    complaints = Complaint.objects.exclude(status__in=['FORCE_CLOSED', 'AWAITING_APPROVAL'])

    if q:
        complaints = Complaint.objects.filter(Q(title__icontains=q))
    elif c:
        complaints = Complaint.objects.filter(Q(category__name__icontains=c))
    elif d:
        complaints = Complaint.objects.filter(Q(district__icontains=d))
    elif s:
        complaints = Complaint.objects.filter(Q(state__icontains=s))
    elif r:
        complaints = Complaint.objects.filter(reference_id=r)
    elif status:
        complaints = Complaint.objects.filter(status=status)
    else: 
        complaints = Complaint.objects.all().order_by('-created')
    
    paginator = Paginator(complaints, 10) 
    page_number = request.GET.get('page') 
    complaints_page = paginator.get_page(page_number) 

    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')  # Remove the page parameter to prevent duplication
    query_string = urlencode(query_params)
    
    context = {'complaints': complaints_page, 'categories': categories, 'query_string': query_string,}

    return render(request, 'base/homepage.html', context)

@login_required(login_url='/login')
def profile(request, userID):
    complaints = Complaint.objects.filter(citizen=userID).order_by('-created')
    profile_user = get_object_or_404(CustomUser, id=userID)
    context = {'complaints': complaints, 'profile_user': profile_user}
    return render(request, 'base/profile.html', context)

@login_required(login_url='/login')
def edit_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            return redirect('profile', userID=request.user.id)  
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, 'base/edit_profile.html', {'form': form})

'''@login_required(login_url='/login')
def createComplaint(request): 
    if request.user.disabled == 'TRUE':
        return redirect('disabled_user_message') 

    if request.method == 'POST':        
        form = ComplaintForm(request.POST, request.FILES)  
        if form.is_valid():
            complaint = form.save(commit=False)  
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            complaint.latitude = float(latitude) if latitude else None
            complaint.longitude = float(longitude) if longitude else None
            image = request.FILES.get('image', None)

            if image:
                mime_type, _ = guess_type(image.name)
                valid_mime_types = [
                    'image/jpeg', 'image/png', 'image/jpg'
                ]
                if mime_type not in valid_mime_types:
                    return redirect('invalid_file_format') 

                max_file_size = 3 * 1024 * 1024
                if image.size > max_file_size:
                    return redirect('file_too_large') 
                
                mime_type, _ = guess_type(request.FILES['image'].name)
                suffix = guess_extension(mime_type) if mime_type else ".jpg" 

                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                    temp_file.write(image.read())
                    temp_file.flush()
                    temp_image_path = temp_file.name
                
                if suffix == ".png":
                    processed_image_path = convert_rgba_to_rgb(temp_image_path)
                    image = processed_image_path

                
            title = form.cleaned_data.get('title', '')
            if contains_offensive_language(title):
                return redirect('restricted_text')

            description = form.cleaned_data.get('description', '')
            if contains_offensive_language(description):
                return redirect('restricted_text')
            
            if not (latitude and longitude and title and description and image):
                return redirect('error_page')


            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(request.FILES['image'].read())
                temp_file.flush()
                
                # face detection and blurring
                blurred_image_path = detect_and_blur_faces(temp_file.name)

                # replace the image for further processing
                temp_file = open(blurred_image_path, 'rb')
                
                if sensitive_content(temp_file.name) == "Sensitive":
                    return redirect('restricted_content')
                
                if complaint.category.name == "ILLEGAL HOARDING":
                    try:
                        detection_message = detect_hoarding(temp_file.name)
                        if detection_message == "Hoarding Detected":
                            complaint.status = 'OPEN'
                    except:
                        pass

                elif complaint.category.name == "POTHOLE":
                    try:
                        is_pothole = predict_pothole(temp_file.name)
                        if is_pothole:
                            complaint.status = 'OPEN' 
                    except:
                        pass

                elif complaint.category.name == "GARBAGE DUMP":
                    try:
                        garbage_status = predict_garbage(temp_file.name)
                        if garbage_status == 'dirty':
                            complaint.status = 'OPEN'  
                    except:
                        pass

                elif complaint.category.name == "FALLEN BRANCHES AND TREES":
                    try:
                        fallen_tree_status = predict_fallen_tree(temp_file.name)
                        if fallen_tree_status == 'fallen_tree':
                            complaint.status = 'OPEN' 
                    except:
                        pass

                elif complaint.category.name == "STAGNANT DRAIN / WATER":
                    try:
                        stagnant_water_status = detect_stagnant_water(temp_file.name)
                        if stagnant_water_status == "Stagnant Water detected":
                            complaint.status = 'OPEN' 
                    except:
                        pass                                 

            latlong = str(latitude) + " " + str(longitude)
            district, state, postal_code = reverseGeoLoc(latlong)
            complaint.district = district
            complaint.state = state
            complaint.pincode = postal_code
            complaint.citizen = request.user
            complaint.save()
            category_abbreviation = complaint.category.abbreviation
            reference_id = f"{category_abbreviation}{complaint.id}"
            complaint.reference_id = reference_id

            # add watermark to the image 
            original_image = Image.open(blurred_image_path) 
            draw = ImageDraw.Draw(original_image)

            # calculate dynamic font size and margin based on image dimensions
            base_width = 1000  
            scale_factor = min(original_image.width, original_image.height) / base_width
            font_size = max(12, int(20 * scale_factor))  
            margin = max(10, int(20 * scale_factor))  

            # define font and position (update font path if needed) 
            font = ImageFont.truetype("static/fonts/cour.ttf", font_size)
            text = f"MyKartavyam\nRef: {complaint.reference_id}"  # Reference ID as watermark text
            text_bbox = draw.textbbox((0, 0), text, font=font)  # Get bounding box
            text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
            x = (original_image.width - text_width) // 2 
            y = (original_image.height - text_height) // 2

            # add text to image
            border_width = max(1, int(2 * scale_factor)) # Thickness of the black border
            for dx, dy in [(-border_width, 0), (border_width, 0), (0, -border_width), (0, border_width),
                        (-border_width, -border_width), (-border_width, border_width), 
                        (border_width, -border_width), (border_width, border_width)]:
                draw.multiline_text((x + dx, y + dy), text, font=font, fill="black", spacing=4)  # Black border

            # draw text with white fill
            draw.multiline_text((x, y), text, font=font, fill="white", spacing=4)  # White text

            if original_image.mode == "RGBA":
                original_image = original_image.convert("RGB")

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as watermarked_file:
                original_image.save(watermarked_file.name, format="JPEG")
                complaint.image.save(f"{complaint.reference_id}.jpg", watermarked_file)          

            complaint.save()
            update_user_badge(request.user)

            if complaint.status == 'OPEN':
                try:
                    tweet_text = f"Reference id: {complaint.reference_id} \nTitle: {complaint.title} \nCategory: {complaint.category.name} \nLocation: {complaint.district}, {complaint.state} https://www.google.com/maps?q={complaint.latitude},{complaint.longitude} \nLandmark: {complaint.landmark} \nMore at: https://mykartavyam.info/view-complaint/{complaint.id} \n#kartavyam #kartavyam_{complaint.district} #kartavyam_{complaint.state}"
                    if len(tweet_text) > 279:
                        tweet_text = tweet_text[0:278]
                        if complaint.image.path:
                            output = post_to_twitter(tweet_text, complaint.image.path)
                        if output:
                            complaint.posted_on_x = True
                            complaint.save()
                except Exception as e:
                    pass 

                ModeratorApproval.objects.create(
                user=request.user,
                complaint_id=complaint.id,  
                reference_id=complaint.reference_id,
                title=complaint.title,
                moderator=None,
                action='APPROVED_BY_AI'
                )                           
                
            return redirect('home')
        
        else:
            return HttpResponse(form.errors)
    else:
        form = ComplaintForm()
    
    context = {'form': form}
    return render(request, 'base/create_complaint.html', context)'''

@login_required(login_url='/login')
def getNotifications(request):
    context = {}
    user = request.user
    notifications = ModeratorApproval.objects.filter(user=user).order_by('-created')
    context = {'notifications': notifications}
    return render(request, 'base/notifications.html', context)

def viewComplaint(request, complaintID):
    complaint = Complaint.objects.get(id=complaintID)
    creator = None
    if request.user:
        if request.user == complaint.citizen:
            creator = 'Yes'
    context = {'complaint': complaint, 'creator':creator}
    return render(request, 'base/view_complaint.html', context)

@login_required(login_url='/login')
def markAsResolved(request, complaintID):
    complaint = Complaint.objects.get(id=complaintID)
    if request.method == 'POST':
        complaint.status = 'RESOLVED'
        complaint.save()
        return redirect('home')
    return render(request, 'base/mark_resolved.html')

@login_required(login_url='/login')
def reOpen(request, complaintID):
    complaint = get_object_or_404(Complaint, id=complaintID)
    
    if request.method == 'POST':
        complaint.status = 'REOPENED'
        complaint.reopened = timezone.now()  
        complaint.save()
        return redirect('home')
    return render(request, 'base/mark_reopened.html', {'complaint': complaint})

@login_required(login_url='/login')
def deleteComplaint(request, complaintID):
    complaint = Complaint.objects.get(id=complaintID)
    if request.method == 'POST':
        if request.user.groups.filter(name__in=['admin', 'moderator']).exists():
            if complaint.status == "AWAITING_APPROVAL":
                ModeratorApproval.objects.create(
                    user=complaint.citizen,  
                    complaint=complaint,
                    reference_id=complaint.reference_id,
                    title=complaint.title,
                    moderator=request.user,  
                    action='REJECTED', 
                    created=timezone.now()
                )
            else:
                    ModeratorApproval.objects.create(
                    user=complaint.citizen,  
                    complaint=complaint,
                    reference_id=complaint.reference_id,
                    title=complaint.title,
                    moderator=request.user,  
                    action='DELETED', 
                    created=timezone.now()
                )

        complaint.delete()
        update_user_badge(request.user)
        return redirect('home')
    return render(request, 'base/delete.html', {'obj': 'complaint', 'text': 'This might affect your badges.', 'complaint':complaint})

@allowed_users(allowed_roles=['admin', 'moderator'])
@login_required(login_url='/login')
def adminPanel(request):
    return render(request, 'base/admin_page.html')

@allowed_users(allowed_roles=['admin', 'moderator'])
@login_required(login_url='/login')
def addCategories(request): 
    form = CategoryForm()
    categories = Category.objects.all()
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('category-update')
    context = {'categories': categories, 'form': form}
    return render(request, 'base/category_update.html', context)

@allowed_users(allowed_roles=['admin', 'moderator'])
@login_required(login_url='/login')
def disableCategory(request, categoryID): 
    category = Category.objects.get(id=categoryID)
    if request.method == 'POST':
        if category.disabled == False:
            category.disabled = True
            category.save()
        return redirect('category-update')
    return render(request, 'base/disable_enable_category.html', {'action': 'disable', 'obj': 'category: '+category.name})    

@allowed_users(allowed_roles=['admin', 'moderator'])
@login_required(login_url='/login')
def enableCategory(request, categoryID): 
    category = Category.objects.get(id=categoryID)
    if request.method == 'POST':
        if category.disabled == True:
            category.disabled = False
            category.save()
        return redirect('category-update')
    return render(request, 'base/disable_enable_category.html', {'action': 'enable', 'obj': 'category: '+category.name})    

@allowed_users(allowed_roles=['admin', 'moderator'])
@login_required(login_url='/login')
def addBadges(request):  
    form = BadgeForm()
    if request.method == 'POST':
        form = BadgeForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('badges-update')
    badges = Badge.objects.all() 
    context = {'badges': badges, 'form':form}
    return render(request, 'base/badges.html', context)

@admin_only
@login_required(login_url='/login')
def editModerators(request): 
    if request.method == 'POST':
        phone_number= request.POST.get('phone_number')
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
        except CustomUser.DoesNotExist:
            return render(request, 'base/some_error.html', {
                'heading_text': "User Not Found",
                'detailed_text': "The user you tried accessing does not exist. The phone number could be incorrect.",
            })
        moderator_group, created = Group.objects.get_or_create(name="moderator")
        user.groups.add(moderator_group)
        return redirect('moderators-update')
    
    group = Group.objects.get(name='moderator')
    moderators = group.user_set.all()
    context = {'moderators': moderators }
    return render(request, 'base/moderator_update.html', context)

@admin_only
@login_required(login_url='/login')
def removeModerator(request, userID):
    user = get_object_or_404(CustomUser, id=userID)
    moderator_group = Group.objects.get(name='moderator')
    if user.groups.filter(name='moderator').exists():
        user.groups.remove(moderator_group)
    return redirect('moderators-update')

@allowed_users(allowed_roles=['admin', 'moderator'])
@login_required(login_url='/login')
def approveComplaints(request):
    unapproved_complaints = Complaint.objects.filter(status='AWAITING_APPROVAL').order_by('-created')
    unapproved_complaints_count = unapproved_complaints.count()    
    context = {'unapproved_complaints': unapproved_complaints, 'unapproved_complaint_count':unapproved_complaints_count}
    return render(request, 'base/approve_complaints.html', context)

@allowed_users(allowed_roles=['admin', 'moderator'])
@login_required(login_url='/login')
def approveComplaint(request, complaintID):
    complaint = Complaint.objects.get(id=complaintID)
    if request.method == 'POST':
        if complaint.status != 'AWAITING_APPROVAL':
            return redirect(error)
        complaint.status = 'OPEN'
        complaint.opened = timezone.now() 
        complaint.save()

        ModeratorApproval.objects.create(
        user=complaint.citizen, 
        complaint_id=complaint.id,
        reference_id=complaint.reference_id,
        title=complaint.title,
        moderator=request.user, 
        action='APPROVED_BY_MOD',  
        )

        post_to_social_media(complaint)

        return redirect('home')
    return render(request, 'base/approve_complaint.html')

@allowed_users(allowed_roles=['admin', 'moderator'])
@login_required(login_url='/login')
def forceCloseComplaint(request, complaintID):
    complaint = Complaint.objects.get(id=complaintID)
    if request.method == 'POST':
        complaint.status = 'FORCE_CLOSED'
        complaint.save()
        return redirect('home')
    return render(request, 'base/force_close_complaint.html')


@allowed_users(allowed_roles=['admin', 'moderator'])
@login_required(login_url='/login')
def autoClose(request):
    if request.method == 'POST':
        try:
            most_recent_duration = AutocloseDuration.objects.latest('created').duration
        except AutocloseDuration.DoesNotExist:
            most_recent_duration = 15 
        cutoff_date = timezone.now() - timedelta(days=most_recent_duration)
        complaints_to_close = Complaint.objects.filter(
            opened__lte=cutoff_date, 
            status__in=['OPEN', 'REOPENED']
        )        
        complaints_to_close.update(status='AUTO_CLOSED')
        return redirect('home')
    return render(request, 'base/autoclose.html')

@allowed_users(allowed_roles=['admin', 'moderator'])
@login_required(login_url='/login')
def setAutoCloseTimePeriod(request):
    if request.method == 'POST':
        try:
            new_duration = int(request.POST.get('autoclose_timeperiod'))
            AutocloseDuration.objects.create(duration=new_duration)
            return redirect('set_autoclose')  
        except (error):
            return render('error')
        
    try:
        most_recent_duration = AutocloseDuration.objects.latest('created').duration
    except AutocloseDuration.DoesNotExist:
        most_recent_duration = 15
        
    context = {'autoclose_timeperiod': most_recent_duration}
    
    return render(request, 'base/set_time_period.html', context)

@allowed_users(allowed_roles=['admin', 'moderator'])
@login_required(login_url='/login')
def disableUser(request):
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
        except CustomUser.DoesNotExist:
            return render(request, 'base/some_error.html', {
                'heading_text': "User Not Found",
                'detailed_text': "The user you tried accessing does not exist. The phone number could be incorrect.",
            })
        if not user:
            return redirect('error')

        if user.groups.filter(name__in=['admin', 'moderator']).exists():
            return redirect('error')
        
        if user.disabled == 'TRUE':
            return redirect('disable-user')

        user.disabled = 'TRUE'
        user.save()

        ModeratorApproval.objects.create(
            user=user,
            complaint=None,
            reference_id=None,
            title=None,
            moderator=request.user,
            action="DISABLE_USER"
        )

        return redirect('disable-user')

    disabled_users = CustomUser.objects.filter(disabled='TRUE')
    context = {'disabled_users': disabled_users}
    return render(request, 'base/disable_users.html', context)

@allowed_users(allowed_roles=['admin', 'moderator'])
@login_required(login_url='/login')
def enableUser(request, userID):
    try:
        user = CustomUser.objects.get(id=userID)
    except CustomUser.DoesNotExist:
        return render(request, 'base/some_error.html', {
            'heading_text': "User Not Found",
            'detailed_text': "The user you tried accessing does not exist.",
        })

    if not user:
        return redirect('disable-user')

    if user.disabled == 'FALSE':
        return redirect('disable-user')

    user.disabled = 'FALSE'
    user.save()

    ModeratorApproval.objects.create(
        user=user,
        complaint=None,
        reference_id=None,
        title=None,
        moderator=request.user,
        action="ENABLE_USER"
    )

    return redirect('disable-user')

@login_required(login_url='/login')
def disabledUserMessage(request):
    return render(request, 'base/disabled_user_message.html')

def aboutUs(request):
    badges = Badge.objects.all() 
    context = {'badges': badges}
    return render(request, 'base/about_us.html', context)

def tnc(request):
    return render(request, 'base/tnc.html')

def privacyPolicy(request):
    return render(request, 'base/privacy_policy.html')

def restrictedContent(request):
    return render(request, 'base/restricted_content.html')

def error(request):
    return render(request, 'base/error.html')

def invalidFileFormat(request):
    return render(request, "base/invalid_file_format.html")

def fileSizeTooLarge(request):
    return render(request, "base/file_size_too_large.html")