from base.twitter import post_to_twitter
from .models import Complaint, Badge
from geopy.geocoders import Nominatim
from PIL import Image, UnidentifiedImageError
import tempfile

def convert_rgba_to_rgb(image_file):
    try:
        with Image.open(image_file) as img:
            if img.format == 'PNG' and img.mode == 'RGBA':
                rgb_image = Image.new("RGB", img.size, (255, 255, 255))
                rgb_image.paste(img, mask=img.split()[3])  
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                    rgb_image.save(temp_file.name, format="PNG")
                    return temp_file.name  
            else:
                return image_file
    except UnidentifiedImageError:
        raise UnidentifiedImageError(f"Cannot identify image file: {image_file}")
    except Exception as e:
        raise Exception(f"Error while processing image: {str(e)}")

def update_user_badge(user):
    total_complaints = Complaint.objects.filter(citizen=user).count()

    badge = Badge.objects.filter(min_complaints__lte=total_complaints).order_by('-min_complaints').first()

    if badge and user.current_badge != badge:
        user.current_badge = badge
        user.save()


def reverseGeoLoc(latlong):
    try:
        geoLoc = Nominatim(user_agent="GetLoc")
        locname = geoLoc.reverse(latlong)
        district = locname.raw['address']['state_district']
        state = locname.raw['address']['state']
        postal_code = locname.raw['address']['postcode']
        return district, state, postal_code  
    except Exception as e:
        return None, None, None  
    
def post_to_social_media(complaint):
    try:
        tweet_text = (
                f"#mykartavyam #mykartavyam_{complaint.district} #mykartavyam_{complaint.state}\n"
                f"Location: {complaint.district}, {complaint.state} "
                f"https://www.google.com/maps?q={complaint.latitude},{complaint.longitude} \n"
                f"More at: https://mykartavyam.info/view-complaint/{complaint.id} \n"
                f"Reference id: {complaint.reference_id} \n"
                f"Category: {complaint.category} \n"
                f"Landmark: {complaint.landmark} \n"                     
            )
        
        if len(tweet_text) > 279:
                    tweet_text = tweet_text[:276] + "..."  

        if complaint.image and complaint.image.path:
            output = post_to_twitter(tweet_text, complaint.image.path)
            if output:
                complaint.posted_on_x = True
                complaint.save()
    except Exception as e:
        print(f"Error posting to social media: {e}")
