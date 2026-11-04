# Intelligence Feed — Journal géopolitique personnel

**Objectif : un seul grand article de synthèse hebdomadaire**, original et rédigé en français, construit à partir d'un grand nombre d'analyses géopolitiques (ISW, CSIS, RUSI, ECFR). Le résultat est distribué dans **Feeder** via RSS en contenu intégral, et disponible en HTML sur GitHub Pages.

## Fonctionnement

- **Collecte** : le script `sources.py` agrège des publications récentes, datées et dédupliquées, sur sept jours, jusqu'à 100 candidats. Cela ne signifie pas que 100 articles complets ont été lus : ISW bloque notamment la récupération automatique ; pour certains éditeurs, seuls le titre et l'extrait RSS sont disponibles.
- **Recherche et rédaction** : `weekly.py` transmet les candidats au modèle OpenAI avec recherche web. L'IA compose un **nouvel article de 10–15 minutes** avec un résumé, 4–6 dossiers, enjeux, points à surveiller, références précises et meilleurs articles à consulter. Aucune liste de “1 article sélectionné par jour”.
- **Publication** : `magazine.py` crée `docs/weekly/YYYY-MM-DD/index.html`, la dernière édition sur `docs/index.html`, un index `docs/editions.json` et un **flux RSS contenant l'article complet** dans `description` et `content:encoded`. Les précédentes éditions sont archivées.
- **Programmation** : tous les dimanches vers 18h30/19h30 heure de Paris selon l'heure d'été/hiver. L'automatisation ChatGPT du dimanche est séparée et reste active tant que l'utilisateur ne demande pas de l'arrêter.

## Sources

- ISW via la page de découverte Feeder, qui fournit les liens et extraits lorsque ISW bloque GitHub (Cloudflare 403).
- CSIS Analysis via Feeder.
- RUSI — flux RSS officiel de publications.
- ECFR — flux RSS officiel d'articles et de publications.

Le workflow s'arrête sans publier de fausse édition s'il manque des sources ou si l'article généré n'est pas correctement structuré.

## Cartes et droits

**À noter :** la politique ISW de janvier 2026 encadre l'incorporation de ses cartes dans des produits d'analyse tiers et peut requérir une autorisation écrite. Cette version inclut des liens directs vers les rapports contenant les cartes, mais **ne copie pas leurs images dans le journal**. Les cartes intégrées sont une prochaine étape, à partir de sources explicitement réutilisables ou avec permission. Les liens restent consultables directement via le navigateur intégré de Feeder.

## Configuration

- Ajouter `OPENAI_API_KEY` dans les **Repository secrets** GitHub Actions ; l'API est facturée séparément de ChatGPT.
- GitHub Pages doit utiliser **GitHub Actions** comme méthode de déploiement.
- Dans Feeder, conserver l'abonnement existant au flux : `https://clementhuguet75.github.io/Cl-ment-own-newsletter-/feed.xml`.
- Déclenchement manuel possible : GitHub Actions → *Publish weekly intelligence digest* → Run workflow.
- `docs/last_run.json` donne, après chaque succès, le **nombre réel d'articles candidats** et la ventilation par éditeur. Cela permet de mesurer ce qui a été examiné, sans faire croire à la lecture intégrale de tous les textes.

## Limites

La qualité finale dépend des sources accessibles et de la capacité de recherche web ; les citations indiquent les publications correspondantes, mais les analyses IA ne doivent pas être considérées comme des faits automatiquement confirmés. Aucun article externe n'est recopié en totalité.

**Déploiement de cette version : à valider sur la première exécution du workflow.**

Projet personnel non affilié aux éditeurs ou à Feeder.
