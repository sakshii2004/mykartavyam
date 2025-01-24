import tweepy
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('API_KEY')
api_secret = os.getenv('API_SECRET')
bearer_token = os.getenv('BEARER_TOKEN')
access_token = os.getenv('ACCESS_TOKEN')
access_token_secret = os.getenv('ACCESS_TOKEN_SECRET')

client = tweepy.Client(bearer_token, api_key, api_secret, access_token, access_token_secret)
auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
api = tweepy.API(auth)

def post_to_twitter(text, image_path):
    try:
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        api = tweepy.API(auth)
        media = api.media_upload(image_path) 
        media_id = media.media_id_string
        client.create_tweet(text=text, media_ids=[media_id])  
        return True
    except Exception as e:
        print("An error occurred while posting to Twitter:", e)
        return e
