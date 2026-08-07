import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate('serviceAccount.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

doc = db.collection('bajush_gold_price').document('latest').get()

if not doc.exists:
    print("No 'latest' document found in Firestore.")
else:
    data = doc.to_dict()
    print("=== Firestore Data ===")
    gold = data.get('gold', {})
    for k, v in gold.items():
        print(f"  {k}: {v}")
    print(f"  Fetched at: {data.get('fetchedAt', 'N/A')}")
