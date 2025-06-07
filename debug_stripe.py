import stripe
from app.config import settings

print(f"Settings loaded: {settings}")
print(f"API Key exists: {bool(settings.stripe_api_key)}")
print(f"API Key: {settings.stripe_api_key[:7]}...")

try:
    stripe.api_key = settings.stripe_api_key
    print(f"Stripe API key set: {stripe.api_key[:7]}...")
    
    # Try to list charges
    charges = stripe.Charge.list(limit=1)
    print(f"Charges found: {len(charges.data)}")
    print("Success!")
except Exception as e:
    print(f"Error: {e}")
    print(f"Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()