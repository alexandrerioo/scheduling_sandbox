## Exo 1

*On reçoit de la part de nos clients un CSV contenant la liste des commandes à produire. Ce CSV est stocké dans Bigquery, transformé puis stocké dans pg. Le process de bout en bout fonctionnait bien avec des imports de 100k lignes, mais un client s’est mis à nous envoyer des imports de 2 millions de lignes, ce qui cause des OOM errors sur nos serveurs. Si tu étais à notre place, comment aurais-tu traité cet import?*

*Niveau 1: je fais du streaming / chunking*

*Rajouter ensuite la contrainte : 1 commande est éclatée sur plusieurs lignes, dans le désordre dans le fichier, et on a besoin de connaitre la première et la dernière étape pour chaque commande*

*Niveau 2 : tu t’appuies sur bigquery pour grouper les OFs (Pb: perf)*

*Niveau 3 : on stream plusieurs fois. La première fois pour récupérer les numéros de ligne sur lesquels apparaissent chaque commande. Les fois suivantes pour traiter les OFs par batch (la lecture du fichier prends ~2s)*

## Exo 2

**Data structure Oplit : on reçoit de nos clients leurs données de commandes clients. Ce sont des CSV, avec toujours 3 colonnes fixes (date, quantité, ID) et plein d’autres colonnes supplémentaires. On souhaite visualiser les 3 colonnes principales dans Oplit, et pouvoir zoomer sur une commande spécifique pour avoir toutes ses infos. Dans une base de données relationnelle, quel schéma de BDD tu aimerais utiliser pour stocker ces CSV ?**

*⇒ Est-ce qu’il pense bien aux jsonb ? Est-ce qu’il connait les index sur les champs jsonb ? (GIN index)*

## Exo 3

**stream on bigquery: on cherche à basculer un gros volume de données de bigquery vers postgresql. Un serveur seul ne peut pas faire un SELECT * pour récupérer toutes les données. Comment ferais-tu pour contourner cette limite ?**

*⇒ une solution est de faire du streaming des données. Bigquery ne permet pas le traitement par batch*