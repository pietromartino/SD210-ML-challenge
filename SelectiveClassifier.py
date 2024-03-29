import numpy as np
import copy

class SelectiveClassifier(object):

    # Sort of "wrapper" classifier that actually creates multiple copies 
    # of the classifier provided, each one trained on a different selection of columns
    
    # ------------------------------------ WARNING ------------------------------------
    # X (and y) data provided to both train and test methods must be Pandas dataframes,
    # since no condition can be evaluated on a simple array [] as required by sklearn.
    # To evaluate a condition on items, columns names/indexes are required.
    
    # In the training phase, for each provided selection we create and train a classifier on all columns
    # but the ones in the selection (see below). 
    # If no selections are provided, this class returns exactly the same results as using the classifier itself.
    
    # At prediction time, we need to make a distinction between classifiers created by selections 
    # with a predicate and classifiers created without a predicate. Classifiers with no predicate predict 
    # all items and average their predictions with the base classifier. Classifiers that are in a selection
    # containing a predicate will predict only the items that satisfy the predicate: these predictions
    # will be then either substituted to existing predictions or averaged with them.  
    
    # Selections = list of [ dict {
    #
    #   predicate: lambda function to evaluate
    #   columns: columns not to select/consider when training classifiers
    #
    #}]
    
    # fill_predicates : specifies wheter predictions made by classifier that have a predicate
                      # should fill previous predictions, or be averaged with them. 

    # allow_multipredicates : specifies wheter an item is allowed to be the subject of multiple predicates

    def __init__(self, clf, selections=[], fill_predicates=True, allow_multipredicates=True):
        self.clf = clf
        self.selections = selections
        self.fill_predicates = fill_predicates
        self.allow_multipredicates = allow_multipredicates
        self.sub_clfs = []
        return 
    
    def fit(self, X, y=None, classes=None):
        if self.clf is None:
             raise ValueError("Please provide a classifier.")
        
        # While fitting i don't care much about predicates, just train 
        # classifiers on differents datasets.
        if len(self.selections) > 0:
            for s in self.selections:
                sub_clf = copy.copy(self.clf)
                sub_clf.fit(X.drop(s['columns'], axis=1).values, y.values.ravel())   
                s['classifier'] = sub_clf
                
        # Still train base clf
        self.clf.fit(X.values,y.values.ravel())
        return self
   
    def predict(self, X):
        return np.argmax(self.predict_proba(X), axis=1)
    
    def predict_proba(self, X):
        if len(self.selections) < 1:
            return self.clf.predict_proba(X.values)

        # Predictions on whole X set (used by base clf + clf with simple columns selections / no predicate)
        preds = [self.clf.predict_proba(X.values)]
        # Predictions on items subject of a predicate
        subset_preds = []
        
        # Get predictions
        for s in self.selections:
            if 'predicate' in s:
                subset = X[X.apply(s['predicate'], axis=1)]
                subset_preds.append( dict(zip(subset.index.values, s['classifier'].predict_proba(X.drop(s['columns'], axis=1).values))) ) 
            else:
                preds.append(s['classifier'].predict_proba(X.drop(s['columns'], axis=1).values))
        
        # Merge predictions of predicates
        # From several dicts [ {}, {} ] to single one { 'id' : [...] , 'id' : [...] }
        merged_subpred = {}
        for subpred in subset_preds:
            for key, value in subpred.items():
                if key not in merged_subpred:
                    merged_subpred[key] = []
                else:
                    if self.allow_multipredicates is False:
                        raise ValueError('Impossible to merge predictions generated by predicates ' + 
                                           'applied to the same item when allow_multipredicates is False')
                merged_subpred[key].append(value)
        
        # Average predictions on all items
#         print('predictions before averaging')    
#         print(preds)
        preds_avg = np.average(preds, axis=0)
#         print('predictions after averaging')    
#         print(preds_avg)   
        
#         print('subpredictions before averaging')    
#         print(merged_subpred)
        for key, value in merged_subpred.items():
            # Average (eventually) predictions on predicate results and substitute them 
            # to previous predictions
            temp_avg = np.average(merged_subpred[key], axis=0)
 #            print('key ' + str(key) + ' avg ' + str(temp_avg))
            preds_avg[key] = temp_avg
 #        print('subpredictions after averaging and filling')    
#         print(preds_avg)    
        # My preds_avg has the average predictions on the whole dataset for items that
        # weren't subject of a predicate, and the (eventual average) prediction of predicate results
        # for items interested by a predicate. Exact fill, return.
        if self.fill_predicates is True:
            return preds_avg
        # If not filling but averaging, just average preds_avg with preds: fields for items not
        # interested by a predicate already contain the average value (no changes), others 
        # contain prediction results after applying the predicate.
        else:
            # Average everything together
            preds.append(preds_avg)
            return np.average(preds, axis=0)   