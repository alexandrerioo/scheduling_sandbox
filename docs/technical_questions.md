## Part 1: Theoretical Questions (20 min)

### A. Data Engineering

- Quelle est la différence entre un LEFT JOIN et un INNER JOIN ? Donne un cas où le choix change le résultat
- Quelle est la différence entre un data lake et un data warehouse?
- Quelle est la différence entre ETL et ELT ? Quand préfères-tu l'un ou l'autre ?
- Quelle est la différence entre batch processing et stream processing?

### A. Data understanding and generation

1. What is the difference between correlation and causation? Give an example where high correlation doesn't imply causation.
2. On te donne des données issues d’un ERP (commandes, production, stocks), mais elles sont incomplètes et parfois incohérentes. Que fais-tu en premier ?

### B. Data pre-processing

1. You receive a 50GB CSV file from a client. How do you approach loading and processing it?
2. How do you detect outliers? What's the difference between an outlier and an erroneous value?
3. Data Normalization
    1. What is data normalization and why is it important for neural networks?
    2. Compare Min-Max scaling vs. StandardScaler. When would you use each?
    3. Do you normalize before or after the train/val/test split, and why?

### C. Feature Engineering

1. What is the purpose of a correlation matrix? What are its limitations?

### D. Modelling

1. Learning Paradigms
   - Give an example of a problem that would be better solved with unsupervised learning.
   - Give an example of a problem that would be better solved with supervised learning.
   - Give an example of a problem that would be better solved with reinforcement learning.
   - Give an example of a problem that would be better solved with semi-supervised learning.
   - Are optimization algorithms considered part of artificial intelligence/machine learning? explain
2. Ensemble Methods
   - You have a Random Forest that's overfitting. Would you decrease the depth of trees or reduce the number of estimators? Justify your choice.
   - What are the key differences between bagging and boosting?

### E. Training

1.  Model Performance Issues
   - Define overfitting and underfitting. How would you identify each in practice?
   - List and explain at least 1 technique to address overfitting in the context of deep learning.
2. Train-test split
    1. What is cross-validation? Why is it better than a simple train/test split?
    2. You have two years of placed order data and wants to build a forecasting model to support production decisions. How do you split the data? 

### F. Evaluation

1. Evaluation Metrics
    - You build a model for detecting defective parts at the end of the production line. Your model obtains 99% accuracy on your test set. Is it ready for production?

### G. Deployment and Monitoring

1. A model performs well in testing but poorly in production. What could be the causes?

### H. Optimisation Concepts

1. When facing an optimisation problem, what are the elements you must define?