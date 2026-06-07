import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000/api/core"

def post(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"HTTP Error {e.code}: {error_body}")
        return {"error": error_body}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON response"}

def get(url):
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())

print("=" * 50)
print("TESTING SMART OPD BACKEND")
print("=" * 50)

# 1. Health check
print("\n[1] Health Check")
result = get(f"{BASE}/health/")
print("Result:", result)

# 2. Get available slots
print("\n[2] Available Slots")
result = get(f"{BASE}/slots/")
print(f"Slots found: {result.get('count', 0)}")
if result.get('slots'):
    for slot in result['slots']:
        print(f"  - Slot {slot['slot_id']}: {slot['doctor_name']} on {slot['date']} ({slot['tokens_available']} spots left)")

# 3. Book a token (using the first available slot)
print("\n[3] Booking a token...")
slots = result.get('slots', [])
if slots:
    slot_id = slots[0]['slot_id']
    result = post(f"{BASE}/book/", {
        "slot_id": slot_id,
        "patient_name": "Ramesh Sharma",
        "patient_age": 30,
        "patient_phone": "9841234567"
    })
    print("Result:", result)
    
    if result.get('success'):
        token = result.get('token', {})
        token_id = token.get('token_id')
        token_number = token.get('token_number')
        print(f"✅ Token booked: {token_number} (ID: {token_id})")
        
        # 4. Check-in
        print("\n[4] Checking in...")
        result = post(f"{BASE}/check-in/{token_id}/", {})
        print("Result:", result)
        
        # 5. Doctor queue
        print("\n[5] Doctor Queue (Doctor ID: 1)")
        result = get(f"{BASE}/doctor-queue/1/")
        print(f"Queue length: {result.get('queue_length', 0)}")
        
        # 6. Start consultation
        print("\n[6] Start Consultation...")
        result = post(f"{BASE}/start-consult/{token_id}/", {})
        print("Result:", result)
        
        # 7. Complete consultation
        print("\n[7] Complete Consultation...")
        result = post(f"{BASE}/complete-consult/{token_id}/", {})
        print("Result:", result)
        
    else:
        print("❌ Booking failed")
else:
    print("❌ No slots available. Add a slot via admin panel.")

print("\n" + "=" * 50)
print("TESTING DONE")