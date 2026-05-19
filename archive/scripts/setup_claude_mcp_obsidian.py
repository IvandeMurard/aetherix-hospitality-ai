"""
Script pour configurer MCP Obsidian dans Claude Desktop
Crée ou met à jour le fichier claude_desktop_config.json
"""

import os
import json
import sys
from pathlib import Path

# Chemin du fichier de configuration
CONFIG_DIR = Path(os.getenv('APPDATA')) / 'Claude'
CONFIG_FILE = CONFIG_DIR / 'claude_desktop_config.json'

# Chemin du vault Obsidian
VAULT_PATH = r"C:\Users\IVAN\OneDrive\Documents\Agentic AI Hospitality"

# Configuration MCP Obsidian
# Utilise @mauricio.wolff/mcp-obsidian (projet bitbonsai/mcp-obsidian)
# qui supporte le protocole 2025-06-18 et create/write/patch notes
OBSIDIAN_CONFIG = {
    "command": "npx",
    "args": ["@mauricio.wolff/mcp-obsidian@latest", VAULT_PATH]
}

def main():
    print("=" * 60)
    print("CONFIGURATION MCP OBSIDIAN POUR CLAUDE DESKTOP")
    print("=" * 60)
    print(f"\nFichier de configuration: {CONFIG_FILE}")
    print(f"Vault Obsidian: {VAULT_PATH}")
    
    # Vérifier que le vault existe
    if not Path(VAULT_PATH).exists():
        print(f"\n[ERREUR] Le vault Obsidian n'existe pas: {VAULT_PATH}")
        sys.exit(1)
    print(f"[OK] Vault Obsidian trouvé")
    
    # Créer le répertoire si nécessaire
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Répertoire de configuration prêt")
    
    # Lire la configuration existante ou créer une nouvelle
    if CONFIG_FILE.exists():
        print(f"\n[INFO] Fichier de configuration existant trouvé")
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print("[OK] Configuration existante chargée")
        except json.JSONDecodeError as e:
            print(f"[ERREUR] Fichier JSON invalide: {e}")
            print("[INFO] Création d'une nouvelle configuration")
            config = {"mcpServers": {}}
    else:
        print(f"\n[INFO] Création d'un nouveau fichier de configuration")
        config = {"mcpServers": {}}
    
    # Vérifier si Obsidian est déjà configuré
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    if "obsidian" in config["mcpServers"]:
        print(f"\n[INFO] Configuration Obsidian existante trouvée")
        print(f"  Ancienne config: {config['mcpServers']['obsidian']}")
        print(f"  Nouvelle config: {OBSIDIAN_CONFIG}")
        response = input("\nVoulez-vous remplacer la configuration existante? (o/n): ")
        if response.lower() != 'o':
            print("[INFO] Configuration non modifiée")
            return
    
    # Ajouter ou mettre à jour la configuration Obsidian
    config["mcpServers"]["obsidian"] = OBSIDIAN_CONFIG
    print(f"\n[OK] Configuration Obsidian ajoutée/mise à jour")
    
    # Afficher les autres serveurs MCP configurés
    other_servers = [k for k in config["mcpServers"].keys() if k != "obsidian"]
    if other_servers:
        print(f"[INFO] Autres serveurs MCP configurés: {', '.join(other_servers)}")
    
    # Écrire la configuration
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Fichier de configuration sauvegardé")
        
        # Valider le JSON
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            json.load(f)
        print("[OK] JSON valide")
        
    except Exception as e:
        print(f"\n[ERREUR] Échec de l'écriture: {e}")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("CONFIGURATION TERMINÉE")
    print("=" * 60)
    print("\n[IMPORTANT] Redémarrez Claude Desktop pour que la configuration soit prise en compte.")
    print(f"\nFichier créé/modifié: {CONFIG_FILE}")

if __name__ == "__main__":
    main()
