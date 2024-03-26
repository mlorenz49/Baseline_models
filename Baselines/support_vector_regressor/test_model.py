import logging
import os
import sys
import toml
from os.path import dirname, join, abspath
from pathlib import Path
from sklearn.svm import SVR

sys.path.insert(0, abspath(join(dirname(__file__), '..')))
from model import SupportVectorRegressor
from utils.utils import mkdir
from utils import testing, analysis

# setting up logging
logging.basicConfig(format='%(asctime)s: %(levelname)s: %(message)s', level=logging.INFO)

# setting up directory for saving results
# save model parameters and results
dir_path = "/nfs/home/students/m.lorenz/output/svr/GDSC/SVR_LCO_20feat_poly_kernel/"
mkdir(dir_path)

# setting up file logging as well
file_logger = logging.FileHandler(Path(os.getcwd() / Path(dir_path + 'Baseline-models.log')), mode='w')
file_logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_logger.setFormatter(formatter)
logging.getLogger().addHandler(file_logger)

# setting up logger for current module
logger = logging.getLogger(__name__)

# start logging
logger.info("Running support vector regression model")

# read in meta data from TOML file
logger.info("Reading in meta data from TOML file")
with open('metadata_LCO.toml', 'r') as file:
    meta_data = toml.load(file)

# create linear regression object
logger.info("Creating support vector regression object")

sv_regression = testing.parse_data(meta_data, SupportVectorRegressor, "SV")

# perform training, testing and evaluation
best_models, best_nfeatures, best_scc, best_models_params = (
    testing.train_test_eval(sv_regression, SVR, "regression", meta_data, dir_path))

# perform data analysis
logger.info("Performing data analysis")
analysis.base_analysis(best_models, sv_regression, "regression", meta_data, dir_path)
# analysis.coef0_distribution(best_models, best_nfeatures, SVC, meta_data, dir_path) # only for linear kernel
analysis.scores_clustering(best_models, dir_path, "regression")
analysis.scatter_predictions(best_models, dir_path)