# ADR-005 : Assistant RAG Local (Ollama + LangChain) Hors Chemin Critique et Sans Privilèges

- **Statut** : Accepté
- **Date** : 2026-10-19
- **Contexte** : Le sujet demande un assistant RAG local utilisant Ollama et LangChain avec un modèle `<= 8B` paramètres pour assister les opérateurs dans la consultation des procédures et de l'architecture, sans être confondu avec l'automate de remédiation ni disposer d'accès privilégiés. Sur `HDV0-INF-P08`, Ollama `v0.23.0` et le manifeste `gemma4:e4b` sont présents.
- **Décision** :
  1. **Isolation du Chemin Critique** : La boucle de détection ML et de remédiation autonome ne dépend jamais du RAG ni d'Ollama. Si Ollama est indisponible ou lent, la reprise autonome s'exécute sans aucun impact.
  2. **Architecture d'Indexation et de Recherche** :
     - Découpage sémantique par sections Markdown (`#`, `##`, `###`) des fichiers de `docs/`, `AGENTS.md` et `infra/ansible/`.
     - Recherche hybride TF-IDF / cosinus (`scikit-learn`) + pipeline LangChain / Ollama (`OLLAMA_BASE_URL` configurable vers `http://127.0.0.1:11434` ou vers un PC IA dédié `http://192.168.137.x:11434`).
  3. **Garde-fous Anti-Hallucination et Anti-Injection de Prompt** :
     - Si le score de similarité documentaire est inférieur au seuil minimal (`0.12`), le service refuse de répondre et indique explicitement que l'information est absente de la base documentaire.
     - Chaque réponse cite obligatoirement le fichier source et la section exacte (`[Source: docs/...#Section]`).
     - Les documents récupérés sont encapsulés dans des balises de données passives ; le service RAG ne possède aucun client HTTP vers `executor` ni aucun outil d'exécution système.
- **Conséquences** :
  - Sécurité maximale contre les injections de prompt indirectes (Indirect Prompt Injection).
  - Transparence totale : si le démon Ollama n'est pas actif lors d'un test, le moteur documentaire retourne les extraits cités exacts en mode dégradé explicite (`llm_status: "OFFLINE_RETRIEVAL_ONLY"`), permettant de tester la recherche documentaire tout en marquant l'inférence LLM `BLOCKED` tant qu'Ollama n'est pas démarré.
