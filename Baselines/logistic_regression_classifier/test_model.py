import logging
import matplotlib.pyplot as plt
import numpy as np
import os
import pandas as pd
import seaborn as sns
import sys
import toml
from os.path import dirname, join, abspath
from pathlib import Path
from scipy import stats
from sklearn.linear_model import LogisticRegression

from model import LogisticClassifier

sys.path.insert(0, abspath(join(dirname(__file__), '..')))
from utils.utils import mkdir

# setting up logging
logging.basicConfig(format='%(asctime)s: %(levelname)s: %(message)s', level=logging.INFO)

# setting up file logging as well
file_logger = logging.FileHandler(Path(os.getcwd() / Path('Baseline-models.log')), mode='w')
file_logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_logger.setFormatter(formatter)
logging.getLogger().addHandler(file_logger)

# setting up logger for current module
logger = logging.getLogger(__name__)

# start logging
logger.info("Running linear regression model")

# read in meta data from TOML file
logger.info("Reading in meta data from TOML file")
with open('metadata_LCO.toml', 'r') as file:
    meta_data = toml.load(file)

# create linear regression object
logger.info("Creating linear regression object")
logistic_classifier = LogisticClassifier(meta_data["metadata"]["dataroot_drp"], meta_data["metadata"]["dataroot_feature"],
                                         meta_data["metadata"]["metric"], meta_data["metadata"]["task"],
                                         meta_data["metadata"]["remove_outliers"], meta_data["metadata"]["log_transform"],
                                         meta_data["metadata"]["feature_type"], meta_data["metadata"]["feature_selection"],
                                         meta_data["metadata"]["norm_feat"], meta_data["metadata"]["norm_method"],
                                         meta_data["metadata"]["CV_folds"], meta_data["metadata"]["n_cpus"],
                                         meta_data["metadata"]["HP_tuning"])

logistic_classifier.cell_line_views
logistic_classifier.drug_views

# prepare drug response data (splitting it)
logistic_classifier.get_drug_response_dataset()

# pre process the drp (y) data
logistic_classifier.data_processing()

# load cell viab/transcriptomic data doesn't matter, as long as cl names are the same as in the drug response data
scc_median = 0
best_scc = 0
best_nfeatures = None
for ntop in meta_data["metadata"]["HP_tuning_features"].get("nfeatures"):
    logger.info(f"Starting dataextraction / training / prediction loop for {ntop} features")
    logistic_classifier.get_feature_dataset(ntop)

    # fit the model
    logistic_classifier.train()

    # predict the ec50 values for the test set
    logistic_classifier.predict()

    # evaluate the model
    logistic_classifier.evaluate()
    scc_median = logistic_classifier.metric_df["scc"].median()

    # save the model if its scc is better than the previous one in best_model_attr
    if scc_median > best_scc:
        logger.info(f"New best model found with {ntop} features")
        best_model_attr = vars(logistic_classifier)
        best_scc = scc_median
        best_nfeatures = ntop

# get best maximum number of iterations
max_iter = []
for target in best_model_attr["models"]:
    target_model = best_model_attr["models"].get(target)
    if isinstance(target_model, LogisticRegression):
        max_iter.append(target_model.get_params()["max_iter"])
    else:
        max_iter.append(target_model.best_params_.get("max_iter"))

# there are more cl with models in best_model_attr["models"] than in best_model_attr["metric_df"] since there we calc.
# the scc for cls with more than one drug. Filter out the alpha and max_iter for cl models with more than one drug
best_models_params = pd.DataFrame({"max_iter": max_iter}, index=best_model_attr["models"].keys())
best_models_params = best_models_params.loc[best_model_attr["metric_df"].index]

best_model_attr["metric_df"]["nfeatures"] = best_nfeatures
best_model_attr["metric_df"]["max_iter"] = best_models_params["max_iter"]

# save model parameters and results
dir_path = "results_transcriptomics/"
# mkdir(dir_path)
logistic_classifier.save(dir_path, best_model_attr)

#################################################### DATA ANALYSIS #####################################################
logger.info("Performing data analysis")
logger.info(
    f"\n\nSummary statistics on {meta_data['metadata'].get('task')} - {meta_data['metadata'].get('feature_type')}:\n"
    f"{best_model_attr['metric_df'].describe()}\n")

sns.set(style="ticks")

### correlation coefficient distribution ###
fig, axs = plt.subplots(1, 2, sharey=True, figsize=(10, 5))
sns.histplot(best_model_attr["metric_df"]["pcc"], ax=axs[0])
sns.histplot(best_model_attr["metric_df"]["scc"], ax=axs[1])
median_value_pcc = best_model_attr["metric_df"]["pcc"].median()
median_value_scc = best_model_attr["metric_df"]["scc"].median()
axs[0].axvline(x=median_value_pcc, color='red', linestyle='dashed', linewidth=2, label='median')
axs[1].axvline(x=median_value_scc, color='red', linestyle='dashed', linewidth=2, label='median')
axs[0].set_xlabel("Pearsons's correlation coefficient (PCC)")
axs[1].set_xlabel("Spearman's correlation coefficient (SCC)")
plt.ylabel("count")
plt.suptitle(f"distribution of correlation coefficients "
             f"({meta_data['metadata'].get('task')} - {meta_data['metadata'].get('feature_type')})",
             fontsize=12, fontweight='bold')
# axs[0].legend()
# axs[1].legend()
sns.despine(right=True)
plt.show()
plt.close()

### scc vs variance ###
if meta_data['metadata'].get('feature_type') == "fingerprints":
    scc = best_model_attr["metric_df"]["scc"]
    pcc = best_model_attr["metric_df"]["pcc"]
    drp = best_model_attr["test_drp"]

    if logistic_classifier.task == "LPO":
        drp = best_model_attr["test_drp"]
        drp = drp.pivot(index="Primary Cell Line Name", columns="Compound", values=best_model_attr["metric"])
        var = drp.loc[scc.index].var(axis=1)
    else:
        var = drp[scc.index].var()

elif meta_data["metadata"].get('feature_type') == "gene_expression":
    scc = best_model_attr["metric_df"]["scc"]
    pcc = best_model_attr["metric_df"]["pcc"]
    drp = best_model_attr["test_drp"]

    if logistic_classifier.task == "LPO":
        drp = best_model_attr["test_drp"].reset_index()
        drp = drp.pivot(index="Compound", columns="Primary Cell Line Name", values=best_model_attr["metric"])
        var = drp.loc[scc.index].var(axis=1)
    else:
        var = drp.loc[scc.index].var(axis=1)

fig, axs = plt.subplot_mosaic([['a)', 'c)'], ['b)', 'c)']], figsize=(15, 10))
axs['a)'].scatter(var, pcc)
axs['b)'].scatter(var, scc)
plt.xlabel("variance")
axs['a)'].set_ylabel("Pearsons's correlation coefficient")
axs['b)'].set_ylabel("Spearman's correlation coefficient")
axs['a)'].set_title(f"correlation coefficient vs variance "
                    f"{meta_data['metadata'].get('task')} - {meta_data['metadata'].get('feature_type')}",
                    fontsize=12, fontweight='bold')
# sns.despine(right = True)
# plt.tight_layout()
# plt.show()
# plt.close()

### analysing how many coef. set to 0 ###
beta0_arr = []
targets = []

for target in best_model_attr["models"]:
    if isinstance(best_model_attr["models"].get(target), LogisticRegression):
        beta0_arr.append(best_model_attr["models"].get(target).coef_ == 0)
        targets.append(target)
    else:
        target_GCV = best_model_attr["models"].get(target)
        beta0_arr.append(target_GCV.best_estimator_.coef_ == 0)
        targets.append(target)

beta0_df = pd.DataFrame(index=targets, data=beta0_arr)
beta0_df.sum()
sns.barplot(x=beta0_df.sum().index, y=beta0_df.sum().values, ax=axs['c)'])
axs['c)'].set_xlabel('coefficient number')
axs['c)'].set_ylabel('count')
axs['c)'].set_title(f'frequency of coefficients set to 0 ('
                    f'{meta_data["metadata"]["task"]} - {meta_data["metadata"]["feature_type"]})', fontsize=12,
                    fontweight='bold')
sns.despine(right=True)
plt.tight_layout()
plt.show()
plt.close()

# generate scatter plot of predictions
# plot y_true vs y_pred, in title: overall correlation

# compute the overall pcc and scc
pcc = stats.pearsonr(best_model_attr["pred_df"]["y_true"], best_model_attr["pred_df"]["y_pred"])[0]
scc = stats.spearmanr(best_model_attr["pred_df"]["y_true"], best_model_attr["pred_df"]["y_pred"])[0]

sns.scatterplot(x="y_true", y="y_pred", data=best_model_attr["pred_df"])
plt.title(f"Overall PCC: {pcc:.2f}, SCC: {scc:.2f}", fontsize=12, fontweight='bold')
plt.xlabel('pEC50[M] ground truth')
plt.ylabel('pEC50[M] prediction')
sns.despine(right=True)
plt.show()
plt.close()

# average number of datapoints per model:
# for training
ls = []
for target in logistic_classifier.data_dict:
    ls.append(np.shape(logistic_classifier.data_dict.get(target).get("X_train"))[0])

logger.info(
    f"\n\nAverage number of datapoints per model for training: {ls.mean()}\n")

# for testing
logger.info(
    f"\n\nAverage number of datapoints per model for testing:"
    f" {best_model_attr['pred_df'].groupby('target').size().mean()}\n")

sns.histplot(x=best_model_attr['pred_df'].groupby('target').size())
plt.title(f"Average number of datapoints per model for testing:"
          f" {best_model_attr['pred_df'].groupby('target').size().mean()}",
          fontsize=12, fontweight='bold')
plt.xlabel('number of samples in a model')
plt.ylabel('number of models')
sns.despine(right=True)
plt.show()
plt.close()
