"""
Test de 3 scénarios différents pour valider le pipeline F&B Operations Agent
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
API_URL = "http://127.0.0.1:8000"
PREDICT_ENDPOINT = f"{API_URL}/predict"

# Scénarios de test
SCENARIOS = [
    {
        "name": "Concert Coldplay",
        "description": "Grand concert au Stade de France",
        "payload": {
            "date": "2024-11-20",
            "events": "Concert Coldplay au Stade de France, soirée ensoleillée",
            "weather": "Ciel dégagé, 22°C"
        }
    },
    {
        "name": "Match de foot",
        "description": "Match de football avec promotion",
        "payload": {
            "date": "2024-11-21",
            "events": "Match de foot à 500m, happy hour promotion, écran géant",
            "weather": "Nuageux, 15°C, vent léger"
        }
    },
    {
        "name": "Festival jazz",
        "description": "Festival de jazz en centre-ville",
        "payload": {
            "date": "2024-11-22",
            "events": "Festival jazz downtown, scène extérieure, food trucks",
            "weather": "Ensoleillé, 20°C, ciel bleu"
        }
    }
]

def test_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Teste un scénario et retourne les résultats
    """
    print(f"\n{'='*70}")
    print(f"📋 SCÉNARIO: {scenario['name']}")
    print(f"{'='*70}")
    print(f"📝 Description: {scenario['description']}")
    print(f"\n📤 Payload:")
    print(json.dumps(scenario['payload'], indent=2, ensure_ascii=False))
    
    start_time = time.time()
    
    try:
        print(f"\n⏳ Envoi de la requête...")
        response = requests.post(
            PREDICT_ENDPOINT,
            json=scenario['payload'],
            timeout=60
        )
        
        elapsed_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"\n✅ PRÉDICTION RÉUSSIE (temps: {elapsed_time:.2f}s)")
            print(f"\n🎯 RÉSULTATS:")
            print(f"   • Covers attendus: {result.get('expected_covers')}")
            print(f"   • Staff recommandé: {result.get('recommended_staff')}")
            print(f"   • Confiance: {result.get('confidence')}%")
            print(f"\n🔑 FACTEURS CLÉS:")
            for i, factor in enumerate(result.get('key_factors', []), 1):
                print(f"   {i}. {factor}")
            
            return {
                "scenario": scenario['name'],
                "status": "success",
                "time": elapsed_time,
                "covers": result.get('expected_covers'),
                "staff": result.get('recommended_staff'),
                "confidence": result.get('confidence'),
                "key_factors": result.get('key_factors', [])
            }
        else:
            print(f"\n❌ ERREUR: Status Code {response.status_code}")
            print(f"   Réponse: {response.text}")
            return {
                "scenario": scenario['name'],
                "status": "error",
                "code": response.status_code,
                "error": response.text
            }
            
    except requests.exceptions.Timeout:
        print(f"\n❌ TIMEOUT: La requête a pris plus de 60 secondes")
        return {
            "scenario": scenario['name'],
            "status": "timeout"
        }
    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERREUR DE REQUÊTE: {e}")
        return {
            "scenario": scenario['name'],
            "status": "exception",
            "error": str(e)
        }

def print_summary(results: list):
    """
    Affiche un résumé des résultats de tous les scénarios
    """
    print(f"\n{'='*70}")
    print("📊 RÉSUMÉ DES TESTS")
    print(f"{'='*70}")
    
    successful = [r for r in results if r.get('status') == 'success']
    failed = [r for r in results if r.get('status') != 'success']
    
    print(f"\n✅ Succès: {len(successful)}/{len(results)}")
    print(f"❌ Échecs: {len(failed)}/{len(results)}")
    
    if successful:
        print(f"\n📈 MÉTRIQUES MOYENNES:")
        avg_covers = sum(r.get('covers', 0) for r in successful) / len(successful)
        avg_staff = sum(r.get('staff', 0) for r in successful) / len(successful)
        avg_confidence = sum(r.get('confidence', 0) for r in successful) / len(successful)
        avg_time = sum(r.get('time', 0) for r in successful) / len(successful)
        
        print(f"   • Covers moyens: {avg_covers:.1f}")
        print(f"   • Staff moyen: {avg_staff:.1f}")
        print(f"   • Confiance moyenne: {avg_confidence:.1f}%")
        print(f"   • Temps moyen: {avg_time:.2f}s")
        
        print(f"\n📋 DÉTAIL PAR SCÉNARIO:")
        for result in results:
            status_icon = "✅" if result.get('status') == 'success' else "❌"
            print(f"\n{status_icon} {result.get('scenario')}")
            if result.get('status') == 'success':
                print(f"   → {result.get('covers')} covers | "
                      f"{result.get('staff')} staff | "
                      f"{result.get('confidence')}% confiance | "
                      f"{result.get('time', 0):.2f}s")
            else:
                print(f"   → Erreur: {result.get('error', result.get('status', 'unknown'))}")

def main():
    """
    Fonction principale : teste les 3 scénarios
    """
    print("="*70)
    print("🚀 TEST DE 3 SCÉNARIOS - F&B OPERATIONS AGENT")
    print("="*70)
    print(f"\n📍 API URL: {API_URL}")
    print(f"📚 Documentation: {API_URL}/docs")
    
    # Vérification rapide de l'API
    try:
        health_check = requests.get(f"{API_URL}/docs", timeout=5)
        if health_check.status_code != 200:
            print(f"\n⚠️  L'API semble avoir un problème (code: {health_check.status_code})")
            print("   Continuons quand même...")
    except:
        print(f"\n⚠️  Impossible de vérifier l'API")
        print("   Assurez-vous qu'elle est lancée sur http://127.0.0.1:8000")
        print("   Commande: python start_api.py")
        return
    
    # Test de chaque scénario
    results = []
    for i, scenario in enumerate(SCENARIOS, 1):
        print(f"\n{'#'*70}")
        print(f"TEST {i}/{len(SCENARIOS)}")
        print(f"{'#'*70}")
        
        result = test_scenario(scenario)
        results.append(result)
        
        # Pause entre les tests
        if i < len(SCENARIOS):
            print(f"\n⏸️  Pause de 2 secondes avant le prochain test...")
            time.sleep(2)
    
    # Résumé final
    print_summary(results)
    
    # Export JSON (optionnel)
    export_file = "test_results.json"
    with open(export_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Résultats exportés dans: {export_file}")
    
    print(f"\n{'='*70}")
    print("✅ TESTS TERMINÉS")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()

