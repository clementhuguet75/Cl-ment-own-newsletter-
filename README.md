# Intelligence Feed — ISW

Un flux RSS personnel qui retient au maximum cinq analyses majeures de l'Institute for the Study of War par semaine. Le flux ne republie ni articles complets ni cartes : les liens ouvrent les publications ISW originales dans le navigateur intégré de Feeder, pour conserver les images.

## Fonctionnement

1. GitHub Actions vérifie chaque jour les titres et liens directs ISW via la page publique [Feeder ISW](https://feeder.co/discover/fbbae6245c/understandingwar-org) lorsque le site officiel refuse l'accès automatisé (HTTP 403).
2. L'API OpenAI, avec recherche web, vérifie les candidats avant de sélectionner au maximum un nouvel article par jour et cinq par semaine. Elle peut ne rien retenir si les sources ne suffisent pas.
3. Le flux RSS est généré dans `docs/feed.xml` et déployé via GitHub Pages. Les sélections des 60 derniers jours restent visibles.
4. Le weekly éditorial ChatGPT du dimanche est indépendant de cette publication RSS.

## Activation

- Dépôt GitHub **public** et GitHub Pages : **Settings → Pages → Build and deployment → GitHub Actions**.
- Créer un **Repository secret** nommé exactement `OPENAI_API_KEY` dans **Settings → Secrets and variables → Actions**. La clé ne doit jamais figurer dans le code, les logs ni un message ChatGPT ; la facturation API est distincte de ChatGPT.
- Vérifier l'exécution dans **Actions → Publish curated ISW RSS**. Sans secret fonctionnel, le workflow échouera et ne remplacera pas les articles existants.
- Lorsque l'exécution de déploiement réussit, ajouter `https://clementhuguet75.github.io/Cl-ment-own-newsletter-/feed.xml` à Feeder et retirer ensuite le flux ISW brut.

## État de validation (4 novembre 2026)

Le dépôt et les tests locaux du RSS sont validés. Le site ISW renvoie HTTP 403 aux serveurs GitHub ; les liens d'articles ISW publiés dans Feeder sont accessibles depuis GitHub. Les exécutions n'ont **pas encore publié** de flux : la variable secrète `OPENAI_API_KEY` apparaît vide dans l'environnement du workflow. La sélection IA, GitHub Pages et la lecture du flux définitif restent à tester en bout en bout.

Projet personnel non affilié à ISW ou Feeder.
