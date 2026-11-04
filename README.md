# Intelligence Feed — ISW

Un flux RSS personnel de 3 à 5 publications ISW sélectionnées par IA chaque semaine. Les entrées du flux pointent vers les articles officiels, pour conserver leurs cartes et illustrations dans le navigateur intégré de Feeder.

## Mise en service

1. Publier le dépôt via GitHub Pages (pour un compte GitHub Free, le dépôt doit être public ; pour certains forfaits payants, un dépôt privé est éligible).
2. Créer un secret GitHub Actions nommé `OPENAI_API_KEY` (ne jamais ajouter la clé dans un fichier ni dans ce chat).
3. Dans Settings → Pages → Build and deployment, sélectionner GitHub Actions.
4. Déclencher Actions → Publish curated ISW RSS → Run workflow, puis tester la page `/feed.xml`.
5. Dans Feeder, suivre l'URL publiée et se désabonner de l'ancien flux brut ISW lorsque tout marche.

## Fonctionnement

- Le workflow s'exécute chaque dimanche, collecte les analyses de la semaine, sélectionne jusqu'à cinq contenus majeurs, génère `docs/feed.xml`, puis déploie ce répertoire sur GitHub Pages.
- Les articles et cartes restent hébergés par ISW ; l'item RSS contient le titre, le lien original et un commentaire court en français.
- Une semaine avec peu d'actualité peut comporter moins de trois articles.
- Le traitement IA via l'API OpenAI est facturé séparément de ChatGPT.

## État

Le dépôt contient un prototype à valider de bout en bout (l'accès web depuis le workflow, l'extraction des contenus, la clé API et la publication). Le flux initial est volontairement vide, sans faux articles.
