"""
Test complet du pipeline F&B Operations Agent
Teste l'endpoint /predict avec un scénario réel
"""

import requests
import json
import time

# Configuration
API_URL = "http://127.0.0.1:8000"
PREDICT_ENDPOINT = f"{API_URL}/predict"
DOCS_ENDPOINT = f"{API_URL}/docs"

def test_api_health():
    """Vérifie que l'API est accessible"""
    print("🔍 Vérification de l'API...")
    try:
        # Augmentation du timeout pour la vérification initiale
        response = requests.get(f"{API_URL}/docs", timeout=10)
        if response.status_code == 200:
            print("✅ API est accessible")
            return True
        else:
            print(f"❌ API retourne le code {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        print(f"⚠️  Timeout lors de la vérification (l'API peut être en cours de démarrage)")
        print(f"   Tentative de connexion directe à l'endpoint /predict...")
        # Essai de connexion directe
        try:
            test_response = requests.get(f"{API_URL}/", timeout=5)
            print("✅ API répond (mais /docs peut être lent)")
            return True
        except:
            print(f"❌ L'API ne répond pas. Assurez-vous qu'elle est lancée sur {API_URL}")
            print(f"   Commande pour lancer: python start_api.py")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur de connexion à l'API: {e}")
        print(f"   Assurez-vous que l'API est lancée sur {API_URL}")
        print(f"   Commande pour lancer: python start_api.py")
        return False

def test_predict_endpoint():
    """Teste l'endpoint /predict avec un payload complet"""
    print("\n" + "="*60)
    print("🧪 TEST DE L'ENDPOINT /predict")
    print("="*60)
    
    # Payload de test
    payload = {
        "date": "2024-11-20",
        "events": "Concert Coldplay nearby, sunny evening",
        "weather": "Sunny, 22°C, light breeze"
    }
    
    print(f"\n📤 Payload envoyé:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    # Mesure du temps d'exécution
    start_time = time.time()
    
    try:
        print(f"\n⏳ Envoi de la requête à {PREDICT_ENDPOINT}...")
        response = requests.post(
            PREDICT_ENDPOINT,
            json=payload,
            timeout=60  # 60 secondes pour le traitement complet
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"\n📥 Réponse reçue (temps: {elapsed_time:.2f}s)")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ PRÉDICTION RÉUSSIE!")
            print("\n" + "="*60)
            print("📊 RÉSULTATS DE LA PRÉDICTION")
            print("="*60)
            print(f"📅 Date: {result.get('date')}")
            print(f"🎪 Événements: {result.get('events')}")
            print(f"🌤️  Météo: {result.get('weather')}")
            print(f"\n🎯 PRÉDICTIONS:")
            print(f"   • Covers attendus: {result.get('expected_covers')}")
            print(f"   • Staff recommandé: {result.get('recommended_staff')}")
            print(f"   • Confiance: {result.get('confidence')}%")
            print(f"\n🔑 FACTEURS CLÉS:")
            for i, factor in enumerate(result.get('key_factors', []), 1):
                print(f"   {i}. {factor}")
            print("\n" + "="*60)
            
            # Format JSON complet
            print("\n📄 Réponse JSON complète:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            return True
        else:
            print(f"\n❌ ERREUR: Status Code {response.status_code}")
            print(f"   Réponse: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"\n❌ TIMEOUT: La requête a pris plus de 60 secondes")
        print("   Le pipeline peut être en cours d'exécution...")
        return False
    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERREUR DE REQUÊTE: {e}")
        return False

def test_multiple_scenarios():
    """Teste plusieurs scénarios différents"""
    print("\n" + "="*60)
    print("🧪 TESTS MULTIPLES SCÉNARIOS")
    print("="*60)
    
    scenarios = [
        {
            "name": "Concert en soirée",
            "payload": {
                "date": "2024-11-20",
                "events": "Concert Coldplay nearby, sunny evening",
                "weather": "Sunny, 22°C, light breeze"
            }
        },
        {
            "name": "Match de foot",
            "payload": {
                "date": "2024-11-21",
                "events": "Football match at 500m, happy hour promotion",
                "weather": "Cloudy, 15°C"
            }
        },
        {
            "name": "Événement corporate",
            "payload": {
                "date": "2024-11-22",
                "events": "Corporate dinner, 50 people reservation",
                "weather": "Rainy, 12°C"
            }
        }
    ]
    
    results = []
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'='*60}")
        print(f"📋 Scénario {i}/{len(scenarios)}: {scenario['name']}")
        print(f"{'='*60}")
        
        try:
            response = requests.post(
                PREDICT_ENDPOINT,
                json=scenario['payload'],
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Succès: {result.get('expected_covers')} covers prévus")
                results.append({
                    "scenario": scenario['name'],
                    "status": "success",
                    "covers": result.get('expected_covers'),
                    "confidence": result.get('confidence')
                })
            else:
                print(f"❌ Erreur: {response.status_code}")
                results.append({
                    "scenario": scenario['name'],
                    "status": "error",
                    "code": response.status_code
                })
        except Exception as e:
            print(f"❌ Exception: {e}")
            results.append({
                "scenario": scenario['name'],
                "status": "exception",
                "error": str(e)
            })
        
        # Pause entre les requêtes
        if i < len(scenarios):
            time.sleep(2)
    
    # Résumé
    print("\n" + "="*60)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*60)
    for result in results:
        status_icon = "✅" if result['status'] == "success" else "❌"
        print(f"{status_icon} {result['scenario']}: {result.get('status', 'unknown')}")
        if result['status'] == "success":
            print(f"   → {result.get('covers')} covers ({result.get('confidence')}% confiance)")

def main():
    """Fonction principale de test"""
    print("="*60)
    print("🚀 TEST COMPLET DU PIPELINE F&B OPERATIONS AGENT")
    print("="*60)
    print(f"\n📍 API URL: {API_URL}")
    print(f"📚 Documentation: {DOCS_ENDPOINT}")
    
    # Test 1: Vérification de l'API
    if not test_api_health():
        print("\n❌ L'API n'est pas accessible. Arrêt des tests.")
        return
    
    # Test 2: Test de l'endpoint /predict
    success = test_predict_endpoint()
    
    if success:
        # Test 3: Tests multiples (optionnel - décommenter pour activer)
        # print("\n" + "="*60)
        # user_input = input("Voulez-vous tester plusieurs scénarios? (o/n): ")
        # if user_input.lower() in ['o', 'oui', 'y', 'yes']:
        #     test_multiple_scenarios()
        pass
    
    print("\n" + "="*60)
    print("✅ TESTS TERMINÉS")
    print("="*60)

if __name__ == "__main__":
    main()

