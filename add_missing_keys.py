"""
Script pour ajouter les clés API manquantes au fichier .env
"""

import os
from pathlib import Path

def add_missing_keys():
    """Ajoute les clés manquantes au fichier .env"""
    
    env_path = Path(".env")
    
    # Lire le contenu actuel
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
    else:
        content = ""
    
    # Vérifier quelles clés manquent
    missing_keys = []
    
    if "PREDICTHQ_API_KEY" not in content:
        missing_keys.append('PREDICTHQ_API_KEY="votre_clé_predictHQ_ici"')
    
    if "OPENWEATHER_API_KEY" not in content:
        missing_keys.append('OPENWEATHER_API_KEY="votre_clé_openweather_ici"')
    
    if missing_keys:
        print("🔧 Ajout des clés manquantes au fichier .env...\n")
        
        # Ajouter les clés manquantes
        if content and not content.endswith('\n'):
            content += '\n'
        
        content += '\n# Clés API supplémentaires\n'
        for key in missing_keys:
            content += key + '\n'
            print(f"✅ Ajouté: {key.split('=')[0]}")
        
        # Écrire le fichier
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✅ Fichier .env mis à jour!")
        print(f"\n⚠️  IMPORTANT: Remplacez 'votre_clé_...' par vos vraies clés API")
        print(f"   1. PREDICTHQ_API_KEY: https://predicthq.com/")
        print(f"   2. OPENWEATHER_API_KEY: https://openweathermap.org/api")
    else:
        print("✅ Toutes les clés sont déjà présentes dans .env")
    
    # Afficher le contenu actuel
    print(f"\n📄 Contenu actuel du .env:")
    print("=" * 60)
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if line.strip() and not line.strip().startswith('#'):
                    key = line.split('=')[0].strip()
                    # Masquer la valeur pour la sécurité
                    if '=' in line:
                        value = line.split('=', 1)[1].strip()
                        if len(value) > 20:
                            masked = f"{value[:10]}...{value[-4:]}"
                        else:
                            masked = "***"
                        print(f"  {key} = {masked}")
    print("=" * 60)

if __name__ == "__main__":
    add_missing_keys()

